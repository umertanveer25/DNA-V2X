# Milestone 1 Empirical Challenge Report: Adversarial Verification & Audit

**Agent**: Challenger M1_1 (`challenger_m1_1`)  
**Parent Agent**: `8e427327-1383-435e-84f9-65791f49405e`  
**Working Directory**: `C:\Users\umert\.gemini\antigravity\scratch\DNA-V2X\.agents\teamwork\challenger_m1_1`  
**Project Root**: `C:\Users\umert\.gemini\antigravity\scratch\DNA-V2X`  
**Date**: 2026-10-08  
**Verdict**: **`REJECT`** (Conditional on Remediation of Critical Integer Overflow Crash BUG-01 and History Window Truncation FLAW-02 in `src/attack_classifier.py`)

---

## Challenge Summary

- **Overall Risk Assessment**: **HIGH**
- **Approved Subsystems**:
  - Cryptographic Keystream & 32-bit Rejection Fisher-Yates Shuffle (`src/dna_4mer_engine.py`): **PASSED** (100,000 iterations, 0 bijection failures, Chi-square uniformity p-values: 0.8722, 0.2396, 0.8922).
  - Memory Sanitization & LRU Cache Concurrency (`src/dna_4mer_engine.py`): **PASSED** (16 concurrent threads, 32,000 ops, bounded capacity invariant strictly maintained, master seed zeroed to `b"\x00"*32`, purge barrier verified).
  - Telemetry Schemas Boundary & NaN Fuzzing (`src/v2x_telemetry_schema.py`): **PASSED** (27 NaN/Inf injections rejected with `ValueError`, 10,000 randomized roundtrips accurate within $10^{-7}$ degrees and $0.005\text{ km/h}$, safe boundary clipping).
- **Rejected Subsystems / Deficiencies**:
  - `src/attack_classifier.py:229`: **CRITICAL CRASH (BUG-01)** — Unhandled `OverflowError: Python int too large to convert to C long` when evaluating `0x100000000 - ts_diff` with `numpy.uint32` timestamps on Windows 64-bit systems.
  - `src/attack_classifier.py:137`: **HIGH LOGIC FLAW (FLAW-02)** — Past ratchet replay search loop hardcodes `for delay in range(1, 9):`, truncating the 16-frame history buffer and causing 100% false Sybil ghost injection misclassification for authentic delayed frames with $d \in [9, 15]$.
  - `src/attack_classifier.py:178`: **MEDIUM ANOMALY (ANOMALY-03)** — Replays with $d=1$ (100 ms) and $d=2$ (200 ms) under 10 Hz streaming fall under the `drift <= 200.0` threshold, misclassifying replay attacks as `MITM_DESYNC` (Class 5).

---

## 1. Observation

### Empirical Test Execution & Verbatim Evidence

#### Test 1: Cryptographic Keystream & Shuffle (`tests/adversarial_keystream.py`)
Executed command:
```powershell
python tests/adversarial_keystream.py
```
Verbatim stdout output:
```
======================================================================
ADVERSARIAL TEST 1: Cryptographic Keystream & Shuffle
======================================================================
[*] Running 100,000 iterations of Fisher-Yates shuffle...
    Completed 25,000/100,000 (25.0%) in 5.03s...
    Completed 50,000/100,000 (50.0%) in 10.22s...
    Completed 75,000/100,000 (75.0%) in 17.25s...
    Completed 100,000/100,000 (100.0%) in 22.30s...
[*] Completed 100,000 iterations in 22.30s (4484.7 iter/s).
[*] Bijection Failures: 0/100000
[*] Uniformity (Index 0): Chi2 Stat = 229.550, df = 255, p-value = 0.8722
[*] Uniformity (Index 127): Chi2 Stat = 270.623, df = 255, p-value = 0.2396
[*] Uniformity (Index 255): Chi2 Stat = 227.425, df = 255, p-value = 0.8922
[*] Empirical Rejections observed: 1
[*] Theoretical Expected Rejections: 0.3485
[*] Testing rejection boundary behavior across all k in [2, 256]...
[*] All 255 rejection boundaries strictly verified!
[*] Verifying DynamicPermutationState API consistency...
[+] TASK 1 ADVERSARIAL TESTS PASSED!
```

#### Test 2: Memory Sanitization & LRU Cache Concurrency (`tests/adversarial_cache_and_memory.py`)
Executed command:
```powershell
python tests/adversarial_cache_and_memory.py
```
Verbatim stdout output:
```
======================================================================
ADVERSARIAL TEST 2: Memory Sanitization & LRU Cache Concurrency
======================================================================
[*] Launching 16 threads executing 32,000 cache operations...
[*] Concurrency stress test finished in 0.16s.
[*] Maximum observed cache size: 64 (Max limit: 64).
[*] Error count: 0
[*] Testing master seed zeroization and historical buffer purge...
[*] Master seed zeroization and purge barrier verified successfully!
[*] Testing concurrent state allocation and mid-flight purging across 8 threads...
[+] TASK 2 ADVERSARIAL TESTS PASSED!
```

#### Test 3: Ratchet Replay & Sybil Discrimination (`tests/adversarial_ratchet_replay.py`)
Executed command:
```powershell
python tests/adversarial_ratchet_replay.py
```
Verbatim stdout output:
```
======================================================================
ADVERSARIAL TEST 3: Ratchet Replay Verification & Sybil Discrimination
======================================================================
[*] Generating multi-frame streaming ratchet from t = 0 to t = 16...
[*] Alice and Bob synchronized at epoch t = 16.
[*] Bob history buffer size: 16 / 16
[*] Bob history epochs present: [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15]

[*] Testing replay injection at current epoch t=16 for delays d = 1 .. 15:
    Format: Delay | Past Epoch | Stale Drift (ms) | f7 (Replay) | f8 (Sybil) | Class Pred | Status
    ---------------------------------------------------------------------------
[*] Sub-test 3A: Testing with np.uint32 timestamp (standard C uint32 array)...
    [CONFIRMED BUG BUG-01] extract_features_vectorized() raises OverflowError on Windows with np.uint32 timestamps: Python int too large to convert to C long

[*] Sub-test 3B: Testing replay injection across delays d = 1 .. 15 (using int64 timestamps):
    Format: Delay | Past Epoch | Stale Drift (ms) | f7 (Replay) | f8 (Sybil) | Class Pred | Status
    ---------------------------------------------------------------------------
    d= 1   | Epoch 15  |  100 ms           | 0.0         | 0.0        | 5 (MITM_DESYNC    ) | ANOMALY
    d= 2   | Epoch 14  |  200 ms           | 0.0         | 0.0        | 5 (MITM_DESYNC    ) | ANOMALY
    d= 3   | Epoch 13  |  300 ms           | 1.0         | 0.0        | 1 (REPLAY_ATTACK  ) | PASS
    d= 4   | Epoch 12  |  400 ms           | 1.0         | 0.0        | 1 (REPLAY_ATTACK  ) | PASS
    d= 5   | Epoch 11  |  500 ms           | 1.0         | 0.0        | 1 (REPLAY_ATTACK  ) | PASS
    d= 6   | Epoch 10  |  600 ms           | 1.0         | 0.0        | 1 (REPLAY_ATTACK  ) | PASS
    d= 7   | Epoch  9  |  700 ms           | 1.0         | 0.0        | 1 (REPLAY_ATTACK  ) | PASS
    d= 8   | Epoch  8  |  800 ms           | 1.0         | 0.0        | 1 (REPLAY_ATTACK  ) | PASS
    d= 9   | Epoch  7  |  900 ms           | 0.0         | 1.0        | 3 (SYBIL_GHOST_INJECTION) | ANOMALY
    d=10   | Epoch  6  | 1000 ms           | 0.0         | 1.0        | 3 (SYBIL_GHOST_INJECTION) | ANOMALY
    d=11   | Epoch  5  | 1100 ms           | 0.0         | 1.0        | 3 (SYBIL_GHOST_INJECTION) | ANOMALY
    d=12   | Epoch  4  | 1200 ms           | 0.0         | 1.0        | 3 (SYBIL_GHOST_INJECTION) | ANOMALY
    d=13   | Epoch  3  | 1300 ms           | 0.0         | 1.0        | 3 (SYBIL_GHOST_INJECTION) | ANOMALY
    d=14   | Epoch  2  | 1400 ms           | 0.0         | 1.0        | 3 (SYBIL_GHOST_INJECTION) | ANOMALY
    d=15   | Epoch  1  | 1500 ms           | 0.0         | 1.0        | 3 (SYBIL_GHOST_INJECTION) | ANOMALY

[*] Testing Sybil Ghost Injection (unauthorized key)...
[*] Sybil Feature f7 (replay): 0.0, f8 (sybil): 1.0
[*] Sybil Classification: 3 (SYBIL_GHOST_INJECTION)
[*] Sybil discrimination verified: Class 3 correctly assigned!
```

#### Test 4: Schemas Fuzzing (`tests/adversarial_schemas_fuzz.py`)
Executed command:
```powershell
python tests/adversarial_schemas_fuzz.py
```
Verbatim stdout output:
```
======================================================================
ADVERSARIAL TEST 4: Telemetry Schemas Fuzzing (SPaT, DENM, BSM)
======================================================================
[*] Fuzzing NaN, +Inf, -Inf on BSM fields...
    BSM: Successfully rejected 18 invalid float permutations.
    SPaT: Successfully rejected 3 countdown NaN/Inf values.
    DENM: Successfully rejected 6 speed/heading NaN/Inf values.
[*] Testing extreme coordinate, speed, acceleration, and elevation clipping...
    BSM extreme bounds: All 5 extremal scenarios clipped and deserialized safely.
    SPaT extreme bounds: Countdowns safely clamped to [0.0, 120.0].
    DENM extreme bounds: Speeds safely clamped to [0.0, 250.0].
[*] Running 10,000 randomized roundtrip serialization tests...
    10,000 roundtrips passed! Max quantization errors:
      Latitude err:    0.00000005 deg (expected <= 1e-7)
      Longitude err:   0.00000005 deg (expected <= 1e-7)
      Speed err:       0.0050 km/h (expected <= 0.01)
      Acceleration err:0.0050 m/s^2 (expected <= 0.01)
[*] Testing malformed payloads and CRC tampering...
[+] TASK 4 ADVERSARIAL TESTS PASSED!
```

---

## 2. Logic Chain

### Logic Chain 1: Cryptographic Shuffle & Uniformity (F-01 Verification)
1. **Observation**: `_generate_epoch_permutation()` in `src/dna_4mer_engine.py` (lines 184-194) implements rejection sampling using unsigned 32-bit words `val`:
   $$\text{limit} = 2^{32} - (2^{32} \pmod k)$$
   where $k = i + 1$ for $i \in [255, 1]$.
2. **Mathematical Soundness**: Since $\text{limit}$ is an exact multiple of $k$, each residue $j \in [0, k-1]$ has exactly $\lfloor 2^{32}/k \rfloor$ representatives in $[0, \text{limit}-1]$. Conditioning on $val < \text{limit}$ yields $P(j) = 1/k$ identically.
3. **Empirical Evidence**: Across 100,000 independent shuffle invocations:
   - 0 bijection violations occurred; every permutation mapped all 256 codons bijectively.
   - Positional Pearson Chi-square tests on indices 0, 127, and 255 produced p-values of 0.8722, 0.2396, and 0.8922 ($df=255$), failing to reject the null hypothesis of uniform distribution.
   - Exact boundary test on synthetic streams accepted $limit - 1$ and rejected $limit$ and $0xFFFFFFFF$ for all $k \in [2, 256]$.

### Logic Chain 2: Memory Sanitization & LRU Cache (F-02, F-03 Verification)
1. **Observation**: `PermutationLRUCache` utilizes an `OrderedDict` enclosed by a re-entrant-safe `threading.Lock()` across all mutations and accessors.
2. **Empirical Evidence**: 16 concurrent worker threads executing 32,000 simultaneous `put`, `get`, `evict_session`, and `clear` calls maintained `len(cache) <= 64` continuously without deadlock or `KeyError`.
3. **Zeroization Verification**: `purge_memory()` in `src/dna_4mer_engine.py` sets `self.master_seed = b"\x00" * 32`, overwrites `self.active_byte_to_4mer = ["AAAA"] * 256`, clears `active_4mer_to_byte`, zeroes all historical snapshot tuples, and clears the deque. Calling `ratchet_forward()` or `_generate_epoch_permutation()` on a purged state immediately raises `RuntimeError`.

### Logic Chain 3: Ratchet Replay vs Sybil Misclassification (F-04 Verification Breakdown)
1. **Observation 1 (History Buffer Capacity)**: `DynamicPermutationState` in `src/dna_4mer_engine.py` defines `history_window: int = 16`, maintaining snapshots of the last 16 epochs in `self._history = deque(maxlen=16)`.
2. **Observation 2 (Hardcoded Truncation in Classifier)**: In `src/attack_classifier.py` line 137:
   ```python
   # Check Past Ratchet States (f-1 to f-8) -> Replay Attack or Desync
   for delay in range(1, 9):
   ```
   The search window only inspects delays $1 \dots 8$.
3. **Observation 3 (Falling into Sybil Classification)**: For any authentic replayed packet with delay $d \in [9, 15]$:
   - Delay is within the valid 16-frame history buffer (`bob.history_buffer` contains epochs $0 \dots 15$).
   - But the loop in `extract_features_vectorized()` terminates at delay 8.
   - `past_replay_match` remains $0.0$.
   - The packet is decoded with current epoch tables, producing pseudo-random bytes. CRC check fails (`crc_match == 0.0`), message header check fails, and line 238 executes:
     ```python
     features[i, 8] = 1.0  # Completely foreign key -> Sybil Ghost
     ```
   - Vectorized classifier assigns Class 3 (`SYBIL_GHOST_INJECTION`) instead of Class 1 (`REPLAY_ATTACK`).
4. **Conclusion**: Worker M1's claim that F-04 "eliminates Sybil misclassification" across forward ratchets is empirically refuted for delays $9 \dots 15$. 100% of packets replayed with delays $9 \dots 15$ are falsely flagged as foreign Sybil attacks.

### Logic Chain 4: Integer Overflow Crash on Windows 64-bit (BUG-01)
1. **Observation**: In `src/attack_classifier.py` lines 228-229:
   ```python
   ts_diff = (curr_time - parsed_ts) & 0xFFFFFFFF
   ts_valid = (ts_diff < 10000) or ((0x100000000 - ts_diff) < 10000)
   ```
2. **Mechanism**:
   - `current_timestamps_ms` is an array of timestamps, typically typed as `numpy.uint32`.
   - `curr_time` is a `numpy.uint32` scalar.
   - `ts_diff` evaluates to a `numpy.uint32` scalar.
   - When evaluating `0x100000000 - ts_diff`, Python binary subtraction converts the Python integer `0x100000000` ($4,294,967,296$) into the C integer type corresponding to NumPy's integer type (`long`).
   - On Windows 64-bit systems (MSVC runtime), C `long` is 32-bit signed (`LONG_MAX = 2,147,483,647`).
   - Because $4,294,967,296 > 2,147,483,647$, the conversion raises:
     ```
     OverflowError: Python int too large to convert to C long
     ```
3. **Blast Radius**: Any batch containing an unverified frame (such as an adversarial injection, Sybil ghost, corrupted frame, or delay $\ge 9$ packet) crashes the entire feature extraction function with an unhandled `OverflowError`.

---

## 3. Caveats

1. **Linux / POSIX C Data Model**: On Linux 64-bit (LP64), C `long` is 64-bit, so `0x100000000` fits in signed `long`. The `OverflowError` specifically crashes Windows systems (LLP64). However, multi-platform vehicular ECUs and development workstations on Windows are severely impacted.
2. **Replay Drift Threshold**: In high-frequency 100 Hz V2X streaming (10 ms interval), frames replayed after 1 to 20 frames have drift $\le 200\text{ ms}$. Whether low-delay replays should be categorized as `MITM_DESYNC` or `REPLAY_ATTACK` is an architectural choice, but currently delays 1 and 2 produce Class 5 instead of Class 1.

---

## 4. Conclusion & Required Remediation

### Authoritative Verdict: **`REJECT`**

While the core cryptographic engine (`src/dna_4mer_engine.py`) and schema serialization (`src/v2x_telemetry_schema.py`) pass all adversarial tests with flying colors, Milestone 1 cannot be approved in its current state due to two concrete defects in `src/attack_classifier.py`:

### Required Remediation Patches for Worker M1

#### 1. Fix BUG-01 (Integer Overflow in `src/attack_classifier.py:229`)
Cast `ts_diff` and `curr_time` to native Python `int` or 64-bit integers prior to arithmetic:
```python
# Remediation in src/attack_classifier.py:
curr_time_val = int(current_timestamps_ms[i])
parsed_ts = int(struct.unpack(">I", byte_list[6:10])[0])
ts_diff = (curr_time_val - parsed_ts) & 0xFFFFFFFF
ts_valid = (ts_diff < 10000) or ((0x100000000 - int(ts_diff)) < 10000)
```

#### 2. Fix FLAW-02 (Replay Window Truncation in `src/attack_classifier.py:137`)
Dynamically query the receiver state's history window (or up to 16 frames) instead of hardcoding `range(1, 9)`:
```python
# Remediation in src/attack_classifier.py:
max_history = min(state.frame_counter, getattr(state, "_history_window_size", 16))
for delay in range(1, max_history + 1):
```

---

## 5. Verification Method

### Automated Unit Test Suite
```powershell
python -m unittest discover tests/ -v
```
**Expected Result**: All 79 tests pass cleanly.

### Reproducing Challenger Adversarial Test Harnesses
1. **Keystream Uniformity & 32-bit Rejection (Task 1)**:
   ```powershell
   python tests/adversarial_keystream.py
   ```
   **Pass Condition**: 100,000 iterations complete, 0 bijection failures, Chi-square p-values $> 0.001$, all 255 boundaries verified.

2. **LRU Concurrency & Memory Sanitization (Task 2)**:
   ```powershell
   python tests/adversarial_cache_and_memory.py
   ```
   **Pass Condition**: 16 concurrent threads complete 32,000 ops, max cache size $\le 64$, master seed zeroed to `b"\x00"*32`, post-purge raises `RuntimeError`.

3. **Ratchet Replay & Sybil Discrimination (Task 3)**:
   ```powershell
   python tests/adversarial_ratchet_replay.py
   ```
   **Demonstration**: Reproduces `OverflowError` (BUG-01) on sub-test 3A, and demonstrates false Sybil classification for delays $9 \dots 15$ on sub-test 3B.

4. **Telemetry Schemas NaN & Boundary Fuzzing (Task 4)**:
   ```powershell
   python tests/adversarial_schemas_fuzz.py
   ```
   **Pass Condition**: 27 NaN/Inf rejections, 10,000 roundtrips accurate, extreme values safely clamped.
