# Technical Analysis Report: FLAW-02 Replay Search Window Truncation

**Investigating Agent**: Explorer M1_Fix_2 (`explorer_m1_fix2`)  
**Mission**: Formulate exact fix for FLAW-02 in `src/attack_classifier.py:137`  
**Parent Agent**: `8e427327-1383-435e-84f9-65791f49405e`  
**Target File**: `src/attack_classifier.py` (line 137)  
**Related Components**: `src/dna_4mer_engine.py` (`DynamicPermutationState`), `tests/adversarial_ratchet_replay.py`  
**Date**: 2026-10-08  

---

## 1. Executive Summary

In `src/attack_classifier.py`, the feature extraction function `extract_features_vectorized()` inspects past permutation states when a packet's CRC fails against the current epoch permutation matrix (`crc_match == 0.0`). The goal of this search is to determine whether the incoming packet is an authentic frame replayed from an earlier ratchet epoch.

However, line 137 hardcodes the backward search range:
```python
# Check Past Ratchet States (f-1 to f-8) -> Replay Attack or Desync
for delay in range(1, 9):
```
This hardcoded loop restricts backward inspection to at most 8 frames ($d \in [1, 8]$). Meanwhile, the receiver's state machine (`DynamicPermutationState` in `src/dna_4mer_engine.py`) explicitly defaults to a history window of **16 frames** (`history_window: int = 16`, bounded ring buffer `self._history = deque(maxlen=16)`).

As an empirical consequence:
- Any authentic packet delayed by $d \in [9, 15]$ frames (or $d=16$) is ignored by the past ratchet search.
- Feature $f_7$ (`past_ratchet_replay_match`) remains `0.0`.
- The frame cannot be decoded with current epoch tables, CRC fails, header checks fail on pseudo-random bytes, and line 238 assigns:
  ```python
  features[i, 8] = 1.0  # Completely foreign key -> Sybil Ghost
  ```
- The classifier outputs Class 3 (`SYBIL_GHOST_INJECTION`) instead of Class 1 (`REPLAY_ATTACK`).
- **Empirical impact**: **100% false Sybil misclassification** for all authentic replayed frames with delay $d \in [9, 15]$ within the valid history buffer.

---

## 2. Mathematical & Architectural Context

### 2.1 The Receiver History Buffer Design
In `src/dna_4mer_engine.py` (lines 120-137, 202-256):
```python
class DynamicPermutationState:
    def __init__(
        self,
        master_seed: bytes,
        session_id: Union[str, bytes] = "V2V_PAIR_01",
        history_window: int = 16
    ):
        ...
        self._history_window_size = max(1, history_window)
        self._history: deque = deque(maxlen=self._history_window_size)
```
Upon each forward ratchet step (`ratchet_forward()`), the instantaneous permutation matrices and snapshot metadata are stored into `_history`:
```python
        self._history.append({
            "frame_counter": self.frame_counter,
            "master_seed": self.master_seed,
            "byte_to_4mer": list(self.active_byte_to_4mer),
            "4mer_to_byte": dict(self.active_4mer_to_byte)
        })
```
The method `get_historical_permutation(delay: int)` reconstructs the exact permutation state for any $1 \le \text{delay} \le \text{history\_window}$ as long as the snapshot remains in `_history`.

At streaming epoch $t = 16$, the receiver's history buffer contains snapshots for epochs $0, 1, 2, \dots, 15$, spanning delays $d = 1$ (epoch 15) to $d = 16$ (epoch 0).

### 2.2 The Root Cause of FLAW-02
In `src/attack_classifier.py` lines 135-173:
```python
        if crc_match == 0.0:
            # Check Past Ratchet States (f-1 to f-8) -> Replay Attack or Desync
            for delay in range(1, 9):
                if state.frame_counter >= delay:
                    chk_mapping = None
                    if hasattr(state, "get_historical_permutation"):
                        hist_obj = state.get_historical_permutation(delay)
...
```
`range(1, 9)` produces integers `1, 2, 3, 4, 5, 6, 7, 8`.
Delays $9, 10, 11, 12, 13, 14, 15, 16$ are **never queried**.

### 2.3 Cascade into Classifier Features
When $d \ge 9$:
1. Loop terminates without matching: `past_replay_match = 0.0`.
2. Forward search ($f+1 \dots f+8$) evaluates to `desync_window_match = 0.0`.
3. Downstream discrimination checks:
   ```python
   if crc_match == 0.0 and past_replay_match == 0.0:
       ...
       if is_valid_header:
           features[i, 9] = 1.0  # Mutation
       elif desync_window_match == 1.0:
           features[i, 8] = 0.0  # MITM Desync
       else:
           features[i, 8] = 1.0  # Completely foreign key -> Sybil Ghost
   ```
   Because the bytes decoded under the wrong epoch are pseudorandom, `is_valid_header` is false, and line 238 executes: `features[i, 8] = 1.0`.
4. In `FastRuleAndMLClassifier`:
   ```python
   sub_sybil = (sub_f[:, 8] == 1.0) | (sub_f[:, 6] == 1.0)
   ...
   preds[mask_unresolved] = np.where(..., np.where(sub_sybil, 3, ...))
   ```
   The replayed authentic frame is falsely classified as **Class 3 (SYBIL_GHOST_INJECTION)**.

---

## 3. Empirical Verification of the Defect

Running `tests/adversarial_ratchet_replay.py` across delays $d = 1 \dots 15$ at epoch $t = 16$ produced the following verbatim results:

| Delay ($d$) | Past Epoch | Stale Drift | Feature $f_7$ (Replay) | Feature $f_8$ (Sybil) | Predicted Class | Status |
|:---:|:---:|:---:|:---:|:---:|:---:|:---:|
| 1 | 15 | 100 ms | 0.0 | 0.0 | 5 (`MITM_DESYNC`) | ANOMALY (drift $\le 200$) |
| 2 | 14 | 200 ms | 0.0 | 0.0 | 5 (`MITM_DESYNC`) | ANOMALY (drift $\le 200$) |
| 3 | 13 | 300 ms | **1.0** | **0.0** | **1 (`REPLAY_ATTACK`)** | **PASS** |
| 4 | 12 | 400 ms | **1.0** | **0.0** | **1 (`REPLAY_ATTACK`)** | **PASS** |
| 5 | 11 | 500 ms | **1.0** | **0.0** | **1 (`REPLAY_ATTACK`)** | **PASS** |
| 6 | 10 | 600 ms | **1.0** | **0.0** | **1 (`REPLAY_ATTACK`)** | **PASS** |
| 7 | 9 | 700 ms | **1.0** | **0.0** | **1 (`REPLAY_ATTACK`)** | **PASS** |
| 8 | 8 | 800 ms | **1.0** | **0.0** | **1 (`REPLAY_ATTACK`)** | **PASS** |
| **9** | **7** | **900 ms** | **0.0** | **1.0** | **3 (`SYBIL_GHOST_INJECTION`)** | **DEFECT (FLAW-02)** |
| **10** | **6** | **1000 ms** | **0.0** | **1.0** | **3 (`SYBIL_GHOST_INJECTION`)** | **DEFECT (FLAW-02)** |
| **11** | **5** | **1100 ms** | **0.0** | **1.0** | **3 (`SYBIL_GHOST_INJECTION`)** | **DEFECT (FLAW-02)** |
| **12** | **4** | **1200 ms** | **0.0** | **1.0** | **3 (`SYBIL_GHOST_INJECTION`)** | **DEFECT (FLAW-02)** |
| **13** | **3** | **1300 ms** | **0.0** | **1.0** | **3 (`SYBIL_GHOST_INJECTION`)** | **DEFECT (FLAW-02)** |
| **14** | **2** | **1400 ms** | **0.0** | **1.0** | **3 (`SYBIL_GHOST_INJECTION`)** | **DEFECT (FLAW-02)** |
| **15** | **1** | **1500 ms** | **0.0** | **1.0** | **3 (`SYBIL_GHOST_INJECTION`)** | **DEFECT (FLAW-02)** |

This demonstrates 100% false Sybil misclassification for every delay exceeding 8 within the 16-frame window.

---

## 4. Exact Remediation Formulation

### 4.1 Proposed Code Modification

In `src/attack_classifier.py`, lines 136-137:

#### Before:
```python
        if crc_match == 0.0:
            # Check Past Ratchet States (f-1 to f-8) -> Replay Attack or Desync
            for delay in range(1, 9):
                if state.frame_counter >= delay:
```

#### After:
```python
        if crc_match == 0.0:
            # Check Past Ratchet States (f-1 to f-max_history, up to receiver's full history window) -> Replay Attack or Desync
            max_history = min(
                getattr(state, "frame_counter", 0),
                getattr(state, "_history_window_size", getattr(state, "history_window", 16))
            )
            for delay in range(1, max_history + 1):
                if state.frame_counter >= delay:
```

### 4.2 Handling of Edge Cases
1. **Early Session ($t < 16$, e.g., $t = 3$)**:
   - `max_history = min(3, 16) = 3`.
   - The loop runs for $d \in [1, 3]$ only, avoiding useless iterations where $d > \text{frame\_counter}$.
2. **Session Start ($t = 0$)**:
   - `max_history = min(0, 16) = 0`.
   - `range(1, 1)` yields an empty generator; loop executes 0 times with zero overhead.
3. **Custom History Window**:
   - If the receiver is initialized with `history_window = 32`, `getattr(state, "_history_window_size", 16)` returns 32, dynamically scaling the search window without requiring code changes.
   - If initialized with `history_window = 8`, the search cap is 8.
4. **Mock / Duck-Typed States**:
   - Safe attribute fallbacks (`getattr`) prevent `AttributeError` if mock objects lack `_history_window_size` or `frame_counter`.

---

## 5. Verification of the Proposed Fix

When the feature extractor was evaluated with the dynamic history window logic across delays $d = 1 \dots 15$:

| Delay ($d$) | Past Epoch | Stale Drift | $f_7$ (Replay) | $f_8$ (Sybil) | Classification | Status |
|:---:|:---:|:---:|:---:|:---:|:---:|
| 1 | 15 | 100 ms | 0.0 | 0.0 | 5 (`MITM_DESYNC`) | Anomaly (drift $\le 200$) |
| 2 | 14 | 200 ms | 0.0 | 0.0 | 5 (`MITM_DESYNC`) | Anomaly (drift $\le 200$) |
| 3 | 13 | 300 ms | 1.0 | 0.0 | 1 (`REPLAY_ATTACK`) | **PASS** |
| 4 | 12 | 400 ms | 1.0 | 0.0 | 1 (`REPLAY_ATTACK`) | **PASS** |
| 5 | 11 | 500 ms | 1.0 | 0.0 | 1 (`REPLAY_ATTACK`) | **PASS** |
| 6 | 10 | 600 ms | 1.0 | 0.0 | 1 (`REPLAY_ATTACK`) | **PASS** |
| 7 | 9 | 700 ms | 1.0 | 0.0 | 1 (`REPLAY_ATTACK`) | **PASS** |
| 8 | 8 | 800 ms | 1.0 | 0.0 | 1 (`REPLAY_ATTACK`) | **PASS** |
| **9** | **7** | **900 ms** | **1.0** | **0.0** | **1 (`REPLAY_ATTACK`)** | **RESOLVED (PASS)** |
| **10** | **6** | **1000 ms** | **1.0** | **0.0** | **1 (`REPLAY_ATTACK`)** | **RESOLVED (PASS)** |
| **11** | **5** | **1100 ms** | **1.0** | **0.0** | **1 (`REPLAY_ATTACK`)** | **RESOLVED (PASS)** |
| **12** | **4** | **1200 ms** | **1.0** | **0.0** | **1 (`REPLAY_ATTACK`)** | **RESOLVED (PASS)** |
| **13** | **3** | **1300 ms** | **1.0** | **0.0** | **1 (`REPLAY_ATTACK`)** | **RESOLVED (PASS)** |
| **14** | **2** | **1400 ms** | **1.0** | **0.0** | **1 (`REPLAY_ATTACK`)** | **RESOLVED (PASS)** |
| **15** | **1** | **1500 ms** | **1.0** | **0.0** | **1 (`REPLAY_ATTACK`)** | **RESOLVED (PASS)** |

### Discrimination Invariance for True Sybil Injections
A true Sybil attacker transmitting with an unauthorized key (`b"MALICIOUS_ATTACKER_FOREIGN_KEY_XX"`):
- Fails current epoch CRC (`crc_match == 0.0`).
- Fails all historical permutations across all 16 epochs in `_history`.
- Yields $f_7 = 0.0, f_8 = 1.0$, predicted as **Class 3 (`SYBIL_GHOST_INJECTION`)** with 100% precision.
- Sybil discrimination is completely preserved and unaffected by expanding the replay search window.

---

## 6. Interaction with BUG-01 and ANOMALY-03

1. **Relation to BUG-01 (`OverflowError` on Windows)**:
   Prior to this fix, delays $9 \dots 15$ failed past ratchet matching, causing them to fall through to lines 228-229:
   `ts_valid = (ts_diff < 10000) or ((0x100000000 - ts_diff) < 10000)`
   On Windows, this triggered `OverflowError` if timestamps were `np.uint32`. With FLAW-02 resolved, delays $9 \dots 15$ match their past epoch permutation and never reach lines 228-229. However, genuine Sybil and corrupted packets still reach lines 228-229, confirming that BUG-01 and FLAW-02 are distinct flaws that must both be resolved.
2. **Relation to ANOMALY-03 (Low Drift Replay Misclassification)**:
   For delays $d=1$ (100 ms) and $d=2$ (200 ms), `drift <= 200.0` causes line 181 to classify the frame as `MITM_DESYNC` (Class 5). FLAW-02 addresses the truncation of delays $9 \dots 15$ (which have drift $900 \dots 1500\text{ ms} > 200.0$). The drift threshold is a separate parameter.
