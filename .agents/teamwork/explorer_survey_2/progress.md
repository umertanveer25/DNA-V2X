# Progress — Survey Explorer 2

Last visited: 2026-10-08T18:41:00Z

## Status
- Initialized DISPATCH.md and BRIEFING.md
- Completed comprehensive audit of `benchmarks/`, `experiments/`, `src/`, `results/`, and `tests/`
- Uncovered major discrepancies:
  1. Table 1 numbers in README are fabricated vs Table 1 CSV (3.54 us / 9.32 us in CSV vs 0.404 us / 0.514 us in README). Actual empirical execution confirms DNA-V2X is 3.0x - 3.7x SLOWER than AES-128-GCM and ChaCha20-Poly1305.
  2. KFold cross-validation in `kfold_monte_carlo.py` is decorative (no model trained, train_idx unused, only 1 sample evaluated). Hardcoded entropy and security scores.
  3. 50,000,000 packet simulation evaluated only 5,000 packets and multiplied confusion matrix counts by 10,000. Feature extraction was excluded from the timed latency window.
  4. VeReMi benchmark in `run_veremi_benchmark.py` bypassed the authentic VeReMi dataset (`authentic_veremi_data.npz`) and used a hand-crafted synthetic generator tailor-made to match `attack_classifier.py` rule thresholds.
  5. Figures 2, 3, 4, 5, 6, 9, 10 rely on hardcoded numbers, synthetic normal distributions (`np.random.normal`), or synthetic sine waves, completely detached from raw results JSON.
  6. Memory cache `_PERM_CACHE` retains up to 50,000 session keys in RAM, violating Perfect Forward Secrecy.
  7. In `baseline_ciphers.py`, AES and ChaCha20 call `os.urandom(12)` syscalls per packet while DNA-V2X does not; yet AES and ChaCha20 are still 3x faster.
- Next: Draft comprehensive `survey_report.md` and `handoff.md`.
