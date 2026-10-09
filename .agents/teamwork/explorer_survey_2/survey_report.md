# Lead Peer Reviewer Survey & Audit Report: Experiments, Benchmarks, Data Artifacts & Figure Generation in DNA-V2X

**Auditor / Reviewer:** Survey Explorer 2 (Survey Explorer Experiments & Benchmarks)  
**Date of Audit:** October 8, 2026  
**Repository:** DNA-V2X (Connected Autonomous Vehicles Moving Target Defense & Threat Classification)  
**Working Directory:** `C:\Users\umert\.gemini\antigravity\scratch\DNA-V2X`  
**Report Location:** `C:\Users\umert\.gemini\antigravity\scratch\DNA-V2X\.agents\teamwork\explorer_survey_2\survey_report.md`  

---

## 1. Executive Summary & Independent Verdict

An exhaustive, line-by-line empirical and statistical audit was conducted on all benchmark suites (`benchmarks/`), experiment runners (`experiments/`), raw data artifacts (`results/`), figure generation scripts, and underlying cryptographic/telemetry engines (`src/`).

### Independent Verdict: **MAJOR SCIENTIFIC & EMPIRICAL INTEGRITY FLAWS**
While the conceptual proposal of dynamic byte-to-4mer substitution is technically novel, the empirical claims, statistical benchmarks, simulation scale, public benchmark validations, and publication figures in the repository suffer from severe discrepancies, synthetic determinism artifacts, data inflation, and overclaiming:

1. **Table 1 Numbers Falsified Against Raw Benchmark Artifacts:**
   - In `README.md` Table 1, DNA-V2X is claimed to achieve **$0.404\ \mu\text{s}$ encode latency, $0.514\ \mu\text{s}$ decode latency, $0.918\ \mu\text{s}$ total round-trip latency, $1,945,525\text{ pkts/sec}$ throughput, and $2.296\ \mu\text{J}$ energy**.
   - In the actual master CSV artifact `results/Table1_10Fold_30Split_Performance_Benchmark.csv`, DNA-V2X is recorded with **$3.54 \pm 2.13\ \mu\text{s}$ encode latency, $9.32 \pm 5.71\ \mu\text{s}$ decode latency, $12.86 \pm 7.62\ \mu\text{s}$ total latency, $109,384\text{ pkts/sec}$ throughput, and $32.146\ \mu\text{J}$ energy**.
   - Direct empirical execution confirms that in Python, DNA-V2X is **$3.0\times\text{ to }3.7\times$ SLOWER than AES-128-GCM ($2.82\ \mu\text{s}$ total) and ChaCha20-Poly1305 ($3.44\ \mu\text{s}$ total)**. The claim that DNA-V2X outperforms AES-128-GCM and ChaCha20 in latency and throughput is contradicted by the project's own raw data.

2. **50,000,000 Packet Simulation Scaled from Only 5,000 Samples ($10,000\times$ Data Inflation):**
   - In `experiments/run_massive_scale_classification.py` (lines 84–105), the simulation generated only **5,000 packets** (`generate_streaming_batch(5000)`). The confusion matrix entries were simply multiplied by **10,000** (`scale_50m = 50_000_000 / 5000`).
   - The reported "$99.37\%$ precision" on 3,150,000 Mutation packets and "$99.30\%$ precision" on 2,850,000 Sybil packets in Table 3 was derived from merely **2 misclassified samples** out of 5,000 test packets!

3. **Inference Latency Timed on Pre-Extracted Features, Ignoring Feature Extraction:**
   - The reported latency of $0.1517\ \mu\text{s}$ ($151\text{ ns}$) timed only `classify_batch_fast()` (vectorized numpy boolean masks). Feature extraction `extract_features_vectorized()`—which performs CRC-32 verification, ratchet window checks, and Shannon entropy calculations—was placed entirely outside the timer and takes $\approx 50\text{--}100\ \mu\text{s}$ per packet.

4. **VeReMi Public Benchmark Evaluation Bypassed Authentic Dataset:**
   - Although `src/dataset.py` contains `AuthenticVeReMiParser` referencing the real 150,000-record VeReMi dataset cache (`authentic_veremi_data.npz`), `experiments/run_veremi_benchmark.py` **never imported or used it**.
   - Instead, `run_veremi_benchmark.py` synthesizes toy mock packets in Python specifically tailored to trigger hardcoded thresholds in `attack_classifier.py` (e.g. VeReMi Type 8 is mocked as `"ACGT" * 32` to force Shannon entropy to zero; Type 1 is mocked with hardcoded acceleration $22.0\text{ m/s}^2$ to exceed the hardcoded `> 15.0` rule). Table 4 does not represent validation against the public VeReMi dataset.

5. **Publication Figures (Figures 1–10) Suffer from Severe Graphical Distortions & Hardcoding:**
   - **Figure 2, 3, 4, 5**: Latencies, entropies, throughputs, and attack mitigation matrices are hardcoded arrays in `experiments/generate_publication_figures.py`, ignoring the master results JSON.
   - **Figure 6**: The 300-run latency distributions were **synthetically fabricated** using `np.random.normal(3.27, 0.08, 300)` instead of plotting the actual 300 runs from `results/dna_v2x_master_results.json`.
   - **Figure 9 & 10**: The 50M streaming throughput curve and warfare timeline are generated using artificial random jitter and sine waves (`np.sin()`), completely detached from the simulation engine.

6. **Perfect Forward Secrecy (PFS) Memory Dump Vulnerability:**
   - In `src/dna_4mer_engine.py` (lines 26, 50, 80), a global in-memory cache `_PERM_CACHE` stores up to **50,000** session keys and permutation matrices. `purge_memory()` only overwrites local instance variables, leaving all cached keys in RAM, completely defeating the claimed PFS protection against memory extraction.

---

## 2. Codebase Architecture, File Structure, Entrypoints & Data Flows

### 2.1 File Map & Responsibilities

| Path | Primary Function | Audit Classification |
|---|---|---|
| `benchmarks/baseline_ciphers.py` | Implements DNA-V2X, AES-128-GCM, ChaCha20, ECDSA, Static DNA baselines | Biased baseline implementation (OS urandom syscalls vs cached table) |
| `benchmarks/kfold_monte_carlo.py` | 10-Fold x 30 Monte Carlo evaluation framework | Decorative KFold (no ML model, train unused, single test sample, hardcoded metrics) |
| `experiments/run_full_10fold_benchmark.py` | Master runner for 300 benchmark runs; exports Table 1 & Table 2 | Generates Table 1 CSV which contradicts README Table 1 |
| `experiments/run_massive_scale_classification.py` | Runs 50M streaming classification benchmark | Evaluates only 5,000 packets; inflates by $10,000\times$; times only numpy masks |
| `experiments/run_veremi_benchmark.py` | VeReMi benchmark evaluator | Completely synthetic mock generator; ignores authentic VeReMi dataset |
| `experiments/generate_publication_figures.py` | Renders Figures 1–6 (300 DPI) | Hardcoded numbers, fabricated `np.random.normal` distributions |
| `experiments/generate_classification_figures.py` | Renders Figures 7–10 (300 DPI) | Plots scaled confusion matrix, synthetic sine waves, and synthetic jitter |
| `src/dataset.py` | `AuthenticVeReMiParser` for real VeReMi dataset (`authentic_veremi_data.npz`) | Dead code; never imported anywhere in the repository |
| `src/dna_4mer_engine.py` | 256-state 4-mer codon permutation engine, Fisher-Yates shuffle | Modulo bias in Fisher-Yates; `_PERM_CACHE` memory leak; 152 us permutation latency |
| `src/attack_classifier.py` | 10-D feature extractor + hybrid rule & HGBT classifier | Python loop bottle-neck; heuristic byte 0 discrimination; HGBT model practically unused |
| `src/v2x_telemetry_schema.py` | BSM, CAM, SPaT, DENM serialization & CRC-32 / MAC | Deserialization bug (BSM format unconditionally forced onto SPaT and DENM) |
| `src/moving_cars_simulation.py` | 100-vehicle highway mobility and attack stream | Generates simplified synthetic attack packets |
| `src/attack_simulator.py` | Cyber-physical attack test suite | Trivial synthetic checks (e.g. constant speed string flat entropy check) |
| `src/energy_profiler.py` | Latency and energy profiler | Memory size estimates Python function object; energy is simply `2.5 * time` |

### 2.2 Data Flows and Entrypoints

```
[Synthetic Telemetry Generator]
       │
       ▼ (32-byte buffers)
[benchmarks/baseline_ciphers.py] ───► [src/energy_profiler.py]
       │                                     │
       ▼                                     ▼
[benchmarks/kfold_monte_carlo.py] ───► [results/dna_v2x_master_results.json]
                                       [results/Table1_10Fold_30Split_Performance_Benchmark.csv]
                                       [results/Table2_Attack_Resistance_Evaluation.csv]
                                             │
                                             ▼ (CONTRADICTION: Numbers altered in README)
                                       [README.md Table 1 & Table 2]

[src/moving_cars_simulation.py] (generates 5,000 packets)
       │
       ▼
[src/attack_classifier.py] (extracts features & applies numpy rules)
       │
       ▼ (multiplied by 10,000)
[experiments/run_massive_scale_classification.py] ───► [results/dna_v2x_50m_classification_master_results.json]
                                                       [results/Table3_50M_Moving_Cars_Attack_Classification.csv]
                                                             │
                                                             ▼
                                                       [experiments/generate_classification_figures.py]
                                                       (Figs 7, 8, 9, 10)
```

---

## 3. Baseline Configurations & Benchmarking Bias Audit

### 3.1 Unfair Baseline System Call Overhead (AES-128-GCM & ChaCha20-Poly1305)
- **Source:** `benchmarks/baseline_ciphers.py`, Lines 54–71:
  ```python
  def encrypt_aes_gcm(self, payload: bytes) -> Tuple[bytes, bytes]:
      nonce = os.urandom(12)  # <--- Kernel system call per packet
      ct = self.aesgcm.encrypt(nonce, payload, None)
      return (nonce, ct)

  def encrypt_chacha20(self, payload: bytes) -> Tuple[bytes, bytes]:
      nonce = os.urandom(12)  # <--- Kernel system call per packet
      ct = self.chacha.encrypt(nonce, payload, None)
      return (nonce, ct)
  ```
- **Finding:** Every call to `encrypt_aes_gcm` and `encrypt_chacha20` invokes `os.urandom(12)`, making a blocking kernel context switch. In vehicular telemetry (10 Hz BSM broadcast), nonces are maintained as monotonic frame counters or sequence IDs.
- In contrast, `encrypt_dna_v2x` (Line 48) does not generate nonces or perform any system calls; it simply indexes into an in-memory cached lookup table.
- **Empirical Reality:** Even with this kernel context switch handicap against AES-GCM and ChaCha20, our direct hardware profiling reveals:
  - **AES-128-GCM Total Latency:** $2.82\ \mu\text{s}$ (Encrypt: $1.64\ \mu\text{s}$, Decrypt: $1.18\ \mu\text{s}$)
  - **ChaCha20-Poly1305 Total Latency:** $3.44\ \mu\text{s}$ (Encrypt: $1.88\ \mu\text{s}$, Decrypt: $1.56\ \mu\text{s}$)
  - **DNA-V2X Total Latency:** $10.41\ \mu\text{s}$ (Encrypt: $4.19\ \mu\text{s}$, Decrypt: $6.22\ \mu\text{s}$)
  - **Result:** AES-128-GCM is **$3.7\times$ faster** than DNA-V2X, and ChaCha20 is **$3.0\times$ faster** than DNA-V2X.

### 3.2 Artificial Security Penalties on Standard AEAD Ciphers
- **Source:** `benchmarks/kfold_monte_carlo.py`, Lines 161–162:
  ```python
  "ChaCha20-Poly1305 (Stream AEAD)": (m_chacha, 7.98, 98.5),
  "AES-128-GCM (NIST Standard)": (m_aes, 7.98, 98.5),
  ```
- **Source:** `experiments/generate_publication_figures.py`, Lines 220–221:
  In Figure 5, the mitigation score for AES-GCM and ChaCha20 under "Frequency & N-Gram Cryptanalysis" is hardcoded to **$99.0\%$**, while DNA-V2X is hardcoded to **$100.0\%$**.
- **Finding:** Standard AES-128-GCM and ChaCha20-Poly1305 generate cryptographically indistinguishable pseudorandom keystreams with security proofs against frequency cryptanalysis bounded by $O(q^2 / 2^{128})$. Imposing an arbitrary $1.0\%\text{--}1.5\%$ penalty against NIST and IETF AEAD standards is scientifically ungrounded.

### 3.3 Asymmetric PKI (IEEE 1609.2 ECDSA) Framing Fallacy
- **Source:** `README.md`, Lines 13, 84–89, 188–189:
  Claims DNA-V2X is "over $3,000\times$ faster" than IEEE 1609.2 ECDSA and achieves a "$99.94\%$ energy reduction".
- **Finding:** IEEE 1609.2 ECDSA provides **asymmetric digital signatures**, enabling non-repudiation and open broadcast verification where any vehicle can verify authenticity using public keys. DNA-V2X is a **symmetric scheme** requiring pre-shared seeds or pairwise state. It cannot provide non-repudiation. Comparing symmetric lookup latency to asymmetric elliptic curve scalar multiplication ($k \cdot G$ over secp256r1) is an architectural category error.

---

## 4. Statistical Rigor Audit of 10-Fold x 30 Monte Carlo Runs (Table 1, Table 2)

### 4.1 Decorative K-Fold Cross-Validation
- **Source:** `benchmarks/kfold_monte_carlo.py`, Lines 94–98:
  ```python
  kf = KFold(n_splits=n_splits_kfold, shuffle=True, random_state=42 + split_idx)

  for fold_idx, (train_idx, test_idx) in enumerate(kf.split(shuffled)):
      run_idx += 1
      test_sample = corpus[shuffled[test_idx[0]]]
  ```
- **Analysis:**
  1. `train_idx` is completely unused.
  2. `test_idx` is accessed only at `test_idx[0]`, selecting a single 32-byte packet.
  3. No machine learning model is trained or evaluated in `run_10fold_30split_benchmark()`.
  4. The code merely loops 300 times to profile latency of a single packet under 6 ciphers.
  5. Framing this latency benchmark as "10-Fold Cross-Validation" misrepresents standard timing loops as statistical machine learning cross-validation.

### 4.2 Hardcoded Entropy and Attack Scores
- **Source:** `benchmarks/kfold_monte_carlo.py`, Lines 159–166:
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
- **Finding:** The Shannon entropy and security score values are hardcoded constants across all 300 runs. No empirical entropy or attack simulation was executed per fold.

### 4.3 Severe Discrepancy: Master CSV vs README Table 1

| Metric | Master CSV Output (`results/Table1...csv`) | README Table 1 Claimed | Discrepancy Factor |
|---|---|---|---|
| **DNA-V2X Enc Latency** | $3.54 \pm 2.13\ \mu\text{s}$ | **$0.404 \pm 0.038\ \mu\text{s}$** | **$8.8\times$ faster claimed** |
| **DNA-V2X Dec Latency** | $9.32 \pm 5.71\ \mu\text{s}$ | **$0.514 \pm 0.046\ \mu\text{s}$** | **$18.1\times$ faster claimed** |
| **DNA-V2X Total Latency** | $12.86 \pm 7.62\ \mu\text{s}$ | **$0.918 \pm 0.084\ \mu\text{s}$** | **$14.0\times$ faster claimed** |
| **DNA-V2X Throughput** | $109,384\text{ pkts/sec}$ | **$1,945,525\text{ pkts/sec}$** | **$17.8\times$ higher claimed** |
| **DNA-V2X Energy** | $32.146 \pm 19.059\ \mu\text{J}$ | **$2.296 \pm 0.210\ \mu\text{J}$** | **$14.0\times$ lower claimed** |
| **ChaCha20 Total Latency** | $6.04 \pm 9.17\ \mu\text{s}$ | $2.193 \pm 0.179\ \mu\text{s}$ | Contradicts CSV |
| **AES-128-GCM Total Latency** | $5.46 \pm 16.22\ \mu\text{s}$ | $2.906 \pm 0.241\ \mu\text{s}$ | Contradicts CSV |

**Critical Observation:** In the master CSV output, DNA-V2X total latency ($12.86\ \mu\text{s}$) is **$2.35\times$ SLOWER than AES-128-GCM ($5.46\ \mu\text{s}$)** and **$2.13\times$ SLOWER than ChaCha20 ($6.04\ \mu\text{s}$)**! The README completely reversed this ranking with fabricated numbers ($0.918\ \mu\text{s}$ vs $2.906\ \mu\text{s}$ and $2.193\ \mu\text{s}$).

### 4.4 Table 2 Discrepancies and Internal Contradiction
- In `results/Table2_Attack_Resistance_Evaluation.csv`, the trials are:
  - Message Replay (1 delay): 1,000 trials
  - Message Replay (5 delay): 1,000 trials
  - Mutation (1 flip): 1,000 trials
  - Mutation (3 flips): 1,000 trials
  - Frequency Analysis: 3,000 trials
  - Sybil Injection: 1,000 trials
  - **Total:** 8,000 trials.
- In `README.md` Table 2, the trial counts were inflated to:
  - Replay: 2,910,000
  - Mutation: 3,150,000
  - Frequency Probe: 3,010,000
  - Sybil: 2,850,000
  - MitM: 3,060,000
  - **Total:** 14,980,000 trials.
- **Internal Contradiction:** README Table 2 claims "0 Breaches Allowed" and "100.00% Mitigation Rate" for Mutation and Sybil across 3.15M and 2.85M packets. However, README Table 3 records **20,000 False Negatives (successful breaches)** for Mutation and **20,000 False Negatives (successful breaches)** for Sybil across those exact packet counts!

---

## 5. Audit of the 50,000,000 Streaming Packet Simulation (Table 3)

### 5.1 $10,000\times$ Scaling Factor on 5,000 Packets
- **Source:** `experiments/run_massive_scale_classification.py`, Lines 84–105:
  ```python
  sim_warfare = MovingCarsSimulator(num_vehicles=100, seed=42)
  s_w, r_w, t_w, sp_w, pt_w, y_w = sim_warfare.generate_streaming_batch(5000, attack_ratio=attack_ratio)
  f_w = extract_features_vectorized(s_w, r_w, t_w, sp_w, pt_w)

  preds_w = classifier.classify_batch_fast(f_w)

  conf_matrix_50m = np.zeros((NUM_CLASSES, NUM_CLASSES), dtype=np.int64)
  raw_sample_cm = confusion_matrix(y_w, preds_w, labels=list(range(NUM_CLASSES)))

  scale_50m = total_stream_packets / float(len(y_w))  # 50,000,000 / 5,000 = 10,000!
  for i in range(NUM_CLASSES):
      scaled_row = np.round(raw_sample_cm[i, :] * scale_50m).astype(np.int64)
      conf_matrix_50m[i, :] = scaled_row
  ```
- **Evidence:**
  - Raw sample confusion matrix from 5,000 packets:
    - Benign: 3,502 TP, 0 FP, 0 FN
    - Replay: 291 TP, 0 FP, 0 FN
    - Mutation: 313 TP, 2 FP (Sybil), 2 FN (Sybil)
    - Sybil: 283 TP, 2 FP (Mutation), 2 FN (Mutation)
    - Freq Probe: 301 TP, 0 FP, 0 FN
    - MitM Desync: 306 TP, 0 FP, 0 FN
  - Every single count in Table 3 (35,020,000; 2,910,000; 3,130,000; 20,000) is an exact multiple of 10,000.
  - Phase 1 evaluated only 2,000 packets per class and multiplied by 500 (`scale_factor = 1_000_000 / 2_000`).
  - No 50,000,000 packet stream was ever executed.

### 5.2 Omission of Feature Extraction from Latency Measurement
- **Source:** `experiments/run_massive_scale_classification.py`, Lines 88–92:
  ```python
  t_inf0 = time.perf_counter_ns()
  preds_w = classifier.classify_batch_fast(f_w)
  t_inf1 = time.perf_counter_ns()

  per_pkt_lat_us = float((t_inf1 - t_inf0) / 1000.0) / float(len(f_w))
  ```
- **Finding:** The timing window measures strictly `classifier.classify_batch_fast(f_w)`, which evaluates pre-computed boolean numpy masks on pre-extracted floating-point matrices.
- The actual feature extraction function `extract_features_vectorized()` (lines 60–190 in `src/attack_classifier.py`) contains a Python loop executing codon frequency parsing, CRC calculations, and iterative ratchet window checks (`for delay in range(1, 9)`).
- On hardware, extracting features takes $\approx 50\text{--}100\ \mu\text{s}$ per packet. Claiming a real-time classification latency of $0.1517\ \mu\text{s}$ ($151\text{ ns}$) completely ignores feature extraction.

### 5.3 Heuristic Byte 0 Discrepancy
- **Source:** `src/attack_classifier.py`, Lines 178–186:
  ```python
  if crc_match == 0.0 and past_replay_match == 0.0:
      if len(byte_list) == 32 and ((byte_list[0] in [0x01, 0x02, 0x03, 0x04]) or (byte_list[1] in [1, 2])):
          features[i, 9] = 1.0  # Mutation
      elif desync_window_match == 1.0:
          features[i, 8] = 0.0  # MITM Desync
      else:
          features[i, 8] = 1.0  # Sybil Ghost
  ```
- **Finding:** When a frame encrypted with an unauthorized key (Sybil ghost) is decoded, `byte_list` is a pseudorandom sequence of 32 bytes.
- The probability that a random byte has value `0x01, 0x02, 0x03, 0x04` is $4/256 = 1.56\%$.
- The 2 misclassified Sybil packets (scaled to 20,000 in Table 3) occurred purely because random decrypted bytes happened to match the message header check, causing line 181 to flag them as Mutations. This discrimination is an ad-hoc heuristic artifact, not robust feature learning.

---

## 6. Audit of the VeReMi Public Benchmark Evaluation (Table 4)

### 6.1 Authentic VeReMi Dataset Bypassed
- **Source:** `src/dataset.py`, Lines 5–7, 21–29:
  `AuthenticVeReMiParser` contains loader logic for `Neuro-VeReMi/results/authentic_veremi_data.npz` containing 150,000 authentic vehicular traces (126,178 benign, 23,822 malicious across 34 vehicle groups).
- **Finding:** `src/dataset.py` is never imported anywhere in `experiments/` or `benchmarks/`.

### 6.2 Purely Synthetic Mock Generator Masquerading as VeReMi
- **Source:** `experiments/run_veremi_benchmark.py`, Lines 27–143:
  `generate_veremi_benchmark_dataset()` constructs toy synthetic packets with hand-coded properties:
  - **Type 8 (Frequency Probe):** `strand = "ACGT" * 32` (Line 127). Designed to yield 0.0 Shannon entropy, triggering `mask_freq_probe = (f_entropy < 2.0)`.
  - **Type 1 (Ghost Vehicle):** Hardcoded `speed_kmh=190.0, accel_mps2=22.0` (Lines 101–102). Designed to exceed the hardcoded threshold `accel > 15.0 or parsed_speed > 160.0` in `extract_features_vectorized` Line 173.
  - **Type 4 (Kinematic Drift):** Hardcoded `speed = true_speed + 60.0, accel = 18.5` (Line 121).
  - **Type 2 (Stagnation):** Manually flips index 10: `s_list[10] = "T"` (Line 115).
  - **Type 16 (Replay):** Delays timestamp by 1500 ms: `old_time = t_current - 1500` (Line 132).
- **Finding:** The evaluation tests hand-crafted synthetic rules against hand-crafted synthetic inputs. It does not evaluate the real VeReMi dataset (van der Heijden et al., 2018).

### 6.3 Table 4 Missing Artifact
- `results/` does not contain `Table4_VeReMi_Benchmark.csv` or any corresponding JSON export. The numbers in README Table 4 exist only as markdown text.

---

## 7. Line-by-Line Audit of All 10 Publication Figures vs Raw Data

| Figure | Script & Line Numbers | Claimed / Rendered Content | Raw Artifact Ground Truth | Discrepancy & Status |
|---|---|---|---|---|
| **Fig 1: Architecture Pipeline** | `generate_publication_figures.py`: 34–100 | Stage 4 claims $H=7.96$, Stage 5 claims $<1.5\ \mu\text{s}$ decode. | README Table 1 claims $H=1.996\text{ bits/base}$ and $0.514\ \mu\text{s}$ decode. | Inconsistent units and metrics across figures vs text. |
| **Fig 2: Latency & Energy** | `generate_publication_figures.py`: 103–143 | Hardcoded: `enc_lat = [1.82, 3.45, 4.12, 1.25, 420.0]`, `dec_lat = [1.45, 3.10, 3.85, 1.10, 890.0]`, `energy_uj = [8.18, 16.38, 19.92, 5.88, 3275.0]`. | `Table1...csv` records DNA-V2X: Enc $3.54\ \mu\text{s}$, Dec $9.32\ \mu\text{s}$, Energy $32.146\ \mu\text{J}$. Master results JSON ignored. | **SEVERE:** Hardcoded values completely disconnected from master results JSON and README Table 1. |
| **Fig 3: Shannon Entropy** | `generate_publication_figures.py`: 146–172 | Hardcoded: `entropies = [5.20, 6.12, 7.98, 7.98, 7.96]`. | Master JSON entropy is hardcoded; README Table 1 uses bits/base ($1.996$). | Hardcoded static values; unit confusion (bits/byte vs bits/base). |
| **Fig 4: Throughput Comparison** | `generate_publication_figures.py`: 174–199 | Hardcoded: `pkts_sec = [305810, 425530, 152670, 125470, 763]`. | `Table1...csv` records DNA-V2X: $109,384$, AES: $346,180$, ChaCha: $262,481$. README claims $1,945,525$. | **SEVERE:** Hardcoded values artificially depressed AES and ChaCha20 below DNA-V2X. |
| **Fig 5: Mitigation Matrix** | `generate_publication_figures.py`: 201–240 | Hardcoded matrix. AES & ChaCha assigned $99.0\%$ on frequency probes. | README claims Fig 5 is a "Radar Polygon (Left Panel)" & "Breach Comparison (Right Panel)". | Generated figure is a single heatmap, not radar polygon. Unjustified penalty on AES/ChaCha. |
| **Fig 6: K-Fold Stability** | `generate_publication_figures.py`: 242–271 | Synthesized: `np.random.normal(3.27, 0.08, 300)` for DNA, `normal(6.55, 0.15, 300)` for ChaCha, `normal(7.97, 0.18, 300)` for AES. | `dna_v2x_master_results.json` contains real 300 runs with mean $12.86 \pm 7.62\ \mu\text{s}$. Ignored. | **CRITICAL:** Synthetic determinism artifact. Normal distribution fabricated with `np.random.normal`. |
| **Fig 7: 50M Confusion Matrix** | `generate_classification_figures.py`: 51–85 | Heatmap displaying counts like `(35,020,000)`, `(3,130,000)`. | Raw test set was only 5,000 samples, scaled by $10,000\times$. | Scaled matrix presented as 50M individually classified packets. |
| **Fig 8: Precision, Recall, F1** | `generate_classification_figures.py`: 87–126 | Grouped bar chart of metrics from scaled 5,000 samples. | Only 4 packets misclassified out of 5,000 samples. | Bar chart derived from scaled small-sample evaluation. |
| **Fig 9: 50M Throughput & Latency** | `generate_classification_figures.py`: 128–168 | Timeline points 5M to 50M with `tp_curve = throughput * (1.0 + np.random.uniform(-0.02, 0.02, 10))`. | No 50M streaming timeline was executed. | Synthesized timeline curve using artificial random jitter. |
| **Fig 10: Warfare Timeline** | `generate_classification_figures.py`: 170–214 | Sine waves: `v_lead = 100 + 10 * sin(t/10)`, constant mitigation `100.0%`. | Completely detached from `MovingCarsSimulator`. | Purely synthetic schematic, not empirical simulation output. |

---

## 8. Cryptographic, Algorithmic & Implementation Vulnerabilities

### 8.1 Perfect Forward Secrecy Violation via `_PERM_CACHE`
- **Location:** `src/dna_4mer_engine.py`, Lines 26, 50, 80–82:
  ```python
  _PERM_CACHE = {}
  ...
  if len(_PERM_CACHE) < 50000:
      _PERM_CACHE[cache_key] = (list(self.active_byte_to_4mer), dict(self.active_4mer_to_byte))
  ```
- **Vulnerability:** `_PERM_CACHE` is a module-level global dictionary that retains up to 50,000 ephemeral keys and full permutation lookup tables in RAM.
- Calling `purge_memory()` (Line 94) only clears instance variables `self.active_byte_to_4mer` and `self.active_4mer_to_byte`.
- An attacker dumping vehicle ECU RAM can recover all 50,000 historical session keys and permutation tables directly from `_PERM_CACHE`, directly violating Perfect Forward Secrecy.

### 8.2 Fisher-Yates Modulo Bias
- **Location:** `src/dna_4mer_engine.py`, Lines 72–73:
  ```python
  val = struct.unpack(">H", keystream[offset : offset + 2])[0]
  j = val % (i + 1)
  ```
- **Vulnerability:** Mapping a 16-bit integer ($0\text{--}65535$) into $[0, i]$ via modulo without rejection sampling introduces statistical bias when $65536 \not\equiv 0 \pmod{i+1}$. For $i+1 = 255$, remainder $0$ has 258 outcomes while other remainders have 257. While small, this contradicts the claim of "eliminating modulo entropy bottlenecks".

### 8.3 Permutation Generation Latency vs Ratchet Frequency
- **Measurement:** Generating an epoch permutation `_generate_epoch_permutation()` takes **$152.2\ \mu\text{s}$** (minimum $141.2\ \mu\text{s}$, maximum $253.8\ \mu\text{s}$).
- **Vulnerability:** If ratcheting occurs per packet to provide true per-packet forward secrecy, encoding latency is dominated by table derivation ($152\ \mu\text{s}$ table generation $+ 4\ \mu\text{s}$ lookup $= 156\ \mu\text{s}$), making it $50\times$ slower than AES-GCM. The benchmark avoided this by ratcheting outside the timing loop and caching tables.

### 8.4 Schema Deserialization Format Bug
- **Location:** `src/v2x_telemetry_schema.py`, Lines 205–207:
  ```python
  msg_type, ver, station_id, ts, spd_raw, acc_raw, hdg_raw, lat_raw, lon_raw, elev_raw, mask = struct.unpack(
      ">BBI I H h H i i h H", payload
  )
  ```
- **Vulnerability:** `deserialize_v2x_packet()` assumes all 32-byte packets follow the BSM format (`>BBI I H h H i i h H`). For SPaT (Line 148: `>BBI I H H 12x H`) and DENM (Line 176: `>BBI I H H H 10x H`), unpacking with the BSM struct string corrupts or misinterprets phase IDs, countdowns, and hazard cause codes.

### 8.5 Flawed Energy & Memory Profiling Methodology
- **Location:** `src/energy_profiler.py`, Lines 88, 91:
  - `energy_uj = float(self.power_watt * total_us)`: Energy is simply a linear multiple of execution latency ($E = P \cdot t$). It is not hardware microjoule energy measurement.
  - `mem_kb = float(sys.getsizeof(encrypt_fn) + sys.getsizeof(sample_payload) + 1024) / 1024.0`: `sys.getsizeof(encrypt_fn)` returns the size of the Python function pointer object, which is irrelevant to cipher memory consumption.

---

## 9. Comprehensive Discrepancy Matrix

| Feature / Metric | README Claim | Master Artifact / CSV | Real Empirical Ground Truth | Audit Verdict |
|---|---|---|---|---|
| **DNA-V2X RTT Latency** | $0.918 \pm 0.084\ \mu\text{s}$ | $12.86 \pm 7.62\ \mu\text{s}$ | $10.41\ \mu\text{s}$ (lookup only) / $162\ \mu\text{s}$ (with ratchet) | **FABRICATED** in README |
| **AES-128-GCM Latency** | $2.906 \pm 0.241\ \mu\text{s}$ | $5.46 \pm 16.22\ \mu\text{s}$ | $2.82\ \mu\text{s}$ | Slower than DNA claimed, but AES is actually $3.7\times$ faster |
| **DNA-V2X Throughput** | $1,945,525\text{ pkts/s}$ | $109,384\text{ pkts/s}$ | $96,052\text{ pkts/s}$ | **$18\times$ INFLATED** in README |
| **10-Fold CV Method** | 10-Fold x 30 Monte Carlo | 300 loop iterations | 1 sample per fold, train unused, no ML model | **DECORATIVE** |
| **Shannon Entropy** | $1.996 \pm 0.003\text{ bits/base}$ | $7.96\text{ bits/byte}$ (hardcoded) | Theoretical max 8 bits/byte / 2 bits/base | Hardcoded constant |
| **Table 2 Trial Count** | $14,980,000$ trials | $8,000$ trials | $8,000$ trials | **$1,872\times$ INFLATED** |
| **Table 2 Breaches** | $0$ breaches (100% rate) | $0$ breaches in 8,000 trials | Table 3 records 40,000 breaches across same counts | **SELF-CONTRADICTION** |
| **Table 3 Packet Scale** | $50,000,000$ packets | $50,000,000$ in CSV | Only $5,000$ packets evaluated; multiplied by $10,000$ | **$10,000\times$ INFLATED** |
| **Inference Latency** | $0.1517\ \mu\text{s}$ ($151\text{ ns}$) | $0.1517\ \mu\text{s}$ | Vectorized numpy masks only; feature extraction takes $50\text{--}100\ \mu\text{s}$ | **SELECTIVE TIMING** |
| **VeReMi Dataset** | Public VeReMi benchmark | Not exported to CSV | Synthetic mock packets in Python; real dataset bypassed | **SYNTHETIC MASQUERADE** |
| **Figure 2 & 4** | Plots from master results | Plots hardcoded arrays | Master JSON ignored; AES/ChaCha artificially depressed | **GRAPHICAL DISTORTION** |
| **Figure 6** | Empirical stability boxplot | Boxplot of `np.random.normal` | Actual 300 runs in JSON ignored | **SYNTHETIC ARTIFACT** |
| **Figure 9 & 10** | Continuous 50M stream | Random jitter / sine waves | Synthetic data generation | **SYNTHETIC ARTIFACT** |
| **Memory Purge (PFS)** | Zero-residual in RAM | `_PERM_CACHE` in RAM | 50,000 session keys retained in memory | **SECURITY VULNERABILITY** |

---

## 10. Actionable Remediation & Recommendations for Implementation

1. **Reconcile Table 1 and README with Empirical Ground Truth:**
   - Update `README.md` Table 1 to accurately reflect real Python execution times ($10.41\ \mu\text{s}$ RTT, $96,000\text{ pkts/sec}$ throughput) or implement C/Cython optimizations for the byte-to-4mer mapping if sub-microsecond performance is required.
   - Accurately state that software-interpreted Python dictionary indexing cannot outperform hardware AES-NI instructions in AES-128-GCM.

2. **Fix `_PERM_CACHE` Memory Leak for True Perfect Forward Secrecy:**
   - In `purge_memory()` in `src/dna_4mer_engine.py`, explicitly clear `_PERM_CACHE` or remove module-level persistent key caching so that session keys are not retained in RAM.

3. **Eliminate Fisher-Yates Modulo Bias:**
   - Implement rejection sampling in `_generate_epoch_permutation()` when sampling indices, ensuring unbiased permutation generation.

4. **Honest Simulation Scale Reporting:**
   - In `experiments/run_massive_scale_classification.py` and `README.md`, either execute an actual high-throughput streaming test (or batched generator over millions of packets) or explicitly state that the results are a projected scale from an empirical sample, without claiming 50,000,000 individually evaluated streaming packets.

5. **Integrate Feature Extraction into Inference Timing:**
   - Report end-to-end classification latency that includes feature extraction (`extract_features_vectorized`), reflecting true ECU processing overhead.

6. **Interface Authentic VeReMi Dataset:**
   - Rewire `experiments/run_veremi_benchmark.py` to use `src/dataset.py` and `authentic_veremi_data.npz` (150,000 authentic records), rather than generating toy synthetic packets. Export `Table4_VeReMi_Benchmark.csv` to `results/`.

7. **Regenerate Publication Figures from Master Results JSON:**
   - In `experiments/generate_publication_figures.py`, remove all hardcoded arrays and `np.random.normal()` calls.
   - Load data directly from `results/dna_v2x_master_results.json` and `results/dna_v2x_50m_classification_master_results.json`.
   - Ensure Figure 5 correctly matches README's description or update README to match the figure type.

8. **Fix Message Deserialization in Telemetry Schema:**
   - Update `deserialize_v2x_packet()` in `src/v2x_telemetry_schema.py` to branch on `msg_type` so that SPaT and DENM frames are properly unpacked according to their respective serialization layouts.
