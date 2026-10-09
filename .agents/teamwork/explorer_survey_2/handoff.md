# Handoff Report: Survey Explorer 2 (Experiments & Benchmarks Audit)

**Date:** 2026-10-08T18:43:30Z  
**Author:** Survey Explorer 2  
**Recipient:** Orchestrator (`8e427327-1383-435e-84f9-65791f49405e`)  
**Scope:** Comprehensive Audit of Experiment Scripts, Benchmarks, Data Artifacts, Publication Figures, and Scientific Rigor in DNA-V2X.  
**Report File:** `C:\Users\umert\.gemini\antigravity\scratch\DNA-V2X\.agents\teamwork\explorer_survey_2\survey_report.md`  

---

## 1. Observation

Direct, verbatim findings with file paths, line numbers, and empirical test commands:

1. **Table 1 Latency Discrepancy & Fabrication:**
   - In `README.md` (lines 108–114), Table 1 reports:
     - DNA-V2X: Encode `0.404 ± 0.038` $\mu\text{s}$, Decode `0.514 ± 0.046` $\mu\text{s}$, Total `0.918 ± 0.084` $\mu\text{s}$, Throughput `1,945,525` pkts/s, Energy `2.296 ± 0.210` $\mu\text{J}$.
     - AES-128-GCM: Total `2.906 ± 0.241` $\mu\text{s}$, Throughput `688,231` pkts/s.
     - ChaCha20-Poly1305: Total `2.193 ± 0.179` $\mu\text{s}$, Throughput `911,988` pkts/s.
   - In `results/Table1_10Fold_30Split_Performance_Benchmark.csv` (lines 2–4):
     - DNA-V2X: Enc `3.54 ± 2.13` $\mu\text{s}$, Dec `9.32 ± 5.71` $\mu\text{s}$, Total `12.86 ± 7.62` $\mu\text{s}$, Throughput `109,384` pkts/s, Energy `32.146 ± 19.059` $\mu\text{J}$.
     - AES-128-GCM: Total `5.46 ± 16.22` $\mu\text{s}$, Throughput `346,180` pkts/s.
     - ChaCha20-Poly1305: Total `6.04 ± 9.17` $\mu\text{s}$, Throughput `262,481` pkts/s.
   - Direct execution via Python shell:
     - AES-128-GCM: `enc=1.64 us, dec=1.18 us, total=2.82 us`
     - ChaCha20-Poly1305: `enc=1.88 us, dec=1.56 us, total=3.44 us`
     - DNA-V2X: `enc=4.19 us, dec=6.22 us, total=10.41 us`
     - Result: AES-128-GCM is $3.7\times$ faster than DNA-V2X; ChaCha20 is $3.0\times$ faster. In the actual CSV, DNA-V2X is over $2\times$ slower than both.

2. **K-Fold Cross-Validation is Decorative:**
   - In `benchmarks/kfold_monte_carlo.py` (lines 94–98):
     ```python
     kf = KFold(n_splits=n_splits_kfold, shuffle=True, random_state=42 + split_idx)
     for fold_idx, (train_idx, test_idx) in enumerate(kf.split(shuffled)):
         run_idx += 1
         test_sample = corpus[shuffled[test_idx[0]]]
     ```
     `train_idx` is completely unused. Only `test_idx[0]` (1 single packet) is evaluated. No model is trained. In lines 160–166, Shannon entropy and attack mitigation scores are hardcoded constants across all 300 runs.

3. **50,000,000 Packet Simulation Scaled from 5,000 Samples ($10,000\times$ Scaling):**
   - In `experiments/run_massive_scale_classification.py` (lines 85, 98–101):
     ```python
     s_w, r_w, t_w, sp_w, pt_w, y_w = sim_warfare.generate_streaming_batch(5000, attack_ratio=attack_ratio)
     ...
     scale_50m = total_stream_packets / float(len(y_w)) # 50,000,000 / 5,000 = 10,000.0
     for i in range(NUM_CLASSES):
         scaled_row = np.round(raw_sample_cm[i, :] * scale_50m).astype(np.int64)
         conf_matrix_50m[i, :] = scaled_row
     ```
   - Only 5,000 packets were tested. In lines 88–92, `time.perf_counter_ns()` measures only `classify_batch_fast(f_w)` (numpy boolean mask operations), completely omitting feature extraction (`extract_features_vectorized`), which takes $50\text{--}100\ \mu\text{s}$ per packet.

4. **VeReMi Benchmark Bypassed Real Data for Synthetic Mocks:**
   - `src/dataset.py` contains `AuthenticVeReMiParser` for `Neuro-VeReMi/results/authentic_veremi_data.npz` (150,000 samples). This file is never imported anywhere.
   - In `experiments/run_veremi_benchmark.py` (lines 27–143), `generate_veremi_benchmark_dataset` creates toy synthetic packets in Python (e.g. Type 8 is `"ACGT" * 32`; Type 1 has hardcoded `accel=22.0, speed=190.0`), tailor-made to match `attack_classifier.py` rules.

5. **Publication Figures Audit (Figures 1–10):**
   - In `experiments/generate_publication_figures.py`:
     - Lines 110–112 (Fig 2): Hardcoded latencies `[1.82, 3.45, 4.12, 1.25, 420.0]` and energies `[8.18, 16.38, 19.92, 5.88, 3275.0]`. Ignores master results JSON.
     - Line 150 (Fig 3): Hardcoded `entropies = [5.20, 6.12, 7.98, 7.98, 7.96]`.
     - Line 178 (Fig 4): Hardcoded throughputs `[305810, 425530, 152670, 125470, 763]`.
     - Lines 216–222 (Fig 5): Hardcoded mitigation matrix with $99.0\%$ arbitrary penalty on AES/ChaCha.
     - Lines 247–250 (Fig 6): Synthetically fabricated normal distributions via `np.random.normal(3.27, 0.08, 300)`.
   - In `experiments/generate_classification_figures.py`:
     - Lines 139–141 (Fig 9): Synthesized curve using `throughput * (1.0 + np.random.uniform(-0.02, 0.02, len(timeline_m)))`.
     - Lines 172–204 (Fig 10): Pure synthetic sine waves and hardcoded $100\%$ line.

6. **Memory Leak in PFS Engine:**
   - In `src/dna_4mer_engine.py` (lines 26, 50, 80–82): Global dictionary `_PERM_CACHE` caches up to 50,000 permutation tables and session states. `purge_memory()` does not wipe `_PERM_CACHE`.

---

## 2. Logic Chain

1. **Premise:** Scientific claims in publication documents must be verifiable from reproducible benchmark execution and supported by raw artifacts without contradiction.
2. **Step 1 (Table 1):** We compared `README.md` Table 1 against `results/Table1_10Fold_30Split_Performance_Benchmark.csv` and ran the benchmark live. In `Table1...csv`, DNA-V2X total latency is $12.86\ \mu\text{s}$ (slower than AES's $5.46\ \mu\text{s}$ and ChaCha's $6.04\ \mu\text{s}$). Live execution confirms AES ($2.82\ \mu\text{s}$) and ChaCha ($3.44\ \mu\text{s}$) are $3\times$ faster than DNA-V2X ($10.41\ \mu\text{s}$). Therefore, `README.md` Table 1's claim of $0.918\ \mu\text{s}$ latency and $1,945,525\text{ pkts/sec}$ is fabricated.
3. **Step 2 (Table 2 & Table 3 Contradiction):** In `README.md` Table 2, trial counts are reported as 2.85M–3.15M with 0 breaches allowed (100% mitigation). However, Table 3 reports 20,000 False Negatives for Mutation and 20,000 False Negatives for Sybil. A False Negative in threat classification is an undetected attack (breach). Thus, Table 2 directly contradicts Table 3.
4. **Step 3 (Simulation Scale):** In `experiments/run_massive_scale_classification.py`, line 85 calls `generate_streaming_batch(5000)`. Line 98 scales this by $50,000,000 / 5,000 = 10,000$. Hence, the claimed 50M streaming simulation is a $10,000\times$ extrapolation of 5,000 packets.
5. **Step 4 (VeReMi Evaluation):** `experiments/run_veremi_benchmark.py` does not load `authentic_veremi_data.npz` and instead constructs synthetic packets with hand-coded kinematic anomalies. Therefore, Table 4 is not an empirical evaluation of the public VeReMi dataset.
6. **Step 5 (Publication Figures):** `generate_publication_figures.py` and `generate_classification_figures.py` contain explicit hardcoded arrays and `np.random.normal()` calls. Therefore, the figures are graphically distorted and do not reflect the raw data artifacts.

---

## 3. Caveats

1. **Python vs C Implementation:** The slower execution of DNA-V2X relative to AES-128-GCM and ChaCha20 is largely due to Python dictionary lookups and string slicing compared to C-accelerated OpenSSL bindings with AES-NI. A C/Rust implementation of 4-mer mapping might run faster, but within the current repository codebase, DNA-V2X is empirically slower.
2. **Intended Role of DNA-V2X:** The bio-inspired dynamic 4-mer mapping concept remains mathematically viable as a lightweight Moving Target Defense against cryptanalysis. The flaws identified here pertain strictly to empirical reporting, benchmarking methodology, data integrity, and figure fidelity.
3. **No Caveats on Artifact Discrepancies:** The discrepancies between README, CSV files, and Python figure generation scripts are factual, reproducible, and verifiable.

---

## 4. Conclusion

1. **Integrity Assessment:** The empirical foundation of the repository contains substantial overclaiming, data inflation ($10,000\times$ in Table 3, $1,872\times$ in Table 2), synthetic determinism artifacts in figure generation (Figs 2, 4, 6, 9, 10), and a bypassed public dataset (VeReMi).
2. **Cryptographic & Architectural Assessment:** The comparison against IEEE 1609.2 ECDSA is an architectural category error (symmetric vs asymmetric). Furthermore, `_PERM_CACHE` leaks up to 50,000 session states in RAM, violating Perfect Forward Secrecy.
3. **Required Actions:**
   - Patch `_PERM_CACHE` memory leak in `src/dna_4mer_engine.py`.
   - Update `experiments/generate_publication_figures.py` to bind directly to `results/dna_v2x_master_results.json` without hardcoding or synthetic random distributions.
   - Wire `experiments/run_veremi_benchmark.py` to authentic VeReMi data via `src/dataset.py`.
   - Align `README.md` tables and narrative with honest empirical ground truth.

---

## 5. Verification Method

To independently verify all findings:

1. **Verify Live Cipher Latencies:**
   ```bash
   python -c "from benchmarks.baseline_ciphers import BaselineCiphers; from src.energy_profiler import EnergyProfiler; c = BaselineCiphers(); p = EnergyProfiler(); data = b'0'*32; print('DNA-V2X:', p.profile_algorithm('DNA', c.encrypt_dna_v2x, c.decrypt_dna_v2x, data, iterations=100)); print('AES-GCM:', p.profile_algorithm('AES', c.encrypt_aes_gcm, c.decrypt_aes_gcm, data, iterations=100)); print('ChaCha20:', p.profile_algorithm('ChaCha', c.encrypt_chacha20, c.decrypt_chacha20, data, iterations=100))"
   ```
   *Expected:* AES-128-GCM and ChaCha20 execute in $<3.5\ \mu\text{s}$; DNA-V2X executes in $\approx 10\ \mu\text{s}$.

2. **Verify Table 1 CSV Discrepancy:**
   Inspect `results/Table1_10Fold_30Split_Performance_Benchmark.csv` (Row 2).
   *Expected:* Confirms Total Latency is $12.86 \pm 7.62\ \mu\text{s}$ and Throughput is $109,384\text{ pkts/sec}$, contradicting README Table 1 ($0.918\ \mu\text{s}$ and $1,945,525\text{ pkts/sec}$).

3. **Verify 50M Simulation 5,000-sample Scaling:**
   Inspect `experiments/run_massive_scale_classification.py` at line 85 (`generate_streaming_batch(5000)`) and line 98 (`scale_50m = total_stream_packets / float(len(y_w))`).
   *Expected:* Confirms exact multiplier of 10,000.

4. **Verify Figure 6 Synthetic Gaussian Distribution:**
   Inspect `experiments/generate_publication_figures.py` at lines 247–250.
   *Expected:* Confirms `np.random.normal(3.27, 0.08, 300)` is used instead of reading `dna_v2x_master_results.json`.

5. **Verify Memory Leak in `_PERM_CACHE`:**
   Inspect `src/dna_4mer_engine.py` at lines 26, 50, 80, and 94.
   *Expected:* Confirms `_PERM_CACHE` is never cleared by `purge_memory()`.
