"""
Unit tests for Multi-Class Attack Classifier and Moving Cars Simulator.
"""

import unittest
import numpy as np

from src.attack_classifier import (
    CLASS_NAMES,
    NUM_CLASSES,
    extract_features_vectorized,
    FastRuleAndMLClassifier
)
from src.moving_cars_simulation import MovingCarsSimulator


class TestAttackClassifier(unittest.TestCase):
    def setUp(self):
        self.sim = MovingCarsSimulator(num_vehicles=10, seed=42)
        self.classifier = FastRuleAndMLClassifier()

    def test_feature_extraction_dimensions(self):
        strands, r_states, cur_times, p_speeds, p_times, y_true = self.sim.generate_streaming_batch(
            batch_size=100, attack_ratio=0.5
        )
        self.assertEqual(len(strands), 100)
        features = extract_features_vectorized(strands, r_states, cur_times, p_speeds, p_times)
        self.assertEqual(features.shape, (100, 10))

    def test_classifier_accuracy_on_all_classes(self):
        # Generate training calibration data
        s_tr, r_tr, t_tr, sp_tr, pt_tr, y_tr = self.sim.generate_streaming_batch(2000, attack_ratio=0.5)
        f_tr = extract_features_vectorized(s_tr, r_tr, t_tr, sp_tr, pt_tr)
        self.classifier.train(f_tr, y_tr)

        # Test on each class individually
        for c_idx in range(NUM_CLASSES):
            if c_idx == 0:
                s_te, r_te, t_te, sp_te, pt_te, y_te = self.sim.generate_streaming_batch(200, attack_ratio=0.0)
            else:
                s_te, r_te, t_te, sp_te, pt_te, y_te = self.sim.generate_streaming_batch(200, attack_ratio=1.0, attack_types=[c_idx])

            f_te = extract_features_vectorized(s_te, r_te, t_te, sp_te, pt_te)
            y_pred = self.classifier.classify_batch_fast(f_te)

            acc = float(np.mean(y_pred == y_te)) * 100.0
            self.assertGreaterEqual(acc, 95.0, f"Class {CLASS_NAMES[c_idx]} accuracy below 95% ({acc:.2f}%)")


if __name__ == "__main__":
    unittest.main()
