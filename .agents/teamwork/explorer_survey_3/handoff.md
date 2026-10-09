# Handoff Report — Survey Explorer 3 (Tests & Infra)

**From:** Survey Explorer 3 (Survey Explorer Tests & Infra)  
**To:** Orchestrator (Lead Reviewer)  
**Date:** 2026-10-08  
**Report Artifact:** `C:\Users\umert\.gemini\antigravity\scratch\DNA-V2X\.agents\teamwork\explorer_survey_3\survey_report.md`

---

## 1. Observation

1. **Test Suite Inventory & Status:**
   - Command: `python -m unittest discover -s tests -v`
   - Result: 17 tests passed in 2.665s.
   - Command: `python -m pytest -v`
   - Result: 17 tests passed in 4.22s.
   - The test suite contains only two files:
     * `tests/test_dna_v2x.py` (248 lines): 15 tests across 4 classes (`TestDNA4MerEngine` [6], `TestV2XSchemas` [3], `TestAttackSimulator` [4], `TestBaselinesAndProfiler` [2]).
     * `tests/test_attack_classifier.py` (52 lines): 2 tests in 1 class (`TestAttackClassifier` [2]).
   - In `README.md:7`, the badge claims `[![Tests: 16/16 Passed](https://img.shields.io/badge/Tests-16%2F16%20Passed%20(100%25)-brightgreen.svg)](tests/)`, which is out of sync with the actual 17 tests.

2. **Code Coverage Analysis:**
   - Command: `python -m pytest --cov=src --cov=benchmarks --cov-report=term-missing tests/`
   - Overall coverage: **83%** (793 statements total, 135 missed).
   - `src/dataset.py`: **0% coverage** (25/25 statements missed, lines 1–38).
   - `benchmarks/kfold_monte_carlo.py`: **16% coverage** (73/87 statements missed, lines 24–48, 55–206).
   - `src/attack_classifier.py`: 90% (15 missed: lines 67–68, 112–113, 136–137, 157–160, 183, 188, 256–259).
   - `src/moving_cars_simulation.py`: 94% (8 missed: lines 82–92, `step_physics` never executed).
   - `src/dna_4mer_engine.py`: 95% (4 missed: lines 127, 134, 145, 168).
   - `src/energy_profiler.py`: 96% (2 missed: lines 95, 101).
   - `src/v2x_telemetry_schema.py`: 98% (2 missed: lines 196, 230).

3. **Performance Inversion in Raw Benchmark Data:**
   - Inspected `results/Table1_10Fold_30Split_Performance_Benchmark.csv`:
     ```csv
     Algorithm,Enc Latency (us),Dec Latency (us),Total Latency (us),Throughput (pkts/s),Throughput (MB/s),Energy (uJ/pkt),Shannon Entropy (bits),Attack Mitigation (%)
     DNA-V2X (Proposed 4-Mer MTD),3.54 ± 2.13,9.32 ± 5.71,12.86 ± 7.62,"109,384",3.34,32.146 ± 19.059,7.96,100.0%
     ChaCha20-Poly1305 (Stream AEAD),2.88 ± 1.93,3.16 ± 8.36,6.04 ± 9.17,"262,481",8.01,15.103 ± 22.920,7.98,98.5%
     AES-128-GCM (NIST Standard),2.43 ± 2.67,3.03 ± 15.77,5.46 ± 16.22,"346,180",10.56,13.662 ± 40.562,7.98,98.5%
     ```
     DNA-V2X measured total latency is 12.86 μs vs AES-128-GCM 5.46 μs (AES is 2.35× faster).
     DNA-V2X measured energy is 32.146 μJ/pkt vs AES-128-GCM 13.662 μJ/pkt (AES uses 57% less energy).
   - In `README.md:107–114`, Table 1 claims:
     DNA-V2X Total Latency: 0.918 ± 0.084 μs, Energy: 2.296 ± 0.210 μJ/pkt.
     ChaCha20-Poly1305: Total Latency: 2.193 ± 0.179 μs, Energy: 5.483 ± 0.448 μJ/pkt.
     AES-128-GCM: Total Latency: 2.906 ± 0.241 μs, Energy: 7.265 ± 0.603 μJ/pkt.
   - In `experiments/generate_publication_figures.py:110–112`, Figure 2 hardcodes:
     `enc_lat = [1.82, 3.45, 4.12, 1.25, 420.0]`
     `dec_lat = [1.45, 3.10, 3.85, 1.10, 890.0]`
     `energy_uj = [8.18, 16.38, 19.92, 5.88, 3275.0]`

4. **Synthetic Fabrication in Figures:**
   - In `experiments/generate_publication_figures.py`:
     * Lines 247–250: `dna_lat = np.random.normal(3.27, 0.08, 300)` — Figure 6 is drawn from synthetic Gaussian random variables, completely ignoring the 300 runs saved in `results/dna_v2x_master_results.json`.
     * Line 150: `entropies = [5.20, 6.12, 7.98, 7.98, 7.96]` — hardcoded array.
     * Line 178: `pkts_sec = [305810, 425530, 152670, 125470, 763]` — hardcoded array.
     * Lines 215–222: Hardcoded 6×5 mitigation matrix array.
   - In `experiments/generate_classification_figures.py`:
     * Lines 138–140: Synthetic random jitter `tp_curve = throughput * (1.0 + np.random.uniform(-0.02, 0.02, len(timeline_m)))`.
     * Line 202: `mitigation_rate = np.ones_like(time_steps_sec) * 100.0` plotted over arbitrary sine waves.

5. **Linear Extrapolation Artifact in "50M Stream":**
   - In `experiments/run_massive_scale_classification.py:85–104`:
     * Generates only `batch_size = 5000` samples: `s_w, r_w, t_w, sp_w, pt_w, y_w = sim_warfare.generate_streaming_batch(5000, ...)`.
     * Multiplies confusion matrix by `scale_50m = 50_000_000 / 5,000 = 10,000.0`.
     * In Phase 1 (lines 54–68), runs only `slice_size = 2000` samples and multiplies by 500.
     * Line 75: `"classification_rate_pkts_sec": 1_250_000` is hardcoded.

6. **Authentic VeReMi Dataset Bypassed:**
   - In `src/dataset.py:5–7`, `CACHE_FILE` points to `../../Neuro-VeReMi/results/authentic_veremi_data.npz`.
   - Verified that `Neuro-VeReMi/results/authentic_veremi_data.npz` exists and contains 150,000 authentic records (`X.shape == (150000, 7)`).
   - In `experiments/run_veremi_benchmark.py:27`, it calls `generate_veremi_benchmark_dataset()` which synthesizes random Gaussian telemetry instead of loading authentic data.

7. **Cryptographic & Memory Vulnerabilities:**
   - `src/dna_4mer_engine.py:26, 50, 80`: `_PERM_CACHE = {}` is a module-level global dictionary storing up to 50,000 permutation tables. `purge_memory()` (lines 94–101) overwrites the instance fields but does NOT clear `_PERM_CACHE`, leaking all session keys in process memory.
   - `src/dna_4mer_engine.py:70–74`: Derives Fisher-Yates index via `j = val % (i + 1)` using 16-bit integers without rejection sampling, introducing statistical modulo bias.
   - `src/attack_classifier.py:125–127`: Recreates past ratchet states via `chk_state = DynamicPermutationState(state.master_seed, state.session_id)` with `frame_counter - delay`. Because `state.master_seed` is updated via a one-way hash ratchet (`SHA-256`), historical permutations cannot be reconstructed from advanced seeds.
   - `src/v2x_telemetry_schema.py:205–221`: `deserialize_v2x_packet()` unpacks all packets using BSM struct format `">BBI I H h H i i h H"`. SPaT and DENM packets have completely different layouts, resulting in corrupt fields upon deserialization.
   - `src/v2x_telemetry_schema.py:70–71`: `lat_raw = int(latitude * 1e7)` lacks bounds clipping, causing signed 32-bit integer overflow in `struct.pack` for coordinates outside valid geographic ranges.

8. **Runtime Encoding Crash:**
   - Command: `python experiments/run_massive_scale_classification.py`
   - Verbatim Error: `UnicodeEncodeError: 'charmap' codec can't encode character '\u03bc' in position 27: character maps to <undefined>` at lines 196–197 when attempting to print `μs` and `μJ` to standard Windows PowerShell console (`cp1252`).

---

## 2. Logic Chain

1. **Step 1 (Test Suite Sufficiency):**
   - Observation: Only 17 tests exist in 2 files; coverage is 83%, with `src/dataset.py` at 0% and `benchmarks/kfold_monte_carlo.py` at 16%. Uncovered lines include critical error handlers (invalid strand lengths, unrecognized codons, malformed buffers, boundary clipping, and ML model fallback).
   - Deduction: The current test suite is inadequate for proving safety, robustness, or non-regression under adversarial vehicular conditions.

2. **Step 2 (Benchmark Soundness & Overclaiming):**
   - Observation: Measured data in `Table1_10Fold_30Split_Performance_Benchmark.csv` establishes that DNA-V2X (12.86 μs) is more than 2× slower and consumes more energy than AES-128-GCM (5.46 μs) and ChaCha20-Poly1305 (6.04 μs). Yet `README.md` Table 1 claims DNA-V2X is 0.918 μs and over 3× faster than AES/ChaCha, and Figure 2 hardcodes a third set of numbers (1.82 μs).
   - Deduction: The README and Figure 2 exhibit empirical discrepancy, selective reporting, or ungrounded overclaiming that contradicts the actual measured outputs of the repository's own benchmark suite.

3. **Step 3 (Figure Fabrication):**
   - Observation: Figure 6 generates data using `np.random.normal(3.27, 0.08, 300)`; Figures 3, 4, 5 hardcode constant arrays; Figures 9 and 10 generate artificial sine waves and linear extrapolations.
   - Deduction: The publication figures do not faithfully depict empirical experimental executions, violating publication-standard empirical integrity.

4. **Step 4 (Synthetic Scaling & VeReMi Bypass):**
   - Observation: `run_massive_scale_classification.py` only tests 5,000 samples and multiplies by 10,000x; `run_veremi_benchmark.py` generates synthetic Gaussian data instead of using the authentic 150,000-record VeReMi dataset in `src/dataset.py`.
   - Deduction: Claims of evaluating "50 Million Streaming Packets" and validating on the "Public VeReMi Benchmark" are simulated approximations that bypass authentic empirical datasets.

5. **Step 5 (Architectural & Security Vulnerabilities):**
   - Observation: `_PERM_CACHE` leaks up to 50,000 permutation tables across memory purges; one-way hash ratchet prevents past state recovery; SPaT/DENM deserialization corrupts fields; missing latitude/longitude boundary checks crash `struct.pack`.
   - Deduction: The codebase contains latent cryptographic leaks, protocol deserialization bugs, and input validation vulnerabilities that must be patched and guarded by regression tests.

---

## 3. Caveats

- **No Caveats.** Every source file, test file, benchmark script, figure generator, results CSV, and JSON artifact was directly inspected and executed on the local runtime environment. All findings are backed by line-numbered code references and command outputs.

---

## 4. Conclusion

The DNA-V2X test infrastructure is currently functional (17/17 tests passing) but severely under-covers critical modules (overall coverage 83%, `src/dataset.py` at 0%, `kfold_monte_carlo.py` at 16%). 

Crucially, the repository exhibits:
1. Significant empirical discrepancies between raw benchmark CSVs and README/figure claims (where DNA-V2X is actually slower than AES-128-GCM and ChaCha20-Poly1305 in raw benchmarks).
2. Data fabrication in publication figure scripts (hardcoded arrays and synthetic normal distributions instead of loading `results/dna_v2x_master_results.json`).
3. Linear extrapolation artifacts (5K packets scaled to 50M) and public VeReMi dataset bypass.
4. Concrete cryptographic and schema bugs (`_PERM_CACHE` memory leakage, one-way ratchet replay state desynchronization, SPaT/DENM deserialization layout mismatch, and coordinate overflow).

A comprehensive expansion of the test suite (adding targeted unit, integration, and proof-of-concept tests across 4 new test files) and verified code patches are strictly required to achieve publication-grade audit rigor.

---

## 5. Verification Method

To independently verify the observations and findings in this handoff report, execute the following commands from `C:\Users\umert\.gemini\antigravity\scratch\DNA-V2X`:

1. **Verify Existing Tests:**
   ```powershell
   python -m unittest discover -s tests -v
   python -m pytest -v
   ```
   *Expected Result:* 17 tests pass.

2. **Verify Code Coverage & Missing Lines:**
   ```powershell
   python -m pytest --cov=src --cov=benchmarks --cov-report=term-missing tests/
   ```
   *Expected Result:* 83% overall coverage; `src/dataset.py` at 0%; `benchmarks/kfold_monte_carlo.py` at 16%.

3. **Verify CSV vs README Performance Inversion:**
   - Inspect `results/Table1_10Fold_30Split_Performance_Benchmark.csv` lines 2–4.
   - Compare with `README.md` lines 107–114.
   - Note DNA-V2X Total Latency (12.86 μs) vs AES-128-GCM (5.46 μs).

4. **Verify Figure Fabrication:**
   - Inspect `experiments/generate_publication_figures.py` lines 110–112 (Fig 2 hardcoded latencies) and lines 247–250 (Fig 6 `np.random.normal`).

5. **Verify VeReMi Bypass & Synthetic Generator:**
   - Inspect `experiments/run_veremi_benchmark.py` line 27 (`generate_veremi_benchmark_dataset`).
   - Run `python -c "import src.dataset; p = src.dataset.AuthenticVeReMiParser(); X, y, g, a = p.load_dataset(); print(X.shape)"` to confirm authentic data exists and is unused.

6. **Verify Memory Leak in `_PERM_CACHE`:**
   - Run:
     ```powershell
     python -c "from src.dna_4mer_engine import DynamicPermutationState, _PERM_CACHE; s = DynamicPermutationState(b'TEST_SEED_123456'); s.purge_memory(); print('Cache count:', len(_PERM_CACHE))"
     ```
   *Expected Result:* Prints `Cache count: 1`, confirming the global cache retained the permutation table after `purge_memory()`.

7. **Verify Windows Console Unicode Crash:**
   ```powershell
   python experiments/run_massive_scale_classification.py
   ```
   *Expected Result:* Crashes at lines 196–197 with `UnicodeEncodeError: 'charmap' codec can't encode character '\u03bc'`.
