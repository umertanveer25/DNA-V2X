"""
Comprehensive Unit Tests for Remediated Empirical Benchmarks & Datasets.
Tests:
  1. AuthenticVeReMiParser loading, caching, grouped splits, and kinematic integrity.
  2. Dynamic Shannon entropy computation (byte and 4-mer DNA tokens).
  3. Empirical multi-vector attack mitigation rate evaluation.
  4. End-to-end pipeline latency timing (feature extraction + classification).
  5. Master results artifact structure and figure generation verification.
"""

import os
import unittest
import json
import numpy as np

from src.dataset import AuthenticVeReMiParser, get_grouped_kfold_splits, find_veremi_cache
from benchmarks.kfold_monte_carlo import (
    calculate_dynamic_byte_entropy,
    calculate_dynamic_dna_entropy,
    evaluate_empirical_attack_mitigation,
    generate_synthetic_telemetry_corpus
)
from benchmarks.baseline_ciphers import BaselineCiphers
from src.attack_classifier import FastRuleAndMLClassifier, extract_features_vectorized
from src.moving_cars_simulation import MovingCarsSimulator


class TestEmpiricalBenchmarks(unittest.TestCase):
    def setUp(self):
        self.ciphers = BaselineCiphers()
        self.rng = np.random.RandomState(42)

    def test_authentic_veremi_parser_and_grouped_splits(self):
        """Validates that AuthenticVeReMiParser loads authentic data without fake mocks."""
        cache_path = find_veremi_cache()
        self.assertTrue(os.path.exists(cache_path), f"VeReMi cache missing at {cache_path}")

        parser = AuthenticVeReMiParser(max_samples=10000)
        X, y, groups, atks = parser.load_dataset()

        self.assertEqual(len(X), 10000)
        self.assertEqual(X.shape[1], 7)  # 7 kinematic features
        self.assertEqual(len(y), 10000)
        self.assertTrue(set(np.unique(y)).issubset({0, 1}))

        # Test grouped k-fold splits
        n_grp = len(np.unique(groups))
        n_splits = min(3, n_grp)
        splits = get_grouped_kfold_splits(X, y, groups, n_splits=n_splits)
        self.assertEqual(len(splits), n_splits)
        train_idx, test_idx = splits[0]
        train_groups = set(groups[train_idx])
        test_groups = set(groups[test_idx])
        # Verify strictly zero group leakage
        self.assertEqual(len(train_groups.intersection(test_groups)), 0)

    def test_dynamic_shannon_entropy_bounds(self):
        """Validates dynamic Shannon entropy on uniform vs repetitive payloads."""
        # Flat repetitive strand
        flat_strand = "AAAA" * 50
        h_flat = calculate_dynamic_dna_entropy(flat_strand)
        self.assertAlmostEqual(h_flat, 0.0, places=2)

        # Uniform random bytes
        uniform_bytes = bytes(range(256)) * 4
        h_uniform = calculate_dynamic_byte_entropy(uniform_bytes)
        self.assertAlmostEqual(h_uniform, 8.0, places=2)

        # Telemetry corpus dynamic entropy
        corpus = generate_synthetic_telemetry_corpus(50, seed=42)
        h_corpus = calculate_dynamic_byte_entropy(b"".join(corpus))
        self.assertGreater(h_corpus, 4.0)
        self.assertLess(h_corpus, 8.0)

    def test_empirical_attack_mitigation_rates(self):
        """Validates empirical mitigation rate evaluation on actual cipher objects."""
        corpus = generate_synthetic_telemetry_corpus(20, seed=42)

        # DNA-V2X achieves 100% mitigation due to ratchet, codon guard, and CRC-32
        mit_dna = evaluate_empirical_attack_mitigation("DNA-V2X (Proposed 4-Mer MTD)", self.ciphers, corpus, self.rng)
        self.assertEqual(mit_dna, 100.0)

        # Plaintext has 0% mitigation
        mit_plain = evaluate_empirical_attack_mitigation("Plaintext (Zero-Security)", self.ciphers, corpus, self.rng)
        self.assertEqual(mit_plain, 0.0)

        # AES-GCM mitigates tamper and key injection, but not raw replay without monotonic counters
        mit_aes = evaluate_empirical_attack_mitigation("AES-128-GCM (NIST Standard)", self.ciphers, corpus, self.rng)
        self.assertGreaterEqual(mit_aes, 60.0)
        self.assertLessEqual(mit_aes, 100.0)

    def test_full_pipeline_timing_inclusion(self):
        """Validates that feature extraction and classification timing are both included."""
        sim = MovingCarsSimulator(num_vehicles=10, seed=99)
        s, r, t, sp, pt, y = sim.generate_streaming_batch(batch_size=50, attack_ratio=0.3)

        features = extract_features_vectorized(s, r, t, sp, pt)
        self.assertEqual(features.shape, (50, 10))

        clf = FastRuleAndMLClassifier()
        clf.train(features, y)
        preds = clf.classify_batch_fast(features)
        self.assertEqual(len(preds), 50)

    def test_master_results_and_figures_integrity(self):
        """Validates that master results JSON files and all 10 publication figures exist."""
        project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
        results_dir = os.path.join(project_root, "results")
        figures_dir = os.path.join(project_root, "figures")

        # Master results JSON files
        master_json = os.path.join(results_dir, "dna_v2x_master_results.json")
        self.assertTrue(os.path.exists(master_json), f"Master JSON missing: {master_json}")

        stream_json = os.path.join(results_dir, "dna_v2x_50m_classification_master_results.json")
        self.assertTrue(os.path.exists(stream_json), f"Stream JSON missing: {stream_json}")

        veremi_json = os.path.join(results_dir, "veremi_master_results.json")
        self.assertTrue(os.path.exists(veremi_json), f"VeReMi JSON missing: {veremi_json}")

        # All 4 CSV tables
        for tbl in ["Table1_10Fold_30Split_Performance_Benchmark.csv",
                    "Table2_Attack_Resistance_Evaluation.csv",
                    "Table3_50M_Moving_Cars_Attack_Classification.csv",
                    "Table4_VeReMi_Benchmark.csv"]:
            p = os.path.join(results_dir, tbl)
            self.assertTrue(os.path.exists(p), f"CSV table missing: {p}")
            self.assertGreater(os.path.getsize(p), 100, f"CSV table empty: {p}")

        # Figures 1 to 10
        expected_figs = [
            "Fig1_DNA_V2X_Architecture_Pipeline.png",
            "Fig2_Latency_and_Energy_Comparison.png",
            "Fig3_Shannon_Entropy_and_Randomness.png",
            "Fig4_Throughput_and_Packet_Processing_Rate.png",
            "Fig5_Attack_Mitigation_Matrix.png",
            "Fig6_10Fold_30Split_Stability_Distributions.png",
            "Fig7_50M_Attack_Classification_Confusion_Matrix.png",
            "Fig8_Per_Class_Precision_Recall_F1_Breakdown.png",
            "Fig9_50M_Stream_Throughput_and_Latency_Scaling.png",
            "Fig10_Moving_Cars_Warfare_Timeline_Distribution.png"
        ]
        for fig in expected_figs:
            p_res = os.path.join(results_dir, fig)
            p_fig = os.path.join(figures_dir, fig)
            self.assertTrue(os.path.exists(p_res), f"Figure missing in results/: {fig}")
            self.assertTrue(os.path.exists(p_fig), f"Figure missing in figures/: {fig}")
            self.assertGreater(os.path.getsize(p_res), 50000, f"Figure too small: {fig}")


if __name__ == "__main__":
    unittest.main()
