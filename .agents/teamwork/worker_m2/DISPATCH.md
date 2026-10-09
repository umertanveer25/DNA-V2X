# DISPATCH — Worker M2 (Empirical Benchmarks & Experiment Pipeline Remediation)

## Milestone & Scope
Milestone 2: Empirical Benchmark & Experiment Pipeline Remediation
Files Exclusively Owned:
- `benchmarks/kfold_monte_carlo.py`
- `experiments/run_massive_scale_classification.py`
- `experiments/run_veremi_benchmark.py`
- `experiments/generate_publication_figures.py`
- `experiments/generate_classification_figures.py`
- `src/dataset.py`

## Authoritative Inputs & Survey Analyses
- `C:\Users\umert\.gemini\antigravity\scratch\DNA-V2X\.agents\teamwork\ORIGINAL_REQUEST.md`
- `C:\Users\umert\.gemini\antigravity\scratch\DNA-V2X\PROJECT.md`
- Survey Explorer 2 Report: `C:\Users\umert\.gemini\antigravity\scratch\DNA-V2X\.agents\teamwork\explorer_survey_2\survey_report.md`
- Survey Explorer 2 Handoff: `C:\Users\umert\.gemini\antigravity\scratch\DNA-V2X\.agents\teamwork\explorer_survey_2\handoff.md`

## Mandatory Integrity Warning
DO NOT CHEAT. All implementations must be genuine. DO NOT hardcode test results, create dummy/facade implementations, or circumvent the intended task. A forensic auditor will independently verify your work. Integrity violations WILL be detected and your work WILL be rejected.

## Tasks
1. `benchmarks/kfold_monte_carlo.py` (F-12):
   - Replace decorative single-sample K-fold loop with genuine cross-validation: train on `train_idx` and evaluate on full `test_idx` folds.
   - Remove hardcoded Shannon entropy (line 160) and hardcoded attack mitigation percentages (line 166). Compute authentic dynamic Shannon entropy from actual output ciphertext and compute authentic empirical attack mitigation rates.
2. `experiments/run_massive_scale_classification.py` (F-13, F-16):
   - Remove the artificial 10,000x multiplier (`scale_50m = 50_000_000 / 5,000`) and the 500x multiplier.
   - Execute an authentic, high-throughput streaming evaluation with actual feature extraction included in the timed loop.
   - Fix Windows console cp1252 crash: replace `\u03bc` with `us` and `uJ` (or safe UTF-8 encoding).
3. `experiments/run_veremi_benchmark.py` & `src/dataset.py` (F-14):
   - Wire `run_veremi_benchmark.py` directly to `AuthenticVeReMiParser` from `src/dataset.py` to evaluate against the real 150,000-record dataset at `Neuro-VeReMi/results/authentic_veremi_data.npz` (or fallback safely to verified authentic subset if memory requires, without generating toy fake strings).
   - Evaluate real precision, recall, F1, and throughput metrics.
4. `experiments/generate_publication_figures.py` & `experiments/generate_classification_figures.py` (F-15):
   - Eliminate all hardcoded latency arrays (Fig 2), entropy arrays (Fig 3), throughput arrays (Fig 4), and arbitrary penalty matrices (Fig 5).
   - Eliminate synthetic Gaussian random variable fabrication (`np.random.normal(3.27, 0.08, 300)` in Fig 6).
   - Bind figure generation scripts directly to the authentic master results JSON (`results/dna_v2x_master_results.json`) and raw benchmark CSV files.
   - Eliminate synthetic sine wave and artificial random jitter in Figs 9 and 10, plotting genuine streaming metrics.
5. Verification:
   - Run `python benchmarks/kfold_monte_carlo.py` (or quick verification mode).
   - Run `python experiments/run_veremi_benchmark.py`.
   - Run `python experiments/run_massive_scale_classification.py`.
   - Run figure generation scripts and verify output PNGs exist in `figures/`.
   - Run `python -m unittest discover tests/ -v` to ensure zero regressions across all 79 tests.
6. Deliver handoff report to `C:\Users\umert\.gemini\antigravity\scratch\DNA-V2X\.agents\teamwork\worker_m2\handoff.md`.
