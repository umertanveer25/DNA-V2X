"""
Adversarial Verification Suite for Milestone 2:
1. Dynamic Shannon Entropy (absence of hardcoded 7.96, variance across payloads/keys).
2. Data Leakage & Group Independence (GroupKFold disjointness, zero trajectory leakage).
3. Latency & Throughput Pipeline Timing (pure inference vs full pipeline transparency).
"""

import os
import json
import unittest
import numpy as np
from src.dataset import AuthenticVeReMiParser, get_grouped_kfold_splits
from src.dna_4mer_engine import DNA4MerEngine, DynamicPermutationState
from benchmarks.kfold_monte_carlo import (
    calculate_dynamic_dna_entropy,
    calculate_dynamic_byte_entropy,
    generate_synthetic_telemetry_corpus
)
from src.attack_classifier import FastRuleAndMLClassifier, extract_features_vectorized
from src.moving_cars_simulation import MovingCarsSimulator


class TestAdversarialM2Verification(unittest.TestCase):
    def test_dynamic_shannon_entropy_variance_and_no_constant(self):
        """Adversarially verifies dynamic Shannon entropy variance across seeds and payloads."""
        engine = DNA4MerEngine()
        corpus = generate_synthetic_telemetry_corpus(num_samples=200, seed=101)

        entropies = []
        for i in range(20):
            state = DynamicPermutationState(f"ADV_SEED_{i}".encode())
            packets = corpus[i * 10 : (i + 1) * 10]
            strands = []
            for p in packets:
                strands.append(engine.encode_bytes(p, state))
                state.ratchet_forward()
            ent = calculate_dynamic_dna_entropy("".join(strands))
            entropies.append(ent)

        # 1. Must vary naturally across keys and payloads
        self.assertGreater(np.std(entropies), 0.01, "Entropy standard deviation must be non-zero!")
        self.assertEqual(len(set(entropies)), len(entropies), "All entropy values must be distinct!")
        
        # 2. Must not be hardcoded 7.96
        for ent in entropies:
            self.assertFalse(np.isclose(ent, 7.96, atol=1e-4), f"Hardcoded 7.96 detected: {ent}")

        # 3. Master JSON check
        master_path = os.path.join(os.path.dirname(__file__), "..", "results", "dna_v2x_master_results.json")
        self.assertTrue(os.path.exists(master_path))
        with open(master_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        master_ents = data["raw_metrics"]["DNA-V2X (Proposed 4-Mer MTD)"]["entropy"]
        self.assertEqual(len(master_ents), 300)
        self.assertEqual(len(set(master_ents)), 300, "All 300 master benchmark runs must have distinct entropy!")
        self.assertFalse(any(np.isclose(e, 7.96, atol=1e-4) for e in master_ents), "Constant 7.96 must not exist in master results!")

    def test_zero_data_leakage_and_group_independence(self):
        """Adversarially verifies GroupKFold group disjointness and zero scenario leakage."""
        parser = AuthenticVeReMiParser(max_samples=20000)
        X, y, groups, attack_types = parser.load_dataset()

        unique_groups = np.unique(groups)
        self.assertGreater(len(unique_groups), 3, "Dataset must have multiple independent scenario groups.")

        for n_splits in [3, 5]:
            splits = get_grouped_kfold_splits(X, y, groups, n_splits=n_splits)
            for fold_idx, (train_idx, test_idx) in enumerate(splits):
                train_grp = set(groups[train_idx])
                test_grp = set(groups[test_idx])
                intersection = train_grp.intersection(test_grp)
                self.assertEqual(
                    len(intersection),
                    0,
                    f"DATA LEAKAGE DETECTED in {n_splits}-fold split {fold_idx}: Overlapping groups: {intersection}"
                )
                # Verify indices disjoint
                self.assertEqual(len(set(train_idx).intersection(set(test_idx))), 0)

    def test_pipeline_timing_honesty_and_no_concealment(self):
        """Adversarially validates feature extraction vs classification timing and honest reporting."""
        sim = MovingCarsSimulator(num_vehicles=20, seed=333)
        s, r, t, sp, pt, y = sim.generate_streaming_batch(batch_size=500, attack_ratio=0.3)

        feats = extract_features_vectorized(s, r, t, sp, pt)
        clf = FastRuleAndMLClassifier()
        clf.train(feats, y)

        # Check master json artifact
        master_path = os.path.join(os.path.dirname(__file__), "..", "results", "dna_v2x_50m_classification_master_results.json")
        self.assertTrue(os.path.exists(master_path))
        with open(master_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        meta = data["phase2_massive_50m_stream"]["stream_metadata"]
        feat_lat = meta["feature_extraction_latency_us"]
        inf_lat = meta["inference_latency_us"]
        mean_lat = meta["mean_classification_latency_us"]
        throughput = meta["overall_throughput_pkts_sec"]

        # 1. Both must be explicitly documented
        self.assertIn("feature_extraction_latency_us", meta)
        self.assertIn("inference_latency_us", meta)
        self.assertIn("mean_classification_latency_us", meta)
        self.assertIn("overall_throughput_pkts_sec", meta)

        # 2. Total latency must be sum of feature extraction + inference
        self.assertAlmostEqual(mean_lat, feat_lat + inf_lat, places=3)

        # 3. Overall throughput must reflect full pipeline (~1,000-1,200 pkts/s), NOT inflated inference-only rate
        expected_tp = 1_000_000.0 / mean_lat
        self.assertAlmostEqual(throughput, expected_tp, places=1)
        self.assertLess(throughput, 5000.0, "Overall throughput must not deceptively hide feature extraction cost!")
        self.assertGreater(throughput, 500.0, "Throughput must be realistic for vectorized feature extraction pipeline.")


if __name__ == "__main__":
    unittest.main()
