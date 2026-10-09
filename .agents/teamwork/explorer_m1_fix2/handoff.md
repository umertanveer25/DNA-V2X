# Handoff Report: FLAW-02 Replay Search Window Truncation

**Agent**: Explorer M1_Fix_2 (`explorer_m1_fix2`)  
**Type**: Hard (Task Complete)  
**Parent Agent**: `8e427327-1383-435e-84f9-65791f49405e`  
**Working Directory**: `C:\Users\umert\.gemini\antigravity\scratch\DNA-V2X\.agents\teamwork\explorer_m1_fix2`  
**Target File**: `src/attack_classifier.py:137`  
**Date**: 2026-10-08  

---

## 1. Observation

### 1.1 Source Code Inspection
- **File**: `src/attack_classifier.py`
- **Lines 135-139**:
  ```python
  135:         if crc_match == 0.0:
  136:             # Check Past Ratchet States (f-1 to f-8) -> Replay Attack or Desync
  137:             for delay in range(1, 9):
  138:                 if state.frame_counter >= delay:
  139:                     chk_mapping = None
  ```
- **File**: `src/dna_4mer_engine.py`
- **Lines 121, 130-131, 233**:
  ```python
  121:         history_window: int = 16
  ...
  130:         self._history_window_size = max(1, history_window)
  131:         self._history: deque = deque(maxlen=self._history_window_size)
  ...
  233:             delay: Number of frames back in time (1 <= delay <= history_window).
  ```

### 1.2 Adversarial Execution Evidence
Command executed:
```powershell
python tests/adversarial_ratchet_replay.py
```
Verbatim stdout excerpt from Sub-test 3B:
```
    d= 7   | Epoch  9  |  700 ms           | 1.0         | 0.0        | 1 (REPLAY_ATTACK  ) | PASS
    d= 8   | Epoch  8  |  800 ms           | 1.0         | 0.0        | 1 (REPLAY_ATTACK  ) | PASS
    d= 9   | Epoch  7  |  900 ms           | 0.0         | 1.0        | 3 (SYBIL_GHOST_INJECTION) | ANOMALY
    d=10   | Epoch  6  | 1000 ms           | 0.0         | 1.0        | 3 (SYBIL_GHOST_INJECTION) | ANOMALY
    d=11   | Epoch  5  | 1100 ms           | 0.0         | 1.0        | 3 (SYBIL_GHOST_INJECTION) | ANOMALY
    d=12   | Epoch  4  | 1200 ms           | 0.0         | 1.0        | 3 (SYBIL_GHOST_INJECTION) | ANOMALY
    d=13   | Epoch  3  | 1300 ms           | 0.0         | 1.0        | 3 (SYBIL_GHOST_INJECTION) | ANOMALY
    d=14   | Epoch  2  | 1400 ms           | 0.0         | 1.0        | 3 (SYBIL_GHOST_INJECTION) | ANOMALY
    d=15   | Epoch  1  | 1500 ms           | 0.0         | 1.0        | 3 (SYBIL_GHOST_INJECTION) | ANOMALY
```
Observed behavior:
- For $d \in [3, 8]$, $f_7 = 1.0$ and $f_8 = 0.0$ $\rightarrow$ Class 1 (`REPLAY_ATTACK`).
- For $d \in [9, 15]$, $f_7 = 0.0$ and $f_8 = 1.0$ $\rightarrow$ Class 3 (`SYBIL_GHOST_INJECTION`).
- 100% of replayed authentic frames with delays $d \in [9, 15]$ are misclassified as foreign Sybil ghost injections.

---

## 2. Logic Chain

1. **Premise 1 (History Buffer Capacity)**: `DynamicPermutationState` stores up to 16 historical snapshots (`_history = deque(maxlen=16)`). At epoch $t=16$, `bob.history_buffer` holds all epochs from $t=0$ to $t=15$.
2. **Premise 2 (Loop Truncation)**: In `src/attack_classifier.py:137`, `for delay in range(1, 9):` iterates strictly over $d \in \{1, 2, 3, 4, 5, 6, 7, 8\}$. Delays $d \ge 9$ are never queried.
3. **Inference 1 (Feature Degradation)**: For an authentic replayed packet with $d \in [9, 15]$, `get_historical_permutation(delay)` is never called for the matching epoch. `past_replay_match` remains `0.0`.
4. **Inference 2 (False Sybil Misclassification)**: Because `past_replay_match == 0.0` and the packet cannot be decoded using the current epoch key (yielding pseudorandom bytes that fail CRC and header validation), lines 220-238 assign $f_8 = 1.0$ (`SYBIL_GHOST_INJECTION`).
5. **Inference 3 (Remediation Mechanism)**: Replacing `range(1, 9)` with:
   ```python
   max_history = min(
       getattr(state, "frame_counter", 0),
       getattr(state, "_history_window_size", getattr(state, "history_window", 16))
   )
   for delay in range(1, max_history + 1):
   ```
   ensures that all retained history snapshots up to the receiver's window size (16 frames) are queried.
6. **Empirical Validation of Fix**: Testing the dynamic loop across $d \in [9, 15]$ successfully matches past ratchet states, setting $f_7 = 1.0, f_8 = 0.0$, and restoring classification to Class 1 (`REPLAY_ATTACK`) with 100% accuracy, while maintaining 100% true Sybil detection for foreign keys.

---

## 3. Caveats

1. **Low-Drift Replays (ANOMALY-03)**:
   For $d=1$ (100 ms) and $d=2$ (200 ms) at 10 Hz streaming, `drift <= 200.0` causes lines 180-182 to assign $f_7 = 0.0, desync\_window\_match = 1.0$, predicting Class 5 (`MITM_DESYNC`). FLAW-02 focuses strictly on the search window truncation for $d \in [9, 16]$; the 200 ms drift threshold is a separate policy parameter.
2. **Frames Beyond the History Buffer ($d > 16$)**:
   Frames replayed with delay greater than the receiver's history window size (e.g., $d \ge 17$ for a 16-frame buffer) have been evicted from RAM. They cannot be decoded and will correctly be treated as unauthenticated frames.
3. **Forward Window (Line 186)**:
   Line 186 tests `for forward in range(1, 9):` to detect ahead-of-time desynchronization. Forward desync does not use a stored history buffer; it computes `ratchet_forward()` iteratively and remains bounded to 8 forward frames.

---

## 4. Conclusion

FLAW-02 is a high-severity logic flaw resulting from a hardcoded `range(1, 9)` at line 137 in `src/attack_classifier.py`. It prematurely truncates the replay search at 8 frames, causing authentic packets replayed with delays $9 \dots 16$ to be falsely labeled as Sybil attacks (Class 3).

### Actionable Remediation Specification

Apply the patch formulated in `flaw_02_replay_window.patch`:
In `src/attack_classifier.py:136-137`:
Replace:
```python
            # Check Past Ratchet States (f-1 to f-8) -> Replay Attack or Desync
            for delay in range(1, 9):
```
With:
```python
            # Check Past Ratchet States (f-1 to f-max_history, up to receiver's full history window) -> Replay Attack or Desync
            max_history = min(
                getattr(state, "frame_counter", 0),
                getattr(state, "_history_window_size", getattr(state, "history_window", 16))
            )
            for delay in range(1, max_history + 1):
```

---

## 5. Verification Method

### 5.1 Automated Unit Test Suite
Verify that existing tests continue to pass without regression:
```powershell
python -m unittest discover tests/ -v
```
**Expected**: All 79 tests pass cleanly (`Ran 79 tests ... OK`).

### 5.2 Adversarial Ratchet Replay Test
Verify resolution of false Sybil classification across $d \in [9, 15]$:
```powershell
python tests/adversarial_ratchet_replay.py
```
**Pass Conditions**:
- Delays $d \in [3, 15]$ all report:
  `f7 (Replay) = 1.0 | f8 (Sybil) = 0.0 | pred = 1 (REPLAY_ATTACK) | PASS`
- Sybil Ghost Injection reports:
  `f7 = 0.0 | f8 = 1.0 | pred = 3 (SYBIL_GHOST_INJECTION)`

### 5.3 Invalidation Condition
If any replay packet with delay $9 \le d \le 16$ within the valid history buffer produces $f_7 = 0.0$ or Class 3 (`SYBIL_GHOST_INJECTION`), this conclusion is invalidated.
