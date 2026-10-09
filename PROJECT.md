# Project: DNA-V2X Repository Audit & Remediation

## Architecture
- **Core Security Engine (`src/`)**:
  - `dna_4mer_engine.py`: Dynamic 4-mer codon mapping, keystream derivation, Fisher-Yates permutation shuffle, forward-ratchet state evolution, memory sanitization.
  - `attack_classifier.py`: Feature extraction (`extract_features_vectorized`), vectorized rule masks, hybrid rule/ML classifier (`FastRuleAndMLClassifier`).
  - `v2x_telemetry_schema.py`: Binary serialization & deserialization for BSM, SPaT, and DENM frames, checksums, and CRC-32 MAC.
  - `moving_cars_simulation.py` & `attack_simulator.py`: Kinematic physics simulation (IDM), noise injection, threat injection (Replay, Mutation, Sybil, Frequency Probe).
  - `energy_profiler.py`: Execution profiling, timing, energy scaling, working set memory profiling.
  - `dataset.py`: `AuthenticVeReMiParser` for public VeReMi dataset (`Neuro-VeReMi/results/authentic_veremi_data.npz`).
- **Empirical Benchmarks & Experiments (`benchmarks/`, `experiments/`)**:
  - `benchmarks/baseline_ciphers.py`: Ciphers baseline harness (AES-128-GCM, ChaCha20-Poly1305, IEEE 1609.2 ECDSA).
  - `benchmarks/kfold_monte_carlo.py`: 10-Fold x 30 Monte Carlo cross-validation.
  - `experiments/run_massive_scale_classification.py`: Large-scale streaming packet classification pipeline.
  - `experiments/run_veremi_benchmark.py`: Public VeReMi dataset validation.
  - `experiments/generate_publication_figures.py` & `experiments/generate_classification_figures.py`: Publication figures generation (Figures 1–10).
- **Test Infrastructure (`tests/`)**:
  - Unit and integration tests, vulnerability regression tests, proof-of-concept validation harnesses.

## Code Layout
- `src/`: Core engines, schemas, classifiers, and simulators.
- `benchmarks/`: Cryptographic baseline implementations and Monte Carlo benchmark runners.
- `experiments/`: Classification scale benchmarks, VeReMi evaluators, publication figure scripts.
- `tests/`: Unit, integration, and regression test suites.
- `results/`: Raw benchmark CSVs and master JSON artifacts.

## Feature & Audit Vulnerability Inventory
| # | Feature / Vulnerability | Description | Milestone | Source |
|---|-------------------------|-------------|-----------|--------|
| F-01 | Fisher-Yates Modulo Bias | 16-bit modulo arithmetic causes +0.388% bias for k=255; needs rejection sampling or uniform slicing | M1 | Survey E1 |
| F-02 | Memory Sanitization Failure | `purge_memory()` leaves plaintext `master_seed` intact in instance memory | M1 | Survey E1 |
| F-03 | PFS Memory Cache Leak | Global `_PERM_CACHE` retains up to 50,000 session keys/tables (~1.65 GB RAM) surviving purge | M1 | Survey E1, E2, E3 |
| F-04 | Replay Attack Misclassification | Irreversible one-way SHA-256 ratchet desyncs historical session state, classifying replay as Sybil | M1 | Survey E1 |
| F-05 | Length Truncation Misclassification | Truncated packets (<128 chars) claim entropy < 2.0 and classify as Frequency Probe instead of Mutation | M1 | Survey E1 |
| F-06 | SPaT/DENM Deserialization Corruption | `deserialize_v2x_packet()` unpacks all packets using BSM struct format, corrupting signal/hazard fields | M1 | Survey E1, E3 |
| F-07 | Sensor NaN Silent Corruption | `min(250.0, nan)` converts NaN speed to 250.0 km/h; missing bounds clipping on elevation/heading crashes pack | M1 | Survey E1 |
| F-08 | Dead ML Classifier Inference Code | `FastRuleAndMLClassifier` boolean masks partition 100% of samples; `HistGradientBoostingClassifier` is 100% dead code | M1 | Survey E1 |
| F-09 | IDM Simulation Lack of Physics & Timestamp Stagnation | Missing IDM car-following equations; batch packets share identical timestamp | M1 | Survey E1 |
| F-10 | Energy Profiler Synthetic Formula | Profiler scales wall time by 2.5 W and function pointer size, rather than real profiling | M1 | Survey E1 |
| F-11 | Table 1 Latency Discrepancy & Overclaiming | README claims 0.918 us vs raw CSV 12.86 us (AES 2.82 us and ChaCha 3.44 us are 3x faster than DNA-V2X) | M2, M4, M5 | Survey E2, E3 |
| F-12 | Decorative K-Fold Cross Validation | `kfold_monte_carlo.py` splits indices but never uses `train_idx` and tests 1 sample; hardcoded entropy | M2, M4 | Survey E2, E3 |
| F-13 | 50M Packet 10,000x Extrapolation | `run_massive_scale_classification.py` tests 5,000 packets and multiplies counts by 10,000; omits feature extraction time | M2, M4 | Survey E2, E3 |
| F-14 | VeReMi Benchmark Synthetic Masquerade | `run_veremi_benchmark.py` bypasses `authentic_veremi_data.npz` and uses toy random packets | M2, M4 | Survey E2, E3 |
| F-15 | Publication Figures 1–10 Data Fabrication | Figs 2–5 hardcode arrays; Fig 6 uses `np.random.normal`; Figs 9–10 use synthetic jitter and sine waves | M2, M4 | Survey E2, E3 |
| F-16 | Windows Console Unicode Crash | Printing `\u03bc` (μs, μJ) crashes with `UnicodeEncodeError` in cp1252 consoles | M2 | Survey E3 |
| F-17 | Regression & POC Test Suite Expansion | Build extensive tests in `tests/` verifying all patched bugs and regression guards | M3 | Survey E1, E2, E3 |
| F-18 | End-to-End Benchmark Execution & Verification | Execute all benchmarks cleanly with authentic data, updating results artifacts and README | M4 | Survey E2, E3 |
| F-19 | Comprehensive 3rd Lead Peer Reviewer Audit Report | Write authoritative, publication-standard 3rd Lead Reviewer Report (R4) | M5 | Original Request |

## Milestones
| # | Name | Scope | Dependencies | Status |
|---|------|-------|-------------|--------|
| M1 | Core Cryptography, Schema & Numerical Remediation | Fix F-01 to F-10 in `src/` (Fisher-Yates bias, memory purge, cache leakage, ratchet history, SPaT/DENM schemas, NaN bounds, rule precedence, ML integration, IDM physics) | none | DONE |
| M2 | Empirical Benchmark & Experiment Pipeline Remediation | Fix F-11 to F-16 in `benchmarks/` and `experiments/` (genuine K-Fold, honest streaming scale, authentic VeReMi pipeline, binding figures to master JSON/CSV, cp1252 safe printing) | M1 | DONE |
| M3 | Test Suite Expansion & POC Regression Harness | Add comprehensive unit, integration, and regression test suites in `tests/` covering F-01 to F-16 (100% pass) | M1, M2 | DONE |
| M4 | End-to-End Benchmark Execution & Empirical Verification | Run all unit tests, Monte Carlo benchmarks, authentic VeReMi evaluation, update raw results artifacts and honest README | M1, M2, M3 | IN_PROGRESS |
| M5 | 3rd Lead Peer Reviewer Audit Report Delivery | Produce authoritative, publication-grade Lead Reviewer Audit Report covering Executive Verdict, Bug Taxonomy, Overclaiming Audit, Patch Summary, and Quality Scores | M1, M2, M3, M4 | PLANNED |

## Interface Contracts
### `src/dna_4mer_engine.py` ↔ Consumers
- `DynamicPermutationState(master_seed: bytes, session_id: bytes = b"")`:
  - `master_seed`: 16-32 bytes key material. Zeroed on `purge_memory()`.
  - `purge_memory()`: Zeroes `self.master_seed`, clears active lookup tables, clears entries associated with this session in `_PERM_CACHE`.
  - `_PERM_CACHE`: Thread-safe LRU or bounded cache with explicit eviction and memory wiping.
  - `_generate_epoch_permutation()`: Unbiased Fisher-Yates shuffle using rejection sampling or cryptographically uniform indices.
  - `get_historical_permutation(delay: int)`: Reconstructs or looks up valid historical permutation state for window $t - \text{delay}$.

### `src/v2x_telemetry_schema.py` ↔ Consumers
- `deserialize_v2x_packet(buffer: bytes) -> V2XTelemetryPacket`:
  - Dispatches deserialization by `msg_type` (BSM: 0x01, SPaT: 0x02, DENM: 0x03).
  - Validates coordinate, speed, acceleration, and elevation ranges; handles NaN/Inf safely without crashes or silent 250 km/h corruption.

### `src/attack_classifier.py` ↔ `src/dna_4mer_engine.py`
- `extract_features_vectorized`:
  - Accurately identifies replayed packets within ratchet window using historical state lookup.
  - Correctly marks length corruptions (<128 or %4 != 0) such that `mask_mutation` takes precedence over `mask_freq_probe`.
- `FastRuleAndMLClassifier`:
  - Hybrid decision arbitration: ambiguous or borderline rule intervals fall back to `HistGradientBoostingClassifier.predict()`.

### `src/dataset.py` ↔ `experiments/run_veremi_benchmark.py`
- `AuthenticVeReMiParser`:
  - Loads authentic 150,000-sample VeReMi dataset from `Neuro-VeReMi/results/authentic_veremi_data.npz`.
  - Feeds authentic feature vectors and ground-truth attack labels into classifier evaluation.
