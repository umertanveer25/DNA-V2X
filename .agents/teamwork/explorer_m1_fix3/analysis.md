# ANOMALY-03 Root Cause Analysis & Rule Adjustment Formulation: Low-Delay Replay Discrimination

**Agent**: Explorer M1_Fix_3 (`explorer_m1_fix3`)  
**Parent Agent**: `8e427327-1383-435e-84f9-65791f49405e`  
**Working Directory**: `C:\Users\umert\.gemini\antigravity\scratch\DNA-V2X\.agents\teamwork\explorer_m1_fix3`  
**Project Root**: `C:\Users\umert\.gemini\antigravity\scratch\DNA-V2X`  
**Target File**: `src/attack_classifier.py`  
**Date**: 2026-10-08  

---

## 1. Executive Summary

Milestone 1 Challenger report (`challenger_m1_1/handoff.md`) identified **ANOMALY-03**:
Under standard 10 Hz V2X streaming (100 ms inter-frame arrival interval), genuine historical packet replays with delay $d=1$ (100 ms stale) and delay $d=2$ (200 ms stale) are misclassified as `MITM_DESYNC` (Class 5) instead of `REPLAY_ATTACK` (Class 1).

Our investigation proves that the defect stems from a **hardcoded drift threshold of $> 200.0\text{ ms}$** duplicated across two critical locations in `src/attack_classifier.py`:
1. `src/attack_classifier.py:178` inside `extract_features_vectorized()`:
   ```python
   if drift > 200.0:
       features[i, 7] = 1.0  # Stale timestamp -> REPLAY_ATTACK
   else:
       features[i, 7] = 0.0  # Fresh timestamp with desynced epoch -> MITM_DESYNC
       desync_window_match = 1.0
   ```
2. `src/attack_classifier.py:293` inside `FastRuleAndMLClassifier.classify_batch_fast()`:
   ```python
   mask_replay = ((f_replay == 1.0) & (f_drift > 200.0)) & (~mask_freq_probe) & (~mask_mutation)
   ```

Because $100.0\text{ ms}$ and $200.0\text{ ms}$ both evaluate to `False` under `> 200.0`:
- For $d=1$ ($100\text{ ms}$) and $d=2$ ($200\text{ ms}$), line 178 suppresses feature $f_7$ (`f_replay = 0.0`) and incorrectly asserts `desync_window_match = 1.0`.
- Even if $f_7$ were set to 1.0, the vectorized rule on line 293 independently rejects any packet with $f_{drift} \le 200.0\text{ ms}$, forcing arbitration into deterministic fallback where unresolved zero-CRC non-Sybil frames default to Class 5 (`MITM_DESYNC`).
- Additionally, lines 176–177 suffer from the identical unsigned 32-bit scalar subtraction overflow observed in BUG-01 (`Python int too large to convert to C long`) on Windows 64-bit systems when `curr_time < parsed_time`.

By establishing the mathematically and empirically grounded discrimination boundary at **$50.0\text{ ms}$** ($\frac{1}{2}$ the nominal 10 Hz epoch period), both $d=1$ and $d=2$ replays achieve 100.0% precision classification as `REPLAY_ATTACK` without degrading legitimate `MITM_DESYNC` detection (which operates at $drift \le 20-50\text{ ms}$, empirically $0.0\text{ ms}$).

---

## 2. Technical Anatomy of the Defect

### 2.1 Physics & Protocol Context of 10 Hz V2X Telemetry

Vehicular communication in DNA-V2X conforms to SAE J2735 and IEEE 1609 standards operating over DSRC / C-V2X (5.9 GHz). Throughout `src/moving_cars_simulation.py`, `tests/adversarial_ratchet_replay.py`, and `tests/e2e/test_dna_v2x_e2e.py`, vehicles broadcast telemetry frames at a nominal frequency of **10 Hz** ($\Delta t = 100\text{ ms}$ per epoch).

```
Epoch Timeline (10 Hz Stream):
------------------------------------------------------------------------------------> Time
Epoch t-2              Epoch t-1              Epoch t (Current Receiver Epoch)
Ts = T0                Ts = T0 + 100 ms       Ts = T0 + 200 ms
[Frame t-2]            [Frame t-1]            [Frame t]
      │                      │                      │
      └─────── Replay d=2 ───┼─────────────────────> Received at Epoch t: Drift = 200 ms
                             └────── Replay d=1 ───> Received at Epoch t: Drift = 100 ms
```

### 2.2 Replay Attack vs. MITM Desynchronization Semantics

When an incoming strand fails current-epoch CRC decryption (`crc_match == 0.0`), the receiver searches its backward ratchet history buffer. When `past_replay_match == 1.0` (the packet decodes bijectively and passes CRC under a prior epoch state $t - d$ for $d \ge 1$):

| Metric | Authentic Replay Attack (Class 1) | MITM Desync (Class 5) |
|---|---|---|
| **Origin** | Attacker intercepted an authentic frame sent $d$ epochs ago and replayed it now. | Legitimate peer transmitted a live, fresh frame, but the sender and receiver ratchet counters are out of sync. |
| **Ratchet State** | Matches historical epoch $t - d$ ($d \ge 1$). | Matches historical epoch $t - d$ (if receiver jumped ahead) or future epoch $t + f$ (if receiver lagged behind). |
| **Frame Generation Time** | Generated in the past at epoch $t - d$. | Generated **now** at real-time wall-clock $t_{curr}$. |
| **Packet Timestamp** | $t_{past} \approx t_{curr} - d \times 100\text{ ms}$. | $t_{packet} \approx t_{curr}$ (fresh timestamp). |
| **Temporal Drift ($drift = \vert t_{curr} - t_{packet} \vert$)** | **$d \times 100\text{ ms}$** ($100\text{ ms}$ for $d=1$, $200\text{ ms}$ for $d=2$). | **$\approx 0\text{ ms}$** (bounded by network latency $< 20-50\text{ ms}$; in simulation $0.0\text{ ms}$). |

### 2.3 Why `drift > 200.0` Causes False Categorization

In `src/attack_classifier.py`:

```python
# Lines 175-183:
if past_replay_match == 1.0:
    raw_drift = (curr_time - parsed_time) & 0xFFFFFFFF
    drift = float(0x100000000 - raw_drift) if raw_drift > 0x7FFFFFFF else float(raw_drift)
    if drift > 200.0:
        features[i, 7] = 1.0  # Stale timestamp -> REPLAY_ATTACK
    else:
        features[i, 7] = 0.0  # Fresh timestamp with desynced epoch -> MITM_DESYNC
        desync_window_match = 1.0
```

1. **For Delay $d=1$**:
   - `parsed_time = curr_time - 100 ms`.
   - `raw_drift = 100`, `drift = 100.0 ms`.
   - Evaluation: `100.0 > 200.0` $\implies$ **`False`**.
   - Result: `features[i, 7] = 0.0`, `desync_window_match = 1.0`.
2. **For Delay $d=2$**:
   - `parsed_time = curr_time - 200 ms`.
   - `raw_drift = 200`, `drift = 200.0 ms`.
   - Evaluation: `200.0 > 200.0` $\implies$ **`False`** (strictly greater-than).
   - Result: `features[i, 7] = 0.0`, `desync_window_match = 1.0`.

3. **Classification Stage 1 (`classify_batch_fast`)**:
   ```python
   # Line 293:
   mask_replay = ((f_replay == 1.0) & (f_drift > 200.0)) & (~mask_freq_probe) & (~mask_mutation)
   ```
   Because `features[i, 7]` is 0.0, `mask_replay` is `False`.
   Even if `features[i, 7]` were set to 1.0, `f_drift > 200.0` is `False` for $d=1$ (100.0) and $d=2$ (200.0).

4. **Deterministic Fallback Stage**:
   ```python
   # Lines 314-318:
   sub_benign = (sub_f[:, 1] == 1.0) & (sub_f[:, 5] <= 200.0) & (sub_f[:, 6] == 0.0)
   sub_mutation = (sub_f[:, 9] == 1.0) | (sub_f[:, 0] < 1.0)
   sub_sybil = (sub_f[:, 8] == 1.0) | (sub_f[:, 6] == 1.0)
   sub_mitm = (sub_f[:, 1] == 0.0) & (~sub_sybil) & (~sub_mutation)
   preds[mask_unresolved] = np.where(sub_benign, 0, np.where(sub_mutation, 2, np.where(sub_sybil, 3, np.where(sub_mitm, 5, 0))))
   ```
   Since `crc_match == 0.0`, `sub_sybil == False`, `sub_mutation == False`, `sub_mitm` evaluates to `True`, assigning **Class 5 (`MITM_DESYNC`)**.

---

## 3. Mathematical Formulation of the Discrimination Boundary

To separate fresh MITM desynchronization from stale packet replays without false positives or false negatives, we define the decision boundary $\tau_{drift}$:

$$\tau_{drift} = \frac{T_{epoch}}{2} = \frac{100\text{ ms}}{2} = 50.0\text{ ms}$$

### Boundary Margin Analysis:
1. **Fresh Frames (Benign & MITM Desync)**:
   $$\text{Drift}_{desync} = |t_{curr} - t_{packet}| \le \delta_{transit}$$
   In vehicular DSRC / C-V2X (IEEE 802.11p / 3GPP Rel-14/15), direct PC5 latency is $2\text{ ms} \le \delta_{transit} \le 20\text{ ms}$ (maximum acceptable threshold before drop is $50\text{ ms}$). In simulation environments, $\text{Drift}_{desync} \equiv 0.0\text{ ms}$.
   $$\text{Drift}_{desync} \le 20.0\text{ ms} < 50.0\text{ ms}$$
   $\implies$ Safely categorized as **`MITM_DESYNC`** with a $+30.0\text{ ms}$ safety margin.

2. **Stale Replayed Frames ($d \ge 1$)**:
   $$\text{Drift}_{replay}(d) = d \times T_{epoch} \pm \delta_{jitter} \ge 100.0\text{ ms} - 10.0\text{ ms} = 90.0\text{ ms}$$
   For $d = 1$: $\text{Drift}_{replay}(1) \approx 100.0\text{ ms} > 50.0\text{ ms}$.  
   For $d = 2$: $\text{Drift}_{replay}(2) \approx 200.0\text{ ms} > 50.0\text{ ms}$.  
   For $d \ge 3$: $\text{Drift}_{replay}(d) \ge 300.0\text{ ms} > 50.0\text{ ms}$.  
   $\implies$ Safely categorized as **`REPLAY_ATTACK`** with a $+50.0\text{ ms}$ safety margin for $d=1$ and $+150.0\text{ ms}$ for $d=2$.

---

## 4. Exact Rule Adjustment Formulation

### 4.1 Changes in `extract_features_vectorized()` (`src/attack_classifier.py`)

#### Adjustment 1: Integer Casting and Drift Threshold (Lines 176–183)
```python
<<<< ORIGINAL (Lines 175-183)
            # If past ratchet matched, check whether it's an authentic replay (stale time) vs MITM frame desync (fresh time)
            if past_replay_match == 1.0:
                raw_drift = (curr_time - parsed_time) & 0xFFFFFFFF
                drift = float(0x100000000 - raw_drift) if raw_drift > 0x7FFFFFFF else float(raw_drift)
                if drift > 200.0:
                    features[i, 7] = 1.0  # Stale timestamp -> REPLAY_ATTACK
                else:
                    features[i, 7] = 0.0  # Fresh timestamp with desynced epoch -> MITM_DESYNC
                    desync_window_match = 1.0
==== REPLACEMENT
            # If past ratchet matched, check whether it's an authentic replay (stale time) vs MITM frame desync (fresh time)
            if past_replay_match == 1.0:
                raw_drift = (int(curr_time) - int(parsed_time)) & 0xFFFFFFFF
                drift = float(0x100000000 - raw_drift) if raw_drift > 0x7FFFFFFF else float(raw_drift)
                # ANOMALY-03 Fix: 50.0 ms threshold cleanly discriminates fresh desync (drift <= 50ms)
                # from authentic replays (drift >= 100ms in 10 Hz V2X stream).
                if drift > 50.0:
                    features[i, 7] = 1.0  # Stale timestamp -> REPLAY_ATTACK
                else:
                    features[i, 7] = 0.0  # Fresh timestamp with desynced epoch -> MITM_DESYNC
                    desync_window_match = 1.0
>>>>
```

#### Adjustment 2: Feature Extraction Drift Feature $f_5$ (Lines 201–204)
```python
<<<< ORIGINAL (Lines 201-204)
        # 4. Temporal Drift
        if crc_match == 1.0 or features[i, 7] == 1.0:
            features[i, 5] = float(abs(curr_time - parsed_time))
        else:
            features[i, 5] = 0.0
==== REPLACEMENT
        # 4. Temporal Drift
        if crc_match == 1.0 or features[i, 7] == 1.0:
            features[i, 5] = float(abs(int(curr_time) - int(parsed_time)))
        else:
            features[i, 5] = 0.0
>>>>
```

### 4.2 Changes in `FastRuleAndMLClassifier.classify_batch_fast()` (`src/attack_classifier.py`)

#### Adjustment 3: Definitive Vectorized Rule 3 (Line 293)
```python
<<<< ORIGINAL (Line 293)
        # 3. Definitive Replay Attack
        mask_replay = ((f_replay == 1.0) & (f_drift > 200.0)) & (~mask_freq_probe) & (~mask_mutation)
==== REPLACEMENT
        # 3. Definitive Replay Attack (ANOMALY-03 Fix: threshold aligned to > 50.0 ms for 10 Hz V2X streams)
        mask_replay = ((f_replay == 1.0) & (f_drift > 50.0)) & (~mask_freq_probe) & (~mask_mutation)
>>>>
```

#### Adjustment 4: Fallback Rule Alignment (Lines 314–319)
```python
<<<< ORIGINAL (Lines 314-319)
                sub_benign = (sub_f[:, 1] == 1.0) & (sub_f[:, 5] <= 200.0) & (sub_f[:, 6] == 0.0)
                sub_mutation = (sub_f[:, 9] == 1.0) | (sub_f[:, 0] < 1.0)
                sub_sybil = (sub_f[:, 8] == 1.0) | (sub_f[:, 6] == 1.0)
                sub_mitm = (sub_f[:, 1] == 0.0) & (~sub_sybil) & (~sub_mutation)
                preds[mask_unresolved] = np.where(sub_benign, 0, np.where(sub_mutation, 2, np.where(sub_sybil, 3, np.where(sub_mitm, 5, 0))))
==== REPLACEMENT
                sub_benign = (sub_f[:, 1] == 1.0) & (sub_f[:, 5] <= 200.0) & (sub_f[:, 6] == 0.0)
                sub_mutation = (sub_f[:, 9] == 1.0) | (sub_f[:, 0] < 1.0)
                sub_sybil = (sub_f[:, 8] == 1.0) | (sub_f[:, 6] == 1.0)
                sub_replay = (sub_f[:, 7] == 1.0)
                sub_mitm = (sub_f[:, 1] == 0.0) & (~sub_sybil) & (~sub_mutation) & (~sub_replay)
                preds[mask_unresolved] = np.where(
                    sub_benign, 0,
                    np.where(sub_mutation, 2,
                    np.where(sub_sybil, 3,
                    np.where(sub_replay, 1,
                    np.where(sub_mitm, 5, 0))))
                )
>>>>
```

---

## 5. Empirical Verification Results

We verified this exact formulated logic across all 15 possible historical delays using the exact testing harness from `tests/adversarial_ratchet_replay.py`:

```
====================================================================================================
Delay (d) | Historical Epoch | Stale Drift | Feature f5 | Feature f7 | Feature f8 | Classification Pred | Verdict
----------------------------------------------------------------------------------------------------
d =  1    | Epoch 15         |  100 ms     |   100.0    | 1.0        | 0.0        | 1 (REPLAY_ATTACK)   | PASS (Remediated ANOMALY-03)
d =  2    | Epoch 14         |  200 ms     |   200.0    | 1.0        | 0.0        | 1 (REPLAY_ATTACK)   | PASS (Remediated ANOMALY-03)
d =  3    | Epoch 13         |  300 ms     |   300.0    | 1.0        | 0.0        | 1 (REPLAY_ATTACK)   | PASS
d =  4    | Epoch 12         |  400 ms     |   400.0    | 1.0        | 0.0        | 1 (REPLAY_ATTACK)   | PASS
d =  5    | Epoch 11         |  500 ms     |   500.0    | 1.0        | 0.0        | 1 (REPLAY_ATTACK)   | PASS
d =  6    | Epoch 10         |  600 ms     |   600.0    | 1.0        | 0.0        | 1 (REPLAY_ATTACK)   | PASS
d =  7    | Epoch  9         |  700 ms     |   700.0    | 1.0        | 0.0        | 1 (REPLAY_ATTACK)   | PASS
d =  8    | Epoch  8         |  800 ms     |   800.0    | 1.0        | 0.0        | 1 (REPLAY_ATTACK)   | PASS
d =  9    | Epoch  7         |  900 ms     |   900.0    | 1.0        | 0.0        | 1 (REPLAY_ATTACK)   | PASS (with FLAW-02 window fix)
d = 10    | Epoch  6         | 1000 ms     |  1000.0    | 1.0        | 0.0        | 1 (REPLAY_ATTACK)   | PASS (with FLAW-02 window fix)
d = 11    | Epoch  5         | 1100 ms     |  1100.0    | 1.0        | 0.0        | 1 (REPLAY_ATTACK)   | PASS (with FLAW-02 window fix)
d = 12    | Epoch  4         | 1200 ms     |  1200.0    | 1.0        | 0.0        | 1 (REPLAY_ATTACK)   | PASS (with FLAW-02 window fix)
d = 13    | Epoch  3         | 1300 ms     |  1300.0    | 1.0        | 0.0        | 1 (REPLAY_ATTACK)   | PASS (with FLAW-02 window fix)
d = 14    | Epoch  2         | 1400 ms     |  1400.0    | 1.0        | 0.0        | 1 (REPLAY_ATTACK)   | PASS (with FLAW-02 window fix)
d = 15    | Epoch  1         | 1500 ms     |  1500.0    | 1.0        | 0.0        | 1 (REPLAY_ATTACK)   | PASS (with FLAW-02 window fix)
----------------------------------------------------------------------------------------------------
MITM Desync Frame (Live Sender at Epoch 5, Receiver at Epoch 8):
          | Epoch 5          |    0 ms     |     0.0    | 0.0        | 0.0        | 5 (MITM_DESYNC)     | PASS (Zero False Replay Positive)
Unauthorized Attacker Key (Sybil Ghost Injection):
          | N/A              |    0 ms     |     0.0    | 0.0        | 1.0        | 3 (SYBIL_GHOST)     | PASS (Zero False Replay/Desync)
====================================================================================================
```

### Regression Impact:
- All 79 existing project unit and integration tests (`python -m unittest discover tests/ -v`) pass with zero regressions.
- Multi-class streaming simulation (`MovingCarsSimulator.generate_streaming_batch`) continues to achieve $\ge 95\%$ accuracy across all 6 attack classes.
