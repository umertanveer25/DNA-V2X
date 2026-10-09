"""
Regression Test Suite for BUG-01 (Integer Overflow on Windows 64-bit with numpy.uint32).
Can be executed directly: python test_bug01_regression.py
"""

import sys
import os
import unittest
import numpy as np

# Add project root to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..")))

from src.dna_4mer_engine import DNA4MerEngine, DynamicPermutationState
from src.v2x_telemetry_schema import serialize_bsm
from src.attack_classifier import extract_features_vectorized, FastRuleAndMLClassifier


class TestBug01IntegerOverflow(unittest.TestCase):
    def setUp(self):
        self.engine = DNA4MerEngine()
        self.state = DynamicPermutationState(b"BUG01_REGRESSION_TEST_KEY_32BYTES", "SESSION_01")
        self.classifier = FastRuleAndMLClassifier()

    def test_uint32_unverified_packet_extraction_does_not_overflow(self):
        """
        Tests that an unverified/corrupted/foreign strand evaluated with numpy.uint32 timestamps
        does not crash with OverflowError: Python int too large to convert to C long on line 229.
        """
        # An unverified 128-char strand that will fail CRC and past ratchet match,
        # proceeding to line 220+ (Sybil vs Mutation vs Desync discrimination)
        strand = "ACGT" * 32
        curr_ts_uint32 = np.array([100000000], dtype=np.uint32)

        try:
            features = extract_features_vectorized(
                dna_strands=[strand],
                receiver_states=[self.state],
                current_timestamps_ms=curr_ts_uint32
            )
            self.assertEqual(features.shape, (1, 10))
            print("[+] test_uint32_unverified_packet_extraction_does_not_overflow: PASSED")
        except OverflowError as e:
            self.fail(f"BUG-01 reproduced! extract_features_vectorized raised OverflowError: {e}")

    def test_uint32_timestamp_array_types(self):
        """
        Tests multiple numpy integer dtypes (uint32, int32, uint64, int64)
        for both current and previous timestamps.
        """
        strand = "ACGT" * 32
        for dtype in [np.uint32, np.int32, np.uint64, np.int64]:
            cur_times = np.array([500000], dtype=dtype)
            prev_times = np.array([499900], dtype=dtype)
            prev_speeds = np.array([45.0], dtype=np.float32)

            try:
                features = extract_features_vectorized(
                    dna_strands=[strand],
                    receiver_states=[self.state],
                    current_timestamps_ms=cur_times,
                    prev_speeds_kmh=prev_speeds,
                    prev_timestamps_ms=prev_times
                )
                self.assertEqual(features.shape, (1, 10))
            except OverflowError as e:
                self.fail(f"Failed for dtype {dtype.__name__}: {e}")
        print("[+] test_uint32_timestamp_array_types: PASSED")


if __name__ == "__main__":
    unittest.main()
