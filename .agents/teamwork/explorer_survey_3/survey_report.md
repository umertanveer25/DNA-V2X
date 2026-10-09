# DNA-V2X Test Infrastructure, Test Coverage & Benchmark Soundness Survey Report

**Survey Lead:** Survey Explorer 3 (Tests & Infra)  
**Date:** 2026-10-08  
**Integrity Mode:** Development  
**Repository Working Directory:** `C:\Users\umert\.gemini\antigravity\scratch\DNA-V2X`  
**Authoritative Reference:** `C:\Users\umert\.gemini\antigravity\scratch\DNA-V2X\.agents\teamwork\ORIGINAL_REQUEST.md`

---

## 1. Executive Summary

This independent survey conducted an exhaustive, line-by-line inspection of the test infrastructure, test runner execution pipelines, Python dependencies, test files in `tests/`, benchmark execution scripts in `benchmarks/` and `experiments/`, and code coverage across all core modules in `src/`.

### Key Findings at a Glance:
1. **Existing Test Suite Baseline:**
   - The test suite comprises **2 test files** (`tests/test_dna_v2x.py` and `tests/test_attack_classifier.py`) containing **17 unit and integration tests** across 5 test classes.
   - All 17 tests currently pass under both `python -m unittest discover -s tests -v` (2.665s) and `python -m pytest -v` (4.22s).
   - README line 7 displays an out-of-date badge claiming `"Tests: 16/16 Passed (100%)"`, failing to account for the current 17 tests.
2. **Code Coverage Reality (pytest-cov):**
   - Total line coverage across `src/` and `benchmarks/` is **83%** (793 statements, 135 missed lines).
   - **`src/dataset.py` has 0% coverage** (25/25 statements unexecuted).
   - **`benchmarks/kfold_monte_carlo.py` has only 16% coverage** (73/87 statements unexecuted).
   - Uncovered branches exist in every core source file, especially around corrupted buffer handling, error raises, schema variants, and boundary conditions.
3. **Severe Empirical & Benchmarking Discrepancies:**
   - **Performance Inversion in Raw Benchmark Data:** In `results/Table1_10Fold_30Split_Performance_Benchmark.csv`, DNA-V2X has an empirical total latency of **12.86 ± 7.62 μs** and energy of **32.146 ± 19.059 μJ/pkt**, making it **slower and more energy-intensive** than standard AES-128-GCM (5.46 ± 16.22 μs, 13.662 μJ/pkt) and ChaCha20-Poly1305 (6.04 ± 9.17 μs, 15.103 μJ/pkt). In contrast, README Table 1 claims DNA-V2X achieves **0.918 ± 0.084 μs** (over 3× faster than AES/ChaCha). Figure 2 hardcodes a third divergent set of numbers (1.82 μs enc / 1.45 μs dec / 8.18 μJ).
   - **Fabricated Figure Data:** `experiments/generate_publication_figures.py` (Figs 2, 3, 4, 5, 6) ignores raw benchmark results in `results/dna_v2x_master_results.json` and renders hardcoded values or artificial Gaussian random distributions (`np.random.normal(3.27, 0.08, 300)`).
   - **10,000× Linear Scaling Artifact:** In `experiments/run_massive_scale_classification.py`, the "50,000,000 packet stream" was computed by running inference on only **5,000 samples** and multiplying confusion matrix counts by **10,000**. The "1,000,000 per class" evaluation ran on **2,000 samples** and multiplied by **500**.
   - **Bypassed Authentic VeReMi Dataset:** `experiments/run_veremi_benchmark.py` claims to validate on the public VeReMi vehicular reference dataset (Table 4), but completely ignores `AuthenticVeReMiParser` from `src/dataset.py` (which contains 150,000 authentic records) and generates synthetic Gaussian telemetry instead.
   - **Hardcoded Benchmark Metrics:** In `benchmarks/kfold_monte_carlo.py` (lines 160–166), Shannon entropy and security scores are hardcoded constants rather than dynamically measured values.
4. **Architectural & Security Flaws Uncovered:**
   - **Module-Level Global Memory Retention:** `src/dna_4mer_engine.py` caches up to 50,000 permutation tables in a global dictionary `_PERM_CACHE` that is never wiped by `purge_memory()`, defeating the claimed "zero-residual RAM purge" PFS guarantee.
   - **Fisher-Yates Modulo Bias:** Deriving permutation indices via `val % (i + 1)` with 16-bit integers introduces statistical modulo bias across 256 items without rejection sampling.
   - **One-Way Ratchet Replay State Desynchronization:** In `src/attack_classifier.py` lines 125–127, past ratchet states are re-instantiated using `state.master_seed`, but `master_seed` is evolved via a one-way SHA-256 ratchet, meaning historical permutations cannot be recovered from the advanced seed.
   - **Broken Telemetry Deserialization:** `deserialize_v2x_packet()` in `src/v2x_telemetry_schema.py` indiscriminately unpacks SPaT and DENM frames using BSM field offsets, corrupting signal timing and hazard alert parameters.
   - **Integer Overflow on Unbounded Coordinates:** `serialize_bsm()` lacks coordinate bounds clipping for latitude/longitude; passing extreme coordinates triggers `struct.error` signed 32-bit integer overflow.
   - **Phantom Kinematic Physics:** `MovingCarsSimulator.step_physics()` claims to implement the Intelligent Driver Model (IDM) but only applies uncorrelated uniform random acceleration noise without inter-vehicle car-following kinematics, and is never executed in existing tests.

---

## 2. Python Environment & Dependency Infrastructure

### 2.1 Runtime Environment
- **Operating System:** Windows 11 (build environment)
- **Python Version:** `Python 3.13.14` (`C:\Users\umert\AppData\Local\Microsoft\WindowsApps\PythonSoftwareFoundation.Python.3.13_qbz5n2kfra8p0\python.exe`)
- **Execution Shell:** PowerShell (Windows)

### 2.2 Dependency Inventory & Specifications
The repository defines dependencies in `requirements.txt`:
```txt
# DNA-V2X: Dependencies
numpy>=1.24.0
scipy>=1.10.0
scikit-learn>=1.2.0
matplotlib>=3.7.0
seaborn>=0.12.0
cryptography>=41.0.0
pytest>=7.3.0
```

Installed packages verified in the runtime environment:
- `numpy`: Installed (active)
- `scipy`: 1.17.1
- `scikit-learn`: 1.6.0
- `matplotlib`: Installed (active)
- `seaborn`: 0.13.2
- `cryptography`: Installed (active)
- `pytest`: 9.1.1
- `pytest-cov`: 7.1.0
- `psutil`: Installed (active)

### 2.3 Runner Execution Protocols
- **Primary Unittest Runner:**
  ```powershell
  python -m unittest discover -s tests -v
  ```
  Result: 17/17 tests pass in 2.665 seconds.
- **Pytest Runner:**
  ```powershell
  python -m pytest -v
  ```
  Result: 17/17 tests pass in 4.22 seconds.
  *Note:* Direct invocation `pytest -v` fails on this Windows environment because the Python Scripts directory is not in user `PATH`. All automated commands must use `python -m pytest`.
- **Coverage Profiling Runner:**
  ```powershell
  python -m pytest --cov=src --cov=benchmarks --cov-report=term-missing tests/
  ```
- **Console Encoding Quirk:**
  Running `python experiments/run_massive_scale_classification.py` under the default Windows console environment crashes with `UnicodeEncodeError: 'charmap' codec can't encode character '\u03bc' in position 27` at lines 196–197 because `μs` and `μJ` are printed directly to `cp1252` stdout. Fix: replace with ASCII `us` / `uJ` or enforce UTF-8 stdout.

---

## 3. Test Suite Inventory

The repository maintains tests exclusively under `tests/`.

### Table 3.1: Detailed Inventory of All Existing Tests

| File Path | Test Class | Test Method Name | Type | Target Module / Function | Status | Runtime | Description |
| :--- | :--- | :--- | :---: | :--- | :---: | :---: | :--- |
| `tests/test_dna_v2x.py` | `TestDNA4MerEngine` | `test_canonical_universe` | Unit | `ALL_256_4MERS`, `BASES` | Pass | <0.01s | Verifies universe contains exactly 256 4-mers of length 4 containing only A,C,G,T. |
| `tests/test_dna_v2x.py` | `TestDNA4MerEngine` | `test_permutation_bijection` | Unit | `DynamicPermutationState` | Pass | <0.01s | Verifies strict 1:1 bijection between 0–255 and 256 4-mers and invertible recovery. |
| `tests/test_dna_v2x.py` | `TestDNA4MerEngine` | `test_symmetric_encoding_decoding` | Unit | `DNA4MerEngine.encode_bytes`, `decode_strand` | Pass | <0.01s | Encodes 32-byte BSM payload into 128 nucleotides and decodes back with Bob. |
| `tests/test_dna_v2x.py` | `TestDNA4MerEngine` | `test_forward_ratchet_pfs` | Unit | `DynamicPermutationState.ratchet_forward` | Pass | <0.01s | Verifies ciphertexts differ across frames, Bob at frame 1 decodes, and frame 0 state fails. |
| `tests/test_dna_v2x.py` | `TestDNA4MerEngine` | `test_memory_purge` | Unit | `DynamicPermutationState.purge_memory` | Pass | <0.01s | Asserts `active_4mer_to_byte` is empty and `active_byte_to_4mer[0] == 'AAAA'`. |
| `tests/test_dna_v2x.py` | `TestDNA4MerEngine` | `test_shannon_entropy` | Unit | `calculate_shannon_entropy`, `calculate_base_frequencies` | Pass | <0.01s | Verifies entropy approaches 8.0 on uniform 256 bytes and base frequencies are 0.25. |
| `tests/test_dna_v2x.py` | `TestV2XSchemas` | `test_all_message_types_serialization` | Unit | `serialize_bsm`, `serialize_cam`, `serialize_spat`, `serialize_denm` | Pass | <0.01s | Checks serialization and CRC match for 4 message types. |
| `tests/test_dna_v2x.py` | `TestV2XSchemas` | `test_corrupted_crc_detection` | Unit | `deserialize_v2x_packet` | Pass | <0.01s | Flips 1 byte in BSM buffer and verifies `ValueError` is raised on CRC mismatch. |
| `tests/test_dna_v2x.py` | `TestV2XSchemas` | `test_lightweight_mac_verification` | Unit | `compute_lightweight_mac`, `verify_lightweight_mac` | Pass | <0.01s | Tests 4-byte constant-time truncated HMAC generation and verification. |
| `tests/test_dna_v2x.py` | `TestAttackSimulator` | `test_replay_attack_detection` | Integration | `AttackSimulator.test_replay_attack` | Pass | 0.05s | Simulates 50 replay attack trials with 3-frame delay; asserts 100% detection. |
| `tests/test_dna_v2x.py` | `TestAttackSimulator` | `test_mutation_attack_detection` | Integration | `AttackSimulator.test_mutation_tamper_attack` | Pass | 0.05s | Simulates 50 mutation trials with 1 base flip; asserts 100% detection. |
| `tests/test_dna_v2x.py` | `TestAttackSimulator` | `test_frequency_analysis_defense` | Integration | `AttackSimulator.test_frequency_analysis_attack` | Pass | 0.12s | Evaluates 1,000 constant-speed packets; asserts entropy > 7.8 bits and 100% detection. |
| `tests/test_dna_v2x.py` | `TestAttackSimulator` | `test_sybil_injection_detection` | Integration | `AttackSimulator.test_sybil_ghost_injection` | Pass | 0.06s | Simulates 50 fake key injections; asserts 100% detection. |
| `tests/test_dna_v2x.py` | `TestBaselinesAndProfiler` | `test_all_baselines` | Unit | `BaselineCiphers` | Pass | 0.02s | Tests round-trip encryption/decryption for DNA-V2X, AES-GCM, ChaCha20, ECDSA, Static DNA, Plaintext. |
| `tests/test_dna_v2x.py` | `TestBaselinesAndProfiler` | `test_energy_profiler` | Unit | `EnergyProfiler.profile_algorithm` | Pass | 0.01s | Runs 50 iterations with dummy lambdas; asserts throughput > 0. |
| `tests/test_attack_classifier.py` | `TestAttackClassifier` | `test_feature_extraction_dimensions` | Integration | `extract_features_vectorized` | Pass | 0.15s | Generates 100 packets and asserts feature tensor has shape `(100, 10)`. |
| `tests/test_attack_classifier.py` | `TestAttackClassifier` | `test_classifier_accuracy_on_all_classes` | Integration | `FastRuleAndMLClassifier` | Pass | 2.10s | Calibrates on 2,000 samples and tests 200 samples per class; asserts accuracy >= 95% per class. |

---

## 4. Code Coverage Analysis & Line-Level Mapping

A full coverage assessment was performed using `pytest-cov 7.1.0` on `Python 3.13.14`:

### Table 4.1: Module-by-Module Code Coverage Breakdown

| Target Module | Statements | Missing Statements | Code Coverage (%) | Uncovered Line Numbers | Root Cause for Missing Coverage |
| :--- | :---: | :---: | :---: | :--- | :--- |
| `benchmarks/__init__.py` | 3 | 0 | **100%** | None | Fully imported |
| `benchmarks/baseline_ciphers.py` | 54 | 0 | **100%** | None | All ciphers exercised in `test_all_baselines` |
| `benchmarks/kfold_monte_carlo.py` | 87 | 73 | **16%** | Lines 24–48, 55–206 | `generate_synthetic_telemetry_corpus` and `run_10fold_30split_benchmark` never invoked in `tests/` |
| `src/__init__.py` | 5 | 0 | **100%** | None | Fully imported |
| `src/attack_classifier.py` | 152 | 15 | **90%** | Lines 67–68, 112–113, 136–137, 157–160, 183, 188, 256–259 | Length corruption error branch, CRC exception fallback, desync window search exceptions, ML fallback branch |
| `src/attack_simulator.py` | 99 | 6 | **94%** | Lines 59–60, 100, 178, 193–201 | Successful breach branches (never hit in 100% detection simulations) and `run_all_attack_evaluations` |
| `src/dataset.py` | 25 | 25 | **0%** | Lines 1–38 | Module is never imported or tested anywhere in `tests/` |
| `src/dna_4mer_engine.py` | 86 | 4 | **95%** | Lines 127, 134, 145, 168 | Invalid strand length exception (`len % 4 != 0`), unrecognized 4-mer codon error, empty strand entropy and base frequencies |
| `src/energy_profiler.py` | 54 | 2 | **96%** | Lines 95, 101 | Entropy calculation with ciphertexts, `attack_rate_fn` callback execution |
| `src/moving_cars_simulation.py` | 143 | 8 | **94%** | Lines 82–92 | `step_physics(dt_sec)` method is never called in any test |
| `src/v2x_telemetry_schema.py` | 85 | 2 | **98%** | Lines 196, 230 | Packet length != 32 exception, MAC payload != 28 bytes exception |
| **TOTAL REPOSITORY** | **793** | **135** | **83%** | — | — |

---

## 5. Threat Model & Protocol Schema Test Coverage Mapping

### 5.1 Threat Model Coverage Audit

| Threat Category | Implemented Defense Mechanism | Unit Test in `tests/` | Integration / Stream Test | Coverage Assessment | Identified Audit Gaps |
| :--- | :--- | :---: | :---: | :---: | :--- |
| **Message Replay** | Ephemeral Ratchet Permutation Invalidation | `test_replay_attack_detection` | `test_classifier_accuracy_on_all_classes` | Partial | Only delays of 1 and 3 frames tested. Past ratchet search in `attack_classifier.py` uses advanced `state.master_seed`, meaning historical states cannot be recovered. Untested. |
| **Nucleotide Mutation / Tamper** | Bijective 4-mer Mapping + CRC-32 / HMAC | `test_mutation_attack_detection`, `test_corrupted_crc_detection` | `test_classifier_accuracy_on_all_classes` | Partial | Single and multi-base flips tested. Length truncations, non-multiple-of-4 strands, and non-canonical characters are never tested. |
| **Frequency Analysis / Cryptanalysis** | Dynamic Rolling Permutation Shuffling | `test_frequency_analysis_defense` | None | Partial | Evaluated only on 1,000 synthetic BSM packets. Pathological payloads (e.g. all-zeros, repeated 4-mers) are not tested in the main engine. |
| **Sybil Ghost Injection** | Ephemeral Dynamic Seed Authentication + Kinematic Anomaly Filter | `test_sybil_injection_detection` | `test_classifier_accuracy_on_all_classes` | Partial | Evaluated with arbitrary seeds. Extreme kinematic boundaries (accel > 15 m/s², speed > 160 km/h) are not systematically boundary-tested. |
| **MitM Frame Desynchronization** | Ratchet Window Verification | None | `test_classifier_accuracy_on_all_classes` | Weak | No direct unit test in `test_dna_v2x.py` verifying detection or handling of desynchronized frame states. |
| **Known-Plaintext & State Reconstruction** | CSPRNG Fisher-Yates Permutations | None | None | **Zero (Untested)** | Claimed in docstring of `attack_simulator.py:8`, but no method exists in `AttackSimulator`. |
| **Packet-Drop Desynchronization** | Ratchet Lookahead Window | None | None | **Zero (Untested)** | Claimed in docstring of `attack_simulator.py:9`, but no implementation or test exists. |

### 5.2 Protocol Schema Coverage Audit

| Schema Standard | Format Definition | Serialization Tested | Deserialization Tested | Field Verification Tested | Identified Audit Gaps & Vulnerabilities |
| :--- | :--- | :---: | :---: | :---: | :--- |
| **SAE J2735 BSM** | 28B payload + 4B CRC | Yes (`test_all_message_types_serialization`) | Yes | Yes (speed, accel, safety bitmask) | No boundary clipping for latitude/longitude in `serialize_bsm()` (overflows signed 32-bit int). No NaN/Inf validation. |
| **ETSI EN 302 637-2 CAM** | 28B payload + 4B CRC | Yes | Yes (partial) | No | Deserializer parses CAM using BSM schema; CAM-specific fields (hazard lights) are not verified. |
| **SAE J2735 SPaT** | 28B payload + 4B CRC | Yes | Partial | **Broken** | `deserialize_v2x_packet()` unpacks with BSM layout (`>BBI I H h H i i h H`), reading SPaT `phase_id` as speed, `countdown` as accel, and pad bytes as coordinates. |
| **ETSI EN 302 637-2 DENM** | 28B payload + 4B CRC | Yes | Partial | **Broken** | `deserialize_v2x_packet()` unpacks with BSM layout, reading DENM `cause_code` as speed and pad bytes as coordinates. |
| **ETSI CPM** | Defined constant `MSG_TYPE_CPM = 0x05` | **No** | **No** | **No** | Constant defined in `v2x_telemetry_schema.py:21`, but no `serialize_cpm` or deserialization exists. |
| **Lightweight Truncated MAC** | 4B HMAC-SHA256 | Yes (`test_lightweight_mac_verification`) | N/A | Yes | Constant-time check tested; invalid payload length raises are untested; 32-bit tag collision bound ($2^{16}$) not documented or bounded. |

---

## 6. Empirical Flaws, Benchmarking Soundness & Data Integrity Issues

### 6.1 Severe Inversion Between Measured CSV Results and Publication Claims
Inspection of `results/Table1_10Fold_30Split_Performance_Benchmark.csv` (the actual output of the 300-run benchmark) reveals:

```csv
Algorithm,Enc Latency (us),Dec Latency (us),Total Latency (us),Throughput (pkts/s),Throughput (MB/s),Energy (uJ/pkt),Shannon Entropy (bits),Attack Mitigation (%)
DNA-V2X (Proposed 4-Mer MTD),3.54 ± 2.13,9.32 ± 5.71,12.86 ± 7.62,"109,384",3.34,32.146 ± 19.059,7.96,100.0%
ChaCha20-Poly1305 (Stream AEAD),2.88 ± 1.93,3.16 ± 8.36,6.04 ± 9.17,"262,481",8.01,15.103 ± 22.920,7.98,98.5%
AES-128-GCM (NIST Standard),2.43 ± 2.67,3.03 ± 15.77,5.46 ± 16.22,"346,180",10.56,13.662 ± 40.562,7.98,98.5%
Static DNA Substitution,3.38 ± 1.87,8.20 ± 29.99,11.58 ± 30.10,"135,652",4.14,28.948 ± 75.243,6.12,35.0%
IEEE 1609.2 ECDSA (Vehicular PKI),60.36 ± 39.66,145.63 ± 105.15,205.98 ± 137.20,"6,895",0.21,514.961 ± 342.990,7.99,95.0%
Plaintext (Zero-Security),0.20 ± 0.33,0.19 ± 0.44,0.39 ± 0.57,"3,874,982",118.26,0.986 ± 1.414,5.20,0.0%
```

#### Comparison of the Three Conflicting Datasets:
1. **Measured Raw Data in CSV:**
   - DNA-V2X Total Latency: **12.86 ± 7.62 μs**
   - AES-128-GCM Total Latency: **5.46 ± 16.22 μs** (AES is **2.35× FASTER** than DNA-V2X!)
   - ChaCha20-Poly1305 Total Latency: **6.04 ± 9.17 μs** (ChaCha20 is **2.13× FASTER** than DNA-V2X!)
   - DNA-V2X Energy: **32.146 μJ/pkt** vs AES **13.662 μJ/pkt** (DNA-V2X consumes **2.35× MORE ENERGY** than AES!)
2. **README.md Table 1 Claims:**
   - DNA-V2X: Total **0.918 ± 0.084 μs**, Energy **2.296 ± 0.210 μJ/pkt**
   - ChaCha20: Total **2.193 ± 0.179 μs**, Energy **5.483 ± 0.448 μJ/pkt**
   - AES-128-GCM: Total **2.906 ± 0.241 μs**, Energy **7.265 ± 0.603 μJ/pkt**
   *(Claims DNA-V2X is over 3× faster and uses 3× less energy than AES-128-GCM!)*
3. **Figure 2 (`generate_publication_figures.py` lines 110–112):**
   - Enc Latency: `[1.82, 3.45, 4.12, 1.25, 420.0]`
   - Dec Latency: `[1.45, 3.10, 3.85, 1.10, 890.0]`
   - Energy: `[8.18, 16.38, 19.92, 5.88, 3275.0]`
   *(Completely fabricated hardcoded numbers, matching neither the CSV nor the README!)*

### 6.2 Data Fabrication in Publication Figures (Figs 2–6, 9–10)
- In `experiments/generate_publication_figures.py`:
  - `fig2_latency_and_energy()` receives `master_results` but does not use it; hardcodes all values (lines 110–112).
  - `fig3_shannon_entropy()` hardcodes entropies `[5.20, 6.12, 7.98, 7.98, 7.96]` (line 150).
  - `fig4_throughput_comparison()` hardcodes throughputs `[305810, 425530, 152670, 125470, 763]` (line 178).
  - `fig5_attack_mitigation_matrix()` hardcodes a 6×5 array (lines 215–222).
  - `fig6_kfold_stability()` synthesizes fake data using `np.random.normal(3.27, 0.08, 300)` etc. (lines 247–250) rather than extracting the 300 actual recorded runs from `dna_v2x_master_results.json`.
- In `experiments/generate_classification_figures.py`:
  - `plot_fig9_throughput_latency()` generates synthetic curves with random jitter `throughput * (1.0 + np.random.uniform(-0.02, 0.02, ...))` (lines 139–140).
  - `plot_fig10_warfare_timeline()` plots synthetic sine waves and hardcodes `mitigation_rate = np.ones_like(time_steps_sec) * 100.0` (line 202).

### 6.3 10,000× Linear Scaling Artifact in "50M Stream"
In `experiments/run_massive_scale_classification.py`:
- In Phase 1 (lines 54–68), `slice_size = 2000` is evaluated, and the confusion matrix row is scaled by `1_000_000 / len(preds) = 500`.
- In Phase 2 (lines 85–104):
  ```python
  s_w, r_w, t_w, sp_w, pt_w, y_w = sim_warfare.generate_streaming_batch(5000, attack_ratio=attack_ratio)
  ...
  scale_50m = total_stream_packets / float(len(y_w))  # 50,000,000 / 5,000 = 10,000.0
  for i in range(NUM_CLASSES):
      scaled_row = np.round(raw_sample_cm[i, :] * scale_50m).astype(np.int64)
  ```
  Only 5,000 packets were simulated; the results were multiplied by 10,000 to manufacture 50,000,000 packets.
- Line 75 hardcodes `"classification_rate_pkts_sec": 1_250_000`.

### 6.4 Public VeReMi Benchmark Evaluated on Purely Synthetic Generator
- `README.md` Table 4 claims: `"Public Benchmark Validation (VeReMi Vehicular Reference Misbehavior Dataset) ... Evaluated across 50,000 packets"`.
- However, `experiments/run_veremi_benchmark.py:27` defines `generate_veremi_benchmark_dataset()` which creates synthetic packets with random kinematics.
- `src/dataset.py` contains `AuthenticVeReMiParser`, which loads 150,000 real records from `Neuro-VeReMi/results/authentic_veremi_data.npz`, but `run_veremi_benchmark.py` never imports or calls it.

### 6.5 Hardcoded Metrics in 10-Fold Benchmark Loop
In `benchmarks/kfold_monte_carlo.py` (lines 160–166):
```python
metrics_map = {
    "DNA-V2X (Proposed 4-Mer MTD)": (m_dna, 7.96, 100.0),
    "ChaCha20-Poly1305 (Stream AEAD)": (m_chacha, 7.98, 98.5),
    "AES-128-GCM (NIST Standard)": (m_aes, 7.98, 98.5),
    "Static DNA Substitution": (m_static, 6.12, 35.0),
    "IEEE 1609.2 ECDSA (Vehicular PKI)": (m_ecdsa, 7.99, 95.0),
    "Plaintext (Zero-Security)": (m_plain, 5.20, 0.0)
}
```
The entropy values (7.96, 7.98, 6.12, etc.) and security percentages (100.0, 98.5, 35.0, etc.) are hardcoded constants injected directly into the data collector on every fold.

---

## 7. Architectural Vulnerabilities & Code Anomalies Uncovered

### 7.1 Global Cache Memory Leak Contradicting PFS Purge
- **Location:** `src/dna_4mer_engine.py:26`, `50–54`, `80–82`, `94–101`
- **Issue:** `_PERM_CACHE` is a module-level global dictionary storing `(cached_byte_to_4mer, cached_4mer_to_byte)` keyed by `(master_seed, frame_counter, session_id)`.
- When `purge_memory()` is called on a `DynamicPermutationState` instance, it sets `self.active_byte_to_4mer = ["AAAA"] * 256` and clears `self.active_4mer_to_byte`.
- **However, `_PERM_CACHE` retains up to 50,000 past permutation tables in process memory.** Any post-compromise memory dump can immediately extract all session tables and keys.

### 7.2 Modulo Bias in Fisher-Yates Permutation Derivation
- **Location:** `src/dna_4mer_engine.py:70–74`
- **Issue:**
  ```python
  for i in range(255, 0, -1):
      offset = (255 - i) * 2
      val = struct.unpack(">H", keystream[offset : offset + 2])[0]
      j = val % (i + 1)
      indices[i], indices[j] = indices[j], indices[i]
  ```
  `val` is a 16-bit integer ($0 \le val < 65536$).
  For any $(i + 1)$ that does not divide $65536$ evenly, taking `val % (i + 1)` yields non-uniform probabilities for remaining items (e.g. for $i+1 = 255$, $65536 \pmod{255} = 1$, giving residue 0 higher probability than others). Rejection sampling is required for true cryptographic uniformity.

### 7.3 One-Way Ratchet Breaks Past State Replay Search
- **Location:** `src/attack_classifier.py:125–127`
- **Issue:**
  ```python
  chk_state = DynamicPermutationState(state.master_seed, state.session_id)
  chk_state.frame_counter = state.frame_counter - delay
  chk_state._generate_epoch_permutation()
  ```
  `state.master_seed` is evolved via `ratchet_forward()` using a one-way SHA-256 hash:
  `self.master_seed = hashlib.sha256(self.master_seed + b":RATCHET:FORWARD").digest()[:16]`.
  Once the state ratchets forward, `state.master_seed` is the NEW seed. Creating `DynamicPermutationState` with `state.master_seed` and subtracting `delay` from `frame_counter` does **not** reproduce the permutation of past frames because the seed itself changed!
  Historical states cannot be recovered from future seeds under a one-way ratchet.

### 7.4 Telemetry Deserialization Blindness (SPaT / DENM)
- **Location:** `src/v2x_telemetry_schema.py:205–221`
- **Issue:** `deserialize_v2x_packet()` always unpacks `payload` with `">BBI I H h H i i h H"`.
  When given a SPaT packet (packed as `">BBI I H H 12x H"` with `phase_id` and `countdown_sec`), it parses `phase_id` as `speed_kmh / 100`, `countdown_sec` as `accel_mps2 / 100`, and pad bytes as latitude/longitude.
  The deserializer fails to condition unpacking on `msg_type`.

### 7.5 Unbounded Coordinates Trigger Signed 32-Bit Overflow
- **Location:** `src/v2x_telemetry_schema.py:70–71`, `74–87`
- **Issue:**
  ```python
  lat_raw = int(latitude * 1e7)
  lon_raw = int(longitude * 1e7)
  ```
  Packed with format `'i'` (signed 32-bit integer, max $2,147,483,647$).
  If `latitude > 214.7` or `longitude > 214.7` (or anomalous sensor input), `struct.pack` raises `struct.error: 'i' format requires -2147483648 <= number <= 2147483647`. Boundary clipping to valid geographic bounds ($[-90.0, 90.0]$ and $[-180.0, 180.0]$) is missing.

### 7.6 Missing Real Car-Following Physics in IDM Simulation
- **Location:** `src/moving_cars_simulation.py:80–93`
- **Issue:** The docstring states: `"Updates kinematic positions and speeds according to Intelligent Driver Model (IDM)."`.
  However, the code does not implement IDM equations ($a \cdot [1 - (v/v_0)^\delta - (s^*(v, \Delta v)/s)^2]$). It simply adds uniform noise to acceleration: `v.accel_mps2 += float(self.rng.uniform(-0.2, 0.2))`.
  Vehicles have no awareness of the vehicle ahead and cannot crash or decelerate in response to traffic waves. Furthermore, `step_physics` is never called in any test.

---

## 8. Actionable Test Expansion & Remediation Blueprint

To address all identified audit gaps and ensure 100% test coverage with verifiable regression defenses, the test suite must be expanded with the following specific test modules:

### 8.1 Proposed Test Suite Architecture

```
tests/
├── test_attack_classifier.py           # Existing (enhanced with edge cases)
├── test_dna_v2x.py                     # Existing (enhanced with schema & purge checks)
├── test_audit_cryptographic_poc.py     # NEW: PoC regression tests for crypto & memory flaws
├── test_audit_schemas_and_bounds.py    # NEW: PoC regression tests for SPaT/DENM and boundary overflows
├── test_audit_dataset_and_veremi.py    # NEW: Tests for AuthenticVeReMiParser & dataset splits
└── test_audit_kinematics_and_sim.py    # NEW: Tests for IDM physics, step_physics, and vehicle mobility
```

### 8.2 Detailed Test Specifications for Expansion

#### Test Suite 1: `test_audit_cryptographic_poc.py`
1. **`test_poc_memory_purge_clears_global_cache`**:
   - Create a `DynamicPermutationState`, encode a payload, call `purge_memory()`.
   - Assert `_PERM_CACHE` no longer holds the table for this session/counter.
2. **`test_poc_fisher_yates_uniformity_and_modulo_bias`**:
   - Verify rejection sampling or unbiased keystream unpacking across $10,000$ iterations.
   - Assert chi-square goodness-of-fit $p > 0.01$ for codon position distribution.
3. **`test_dna_strand_invalid_length_exception`**:
   - Pass strands of length 125, 126, 127 into `decode_strand()`. Assert `ValueError` raised.
4. **`test_dna_strand_unrecognized_codon_exception`**:
   - Pass strand with invalid 4-mer codon (e.g. `'ZZZZ'`) into `decode_strand()`. Assert `ValueError` raised.
5. **`test_shannon_entropy_empty_and_short_strands`**:
   - Verify `calculate_shannon_entropy("")` and `calculate_shannon_entropy("ACG")` return `0.0`.
6. **`test_base_frequencies_empty_strand`**:
   - Verify `calculate_base_frequencies("")` returns `{"A": 0.25, "C": 0.25, "G": 0.25, "T": 0.25}`.

#### Test Suite 2: `test_audit_schemas_and_bounds.py`
1. **`test_spat_and_denm_polymorphic_deserialization`**:
   - Serialize SPaT with `phase_id=3`, `countdown_sec=14.5`. Deserialize and assert `pkt.msg_type == MSG_TYPE_SPAT`, `pkt.event_code == 3`, and countdown is preserved.
   - Serialize DENM with `cause_code=1`. Deserialize and assert `pkt.msg_type == MSG_TYPE_DENM` and cause code is preserved.
2. **`test_coordinate_boundary_clipping_and_overflow_protection`**:
   - Pass `latitude=1000.0`, `longitude=-500.0` to `serialize_bsm()`. Assert coordinates are clipped to `[-90.0, 90.0]` and `[-180.0, 180.0]` without `struct.error`.
3. **`test_packet_length_validation_rejects_malformed_buffers`**:
   - Pass 31-byte and 33-byte buffers to `deserialize_v2x_packet()`. Assert `ValueError` raised.
4. **`test_mac_payload_length_validation`**:
   - Pass 27-byte and 29-byte buffers to `compute_lightweight_mac()`. Assert `ValueError` raised.
5. **`test_nan_and_inf_kinematics_handling`**:
   - Pass `speed_kmh=float('nan')` and `accel_mps2=float('inf')`. Assert safe fallback to default values without crash.

#### Test Suite 3: `test_audit_dataset_and_veremi.py`
1. **`test_authentic_veremi_parser_cache_loading`**:
   - Initialize `AuthenticVeReMiParser()`. Load dataset and assert $X.shape[0] == 150000$, $X.shape[1] == 7$, and $y$ contains both benign and malicious labels.
2. **`test_grouped_kfold_splits_integrity`**:
   - Run `get_grouped_kfold_splits(X[:1000], y[:1000], groups[:1000], n_splits=5)`.
   - Assert 5 distinct train/test splits where vehicle groups do not leak across folds.
3. **`test_missing_veremi_cache_file_not_found`**:
   - Instantiate parser with non-existent path. Assert `FileNotFoundError` is raised.

#### Test Suite 4: `test_audit_kinematics_and_sim.py`
1. **`test_step_physics_execution_and_position_update`**:
   - Initialize `MovingCarsSimulator(num_vehicles=10)`. Call `step_physics(dt_sec=0.1)`.
   - Assert all vehicle positions advance and timestamp increments by 100 ms.
2. **`test_highway_corridor_periodic_boundary_wrap`**:
   - Set vehicle position near 10,000 m. Call `step_physics()`. Assert position wraps around corridor correctly.
3. **`test_idm_car_following_behavior`**:
   - Verify follower decelerates when leader is slower and headway decreases below safety threshold.

---

## 9. Test Survey Verdict & Next Steps

| Dimension | Initial Score | Target Score After Remediation | Required Actions |
| :--- | :---: | :---: | :--- |
| **Test Pass Rate** | 100% (17/17) | 100% (~35/35) | Keep all 17 passing while expanding with regression tests |
| **Code Coverage** | 83% | **>98%** | Cover `src/dataset.py` (currently 0%), `kfold_monte_carlo.py` (currently 16%), and all uncovered branches |
| **Protocol Schema Rigor** | 60% | 100% | Fix SPaT/DENM polymorphic deserialization and coordinate clipping |
| **Benchmark Soundness** | 30% | 100% | Reconcile CSV vs README vs figure discrepancies; remove hardcoded values; execute real VeReMi dataset |
| **Memory & Crypto Assurance** | 50% | 100% | Fix `_PERM_CACHE` leakage; fix Fisher-Yates modulo bias; fix one-way ratchet replay state handling |

This report provides the complete, authoritative empirical foundation for Phase 2 and Phase 3 lead reviewer remediation.
