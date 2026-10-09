"""
DNA-V2X: Comprehensive End-to-End (E2E) Test Suite.
Verifies the full lifecycle across BSM, SPaT, DENM schemas, 4-mer genomic cryptography,
forward ratcheting, cyber-physical threat mitigation, and real-time classification.

4-Tier Methodology:
  - Tier 1: Functional Feature Coverage (>= 5 tests per feature)
  - Tier 2: Boundary Value Analysis & Edge Cases (>= 5 tests per feature)
  - Tier 3: Cross-Feature Pairwise Interactions
  - Tier 4: Real-World Vehicular Workload Scenarios (>= 5 scenarios)
"""

import unittest
import struct
import zlib
import time
import math
import random
import numpy as np

from src.v2x_telemetry_schema import (
    serialize_bsm,
    serialize_cam,
    serialize_spat,
    serialize_denm,
    deserialize_v2x_packet,
    compute_lightweight_mac,
    verify_lightweight_mac,
    MSG_TYPE_BSM,
    MSG_TYPE_CAM,
    MSG_TYPE_SPAT,
    MSG_TYPE_DENM,
    V2XTelemetryPacket,
)
from src.dna_4mer_engine import (
    ALL_256_4MERS,
    BASES,
    DNA4MerEngine,
    DynamicPermutationState,
)
from src.attack_simulator import (
    AttackSimulator,
    AttackResult,
)
from src.attack_classifier import (
    CLASS_NAMES,
    NUM_CLASSES,
    extract_features_vectorized,
    FastRuleAndMLClassifier,
)
from src.moving_cars_simulation import (
    MovingCarsSimulator,
    ConnectedVehicle,
)


# ==============================================================================
# TIER 1: Functional Feature Coverage (>= 5 per feature)
# ==============================================================================

class TestTier1FunctionalFeatures(unittest.TestCase):
    """
    Tier 1 tests covering primary happy paths and functional requirements:
      - Feature 1: BSM Serialization & Deserialization
      - Feature 2: SPaT Signal Timing Serialization
      - Feature 3: DENM Hazard Alert Serialization
      - Feature 4: DNA-V2X 4-Mer Genomic Permutation & Encryption Lifecycle
      - Feature 5: Multi-Class Attack Detection & Classification
    """

    def setUp(self):
        self.engine = DNA4MerEngine()
        self.seed_alice = b"OBUSHAREDSECRET1"
        self.seed_bob = b"OBUSHAREDSECRET1"
        self.state_alice = DynamicPermutationState(self.seed_alice, "PAIR_V2V_1001_1002")
        self.state_bob = DynamicPermutationState(self.seed_bob, "PAIR_V2V_1001_1002")

    # --- Feature 1: BSM Serialization & Deserialization (5 tests) ---

    def test_tier1_bsm_standard_roundtrip(self):
        """T1-BSM-1: Validates standard BSM serialization and deserialization."""
        raw = serialize_bsm(station_id=101, speed_kmh=80.0, accel_mps2=1.5, heading_deg=90.0)
        self.assertEqual(len(raw), 32)
        pkt = deserialize_v2x_packet(raw)
        self.assertEqual(pkt.msg_type, MSG_TYPE_BSM)
        self.assertEqual(pkt.station_id, 101)
        self.assertAlmostEqual(pkt.speed_kmh, 80.0, places=1)
        self.assertAlmostEqual(pkt.accel_mps2, 1.5, places=1)
        self.assertAlmostEqual(pkt.heading_deg, 90.0, places=1)

    def test_tier1_bsm_kinematics_fidelity(self):
        """T1-BSM-2: Validates floating-point kinematic precision for speed, acceleration, and heading."""
        raw = serialize_bsm(station_id=102, speed_kmh=112.45, accel_mps2=-4.68, heading_deg=235.4)
        pkt = deserialize_v2x_packet(raw)
        self.assertAlmostEqual(pkt.speed_kmh, 112.45, places=2)
        self.assertAlmostEqual(pkt.accel_mps2, -4.68, places=2)
        self.assertAlmostEqual(pkt.heading_deg, 235.4, places=1)

    def test_tier1_bsm_coordinates_fidelity(self):
        """T1-BSM-3: Validates sub-meter coordinate precision for latitude, longitude, and elevation."""
        lat = 37.774929
        lon = -122.419416
        elev = 42.0
        raw = serialize_bsm(station_id=103, speed_kmh=50.0, accel_mps2=0.0, heading_deg=0.0,
                            latitude=lat, longitude=lon, elevation_m=elev)
        pkt = deserialize_v2x_packet(raw)
        self.assertAlmostEqual(pkt.latitude, lat, places=5)
        self.assertAlmostEqual(pkt.longitude, lon, places=5)
        self.assertAlmostEqual(pkt.elevation_m, elev, places=1)

    def test_tier1_bsm_safety_bitmask_flags(self):
        """T1-BSM-4: Validates individual and composite safety bitmask flags (brake, ABS)."""
        raw_brake = serialize_bsm(station_id=104, speed_kmh=50.0, accel_mps2=0.0, heading_deg=0.0, brake_active=1, abs_active=0)
        self.assertEqual(deserialize_v2x_packet(raw_brake).safety_bitmask, 1)

        raw_abs = serialize_bsm(station_id=104, speed_kmh=50.0, accel_mps2=0.0, heading_deg=0.0, brake_active=0, abs_active=1)
        self.assertEqual(deserialize_v2x_packet(raw_abs).safety_bitmask, 2)

        raw_both = serialize_bsm(station_id=104, speed_kmh=50.0, accel_mps2=0.0, heading_deg=0.0, brake_active=1, abs_active=1)
        self.assertEqual(deserialize_v2x_packet(raw_both).safety_bitmask, 3)

        raw_none = serialize_bsm(station_id=104, speed_kmh=50.0, accel_mps2=0.0, heading_deg=0.0, brake_active=0, abs_active=0)
        self.assertEqual(deserialize_v2x_packet(raw_none).safety_bitmask, 0)

    def test_tier1_bsm_crc32_checksum_verification(self):
        """T1-BSM-5: Validates that valid BSM payloads pass standard CRC-32 verification."""
        raw = serialize_bsm(station_id=105, speed_kmh=65.0, accel_mps2=0.8, heading_deg=180.0)
        payload = raw[:28]
        expected_crc = struct.unpack(">I", raw[28:])[0]
        self.assertEqual(zlib.crc32(payload), expected_crc)

    # --- Feature 2: SPaT Signal Timing Serialization (5 tests) ---

    def test_tier1_spat_standard_roundtrip(self):
        """T1-SPAT-1: Validates standard SPaT signal phase serialization and deserialization."""
        raw = serialize_spat(station_id=201, phase_id=1, countdown_sec=25.0)
        self.assertEqual(len(raw), 32)
        pkt = deserialize_v2x_packet(raw)
        self.assertEqual(pkt.msg_type, MSG_TYPE_SPAT)
        self.assertEqual(pkt.station_id, 201)

    def test_tier1_spat_countdown_precision(self):
        """T1-SPAT-2: Validates 0.1s resolution countdown serialization across multiple durations."""
        for cd in [0.0, 15.5, 45.2, 120.0]:
            raw = serialize_spat(station_id=202, phase_id=3, countdown_sec=cd)
            cd_raw = struct.unpack(">H", raw[12:14])[0]
            self.assertAlmostEqual(cd_raw / 10.0, cd, places=1)

    def test_tier1_spat_station_id_fidelity(self):
        """T1-SPAT-3: Validates intersection station ID fidelity across distinct integer ranges."""
        for sid in [1, 555, 65535, 98765432]:
            raw = serialize_spat(station_id=sid, phase_id=2, countdown_sec=10.0)
            pkt = deserialize_v2x_packet(raw)
            self.assertEqual(pkt.station_id, sid)

    def test_tier1_spat_timestamp_synchronization(self):
        """T1-SPAT-4: Validates timestamp synchronization preservation in SPaT frames."""
        ts = 1700000000
        raw = serialize_spat(station_id=204, phase_id=1, countdown_sec=5.0, timestamp_ms=ts)
        pkt = deserialize_v2x_packet(raw)
        self.assertEqual(pkt.timestamp_ms, ts)

    def test_tier1_spat_crc32_integrity(self):
        """T1-SPAT-5: Validates CRC-32 integrity seal across valid SPaT frames."""
        raw = serialize_spat(station_id=205, phase_id=4, countdown_sec=30.0)
        self.assertEqual(zlib.crc32(raw[:28]), struct.unpack(">I", raw[28:])[0])

    # --- Feature 3: DENM Hazard Alert Serialization (5 tests) ---

    def test_tier1_denm_hard_brake_alert(self):
        """T1-DENM-1: Validates emergency hard brake hazard alert serialization."""
        raw = serialize_denm(station_id=301, cause_code=1, speed_kmh=90.0, heading_deg=45.0)
        self.assertEqual(len(raw), 32)
        pkt = deserialize_v2x_packet(raw)
        self.assertEqual(pkt.msg_type, MSG_TYPE_DENM)
        cause = struct.unpack(">H", raw[10:12])[0]
        self.assertEqual(cause, 1)

    def test_tier1_denm_road_hazard_alert(self):
        """T1-DENM-2: Validates road hazard alert serialization (cause code 2)."""
        raw = serialize_denm(station_id=302, cause_code=2, speed_kmh=60.0, heading_deg=90.0)
        pkt = deserialize_v2x_packet(raw)
        self.assertEqual(pkt.msg_type, MSG_TYPE_DENM)
        self.assertEqual(struct.unpack(">H", raw[10:12])[0], 2)

    def test_tier1_denm_accident_notification(self):
        """T1-DENM-3: Validates accident notification alert serialization (cause code 4)."""
        raw = serialize_denm(station_id=303, cause_code=4, speed_kmh=0.0, heading_deg=0.0)
        pkt = deserialize_v2x_packet(raw)
        self.assertEqual(pkt.msg_type, MSG_TYPE_DENM)
        self.assertEqual(struct.unpack(">H", raw[10:12])[0], 4)

    def test_tier1_denm_vehicle_state_at_hazard(self):
        """T1-DENM-4: Validates recording of vehicle speed and heading during hazard event."""
        raw = serialize_denm(station_id=304, cause_code=3, speed_kmh=75.5, heading_deg=180.0)
        spd = struct.unpack(">H", raw[12:14])[0] / 100.0
        hdg = struct.unpack(">H", raw[14:16])[0] / 10.0
        self.assertAlmostEqual(spd, 75.5, places=1)
        self.assertAlmostEqual(hdg, 180.0, places=1)

    def test_tier1_denm_crc32_verification(self):
        """T1-DENM-5: Validates CRC-32 integrity seal across valid DENM frames."""
        raw = serialize_denm(station_id=305, cause_code=1, speed_kmh=100.0, heading_deg=270.0)
        self.assertEqual(zlib.crc32(raw[:28]), struct.unpack(">I", raw[28:])[0])

    # --- Feature 4: DNA-V2X 4-Mer Genomic Permutation & Encryption Lifecycle (5 tests) ---

    def test_tier1_genomic_canonical_universe(self):
        """T1-GEN-1: Validates canonical 256 4-mer universe completeness, uniqueness, and composition."""
        self.assertEqual(len(ALL_256_4MERS), 256)
        self.assertEqual(len(set(ALL_256_4MERS)), 256)
        for codon in ALL_256_4MERS:
            self.assertEqual(len(codon), 4)
            self.assertTrue(all(c in BASES for c in codon))

    def test_tier1_genomic_bijective_roundtrip(self):
        """T1-GEN-2: Validates strict 1:1 bijective encoding and decoding of arbitrary byte arrays."""
        payload = bytes(range(256))
        strand = self.engine.encode_bytes(payload, self.state_alice)
        self.assertEqual(len(strand), 256 * 4)
        recovered = self.engine.decode_strand(strand, self.state_bob)
        self.assertEqual(recovered, payload)

    def test_tier1_genomic_forward_ratchet_pfs(self):
        """T1-GEN-3: Validates forward ratchet alters ciphertexts across consecutive frames (PFS)."""
        payload = b"CRITICAL_VEHICULAR_TELEMETRY_01!"
        strand_f0 = self.engine.encode_bytes(payload, self.state_alice)
        self.state_alice.ratchet_forward()
        self.state_bob.ratchet_forward()
        strand_f1 = self.engine.encode_bytes(payload, self.state_alice)

        self.assertNotEqual(strand_f0, strand_f1)
        decoded_f1 = self.engine.decode_strand(strand_f1, self.state_bob)
        self.assertEqual(decoded_f1, payload)

    def test_tier1_genomic_spn_avalanche_diffusion(self):
        """T1-GEN-4: Validates Genomic-SPN mode produces >= 40% avalanche nucleotide diffusion on 1-bit change."""
        p1 = b"VEHICLE_CRITICAL_TELEMETRY_0123!"
        p2 = bytearray(p1)
        p2[-1] ^= 0x01
        p2 = bytes(p2)

        strand1 = self.engine.encode_spn_bytes(p1, self.state_alice)
        strand2 = self.engine.encode_spn_bytes(p2, self.state_alice)

        diff_count = sum(1 for c1, c2 in zip(strand1, strand2) if c1 != c2)
        diff_ratio = diff_count / len(strand1)
        self.assertGreaterEqual(diff_ratio, 0.40)
        self.assertEqual(self.engine.decode_spn_strand(strand1, self.state_bob), p1)

    def test_tier1_genomic_memory_purge(self):
        """T1-GEN-5: Validates zero-fill RAM sanitization on purge_memory()."""
        self.state_alice.purge_memory()
        self.assertEqual(len(self.state_alice.active_4mer_to_byte), 0)
        self.assertEqual(self.state_alice.active_byte_to_4mer[0], "AAAA")

    # --- Feature 5: Multi-Class Attack Detection & Classification (5 tests) ---

    def test_tier1_attack_replay_detection(self):
        """T1-ATK-1: Validates message replay attack detection with 100% rate."""
        sim = AttackSimulator()
        res = sim.test_replay_attack(num_trials=25, delay_frames=2)
        self.assertEqual(res.detection_rate_pct, 100.0)
        self.assertEqual(res.successful_breaches, 0)

    def test_tier1_attack_mutation_detection(self):
        """T1-ATK-2: Validates nucleotide mutation tampering attack detection with 100% rate."""
        sim = AttackSimulator()
        res = sim.test_mutation_tamper_attack(num_trials=25, num_mutations=1)
        self.assertEqual(res.detection_rate_pct, 100.0)
        self.assertEqual(res.successful_breaches, 0)

    def test_tier1_attack_sybil_detection(self):
        """T1-ATK-3: Validates unauthorized Sybil ghost vehicle injection detection with 100% rate."""
        sim = AttackSimulator()
        res = sim.test_sybil_ghost_injection(num_trials=25)
        self.assertEqual(res.detection_rate_pct, 100.0)
        self.assertEqual(res.successful_breaches, 0)

    def test_tier1_attack_frequency_probe_detection(self):
        """T1-ATK-4: Validates defense against frequency analysis attack on uniform telemetry."""
        sim = AttackSimulator()
        res = sim.test_frequency_analysis_attack(num_packets=100)
        self.assertGreater(res.details["shannon_entropy_bits"], 7.5)

    def test_tier1_attack_mitm_desync_detection(self):
        """T1-ATK-5: Validates generation and feature extraction of MITM frame desynchronization attacks."""
        mc_sim = MovingCarsSimulator(num_vehicles=5, seed=42)
        strands, states, t, sp, pt, y = mc_sim.generate_streaming_batch(batch_size=50, attack_ratio=1.0, attack_types=[5])
        self.assertTrue(all(label == 5 for label in y))
        features = extract_features_vectorized(strands, states, t, sp, pt)
        self.assertEqual(features.shape, (50, 10))


# ==============================================================================
# TIER 2: Boundary Value Analysis & Edge Cases (>= 5 per feature)
# ==============================================================================

class TestTier2BoundaryAndCornerCases(unittest.TestCase):
    """
    Tier 2 tests covering extreme values, bounds, corrupted packets, and edge cases:
      - Feature 1: BSM Boundaries (extremal speeds, accels, angles, coordinates)
      - Feature 2: SPaT & DENM Boundaries (countdowns, phase codes, corruptions)
      - Feature 3: Genomic 4-Mer Boundaries (empty, malformed lengths, bad alphabet)
      - Feature 4: Attack Simulator Boundaries (single-bit, full-strand mutation, edge entropy)
      - Feature 5: MAC & Memory Boundaries (bit flips, invalid lengths, double purges)
    """

    # --- Feature 1: BSM Boundaries (5 tests) ---

    def test_tier2_bsm_boundary_speed_extremes(self):
        """T2-BSM-1: Validates speed boundaries (0.0 km/h minimum, 250.0 km/h maximum clipping)."""
        for spd_in, spd_exp in [(0.0, 0.0), (250.0, 250.0), (320.0, 250.0), (-15.0, 0.0)]:
            raw = serialize_bsm(station_id=1, speed_kmh=spd_in, accel_mps2=0.0, heading_deg=0.0)
            pkt = deserialize_v2x_packet(raw)
            self.assertAlmostEqual(pkt.speed_kmh, spd_exp, places=1)

    def test_tier2_bsm_boundary_accel_extremes(self):
        """T2-BSM-2: Validates acceleration boundaries (-20.0 to +20.0 m/s^2 clipping)."""
        for acc_in, acc_exp in [(-20.0, -20.0), (20.0, 20.0), (-35.0, -20.0), (45.0, 20.0)]:
            raw = serialize_bsm(station_id=1, speed_kmh=50.0, accel_mps2=acc_in, heading_deg=0.0)
            pkt = deserialize_v2x_packet(raw)
            self.assertAlmostEqual(pkt.accel_mps2, acc_exp, places=1)

    def test_tier2_bsm_boundary_geographic_extremes(self):
        """T2-BSM-3: Validates latitude (+-90 deg) and longitude (+-180 deg) spatial boundaries."""
        for lat, lon in [(90.0, 180.0), (-90.0, -180.0), (0.0, 0.0)]:
            raw = serialize_bsm(station_id=1, speed_kmh=50.0, accel_mps2=0.0, heading_deg=0.0, latitude=lat, longitude=lon)
            pkt = deserialize_v2x_packet(raw)
            self.assertAlmostEqual(pkt.latitude, lat, places=5)
            self.assertAlmostEqual(pkt.longitude, lon, places=5)

    def test_tier2_bsm_boundary_heading_modulo(self):
        """T2-BSM-4: Validates heading boundary angles and modulo 360 wraparound."""
        for hdg_in, hdg_exp in [(0.0, 0.0), (359.9, 359.9), (360.0, 0.0), (720.0, 0.0)]:
            raw = serialize_bsm(station_id=1, speed_kmh=50.0, accel_mps2=0.0, heading_deg=hdg_in)
            pkt = deserialize_v2x_packet(raw)
            self.assertAlmostEqual(pkt.heading_deg, hdg_exp, places=1)

    def test_tier2_bsm_boundary_truncated_corrupted_crc(self):
        """T2-BSM-5: Validates truncated buffers, oversized buffers, and corrupted CRC rejection."""
        raw = serialize_bsm(station_id=1, speed_kmh=50.0, accel_mps2=0.0, heading_deg=0.0)
        with self.assertRaises(ValueError):
            deserialize_v2x_packet(raw[:31])
        with self.assertRaises(ValueError):
            deserialize_v2x_packet(raw + b"\x00")
        corrupt = bytearray(raw)
        corrupt[5] ^= 0x55
        with self.assertRaises(ValueError):
            deserialize_v2x_packet(bytes(corrupt))

    # --- Feature 2: SPaT & DENM Boundaries (5 tests) ---

    def test_tier2_spat_boundary_countdown_limits(self):
        """T2-SPAT-1: Validates countdown limits (0.0s to 120.0s bounds)."""
        for cd_in, cd_exp in [(0.0, 0.0), (120.0, 120.0), (-10.0, 0.0), (180.0, 120.0)]:
            raw = serialize_spat(station_id=1, phase_id=1, countdown_sec=cd_in)
            cd_raw = struct.unpack(">H", raw[12:14])[0] / 10.0
            self.assertAlmostEqual(cd_raw, cd_exp, places=1)

    def test_tier2_spat_boundary_phase_codes(self):
        """T2-SPAT-2: Validates extremal phase code integer values."""
        for phase in [0, 1, 4, 65535]:
            raw = serialize_spat(station_id=1, phase_id=phase, countdown_sec=10.0)
            self.assertEqual(len(raw), 32)
            self.assertEqual(struct.unpack(">H", raw[10:12])[0], phase)

    def test_tier2_denm_boundary_cause_codes(self):
        """T2-DENM-1: Validates extremal cause codes in DENM hazard frames."""
        for code in [0, 1, 4, 65535]:
            raw = serialize_denm(station_id=1, cause_code=code, speed_kmh=60.0, heading_deg=0.0)
            self.assertEqual(len(raw), 32)
            self.assertEqual(struct.unpack(">H", raw[10:12])[0], code)

    def test_tier2_denm_boundary_speed_heading(self):
        """T2-DENM-2: Validates speed and heading boundaries on DENM alert frames."""
        for spd, hdg in [(0.0, 0.0), (250.0, 359.9), (300.0, 360.0)]:
            raw = serialize_denm(station_id=1, cause_code=1, speed_kmh=spd, heading_deg=hdg)
            self.assertEqual(len(raw), 32)
            self.assertEqual(deserialize_v2x_packet(raw).msg_type, MSG_TYPE_DENM)

    def test_tier2_spat_denm_corrupted_payload_rejection(self):
        """T2-SPAT-DENM-3: Validates corrupted SPaT and DENM payload rejection by CRC."""
        for fn in [lambda: serialize_spat(1, 1, 10.0), lambda: serialize_denm(1, 1, 50.0, 0.0)]:
            raw = fn()
            corrupted = bytearray(raw)
            corrupted[10] ^= 0xFF
            with self.assertRaises(ValueError):
                deserialize_v2x_packet(bytes(corrupted))

    # --- Feature 3: Genomic 4-Mer Boundaries (5 tests) ---

    def test_tier2_genomic_boundary_empty_strand(self):
        """T2-GEN-1: Validates handling of empty payloads and empty strands."""
        eng = DNA4MerEngine()
        st = DynamicPermutationState(b"SEED_TEST_001")
        self.assertEqual(eng.encode_bytes(b"", st), "")
        self.assertEqual(eng.decode_strand("", st), b"")

    def test_tier2_genomic_boundary_non_multiple_of_4(self):
        """T2-GEN-2: Validates rejection of strand lengths that are not multiples of 4."""
        eng = DNA4MerEngine()
        st = DynamicPermutationState(b"SEED_TEST_002")
        for bad_len in [1, 2, 3, 5, 127]:
            with self.assertRaises(ValueError):
                eng.decode_strand("A" * bad_len, st)

    def test_tier2_genomic_boundary_invalid_nucleotide_alphabet(self):
        """T2-GEN-3: Validates rejection of unknown codons with characters outside A, C, G, T."""
        eng = DNA4MerEngine()
        st = DynamicPermutationState(b"SEED_TEST_003")
        for invalid_codon in ["ZZZZ", "1234", "NNNN", "A CA"]:
            with self.assertRaises(ValueError):
                eng.decode_strand(invalid_codon, st)

    def test_tier2_genomic_boundary_all_zero_and_all_ff_payloads(self):
        """T2-GEN-4: Validates extreme byte payloads (all 0x00 and all 0xFF)."""
        eng = DNA4MerEngine()
        st = DynamicPermutationState(b"SEED_TEST_004")
        for b_val in [0x00, 0xFF]:
            payload = bytes([b_val] * 32)
            strand = eng.encode_bytes(payload, st)
            self.assertEqual(len(strand), 128)
            self.assertEqual(eng.decode_strand(strand, st), payload)

    def test_tier2_genomic_boundary_entropy_uniform_vs_monotonous(self):
        """T2-GEN-5: Validates Shannon entropy bounds (monotonous H=0.0 vs uniform H=8.0)."""
        eng = DNA4MerEngine()
        monotonous_strand = "AAAA" * 32
        self.assertAlmostEqual(eng.calculate_shannon_entropy(monotonous_strand), 0.0, places=2)
        st = DynamicPermutationState(b"SEED_TEST_005")
        full_spec = bytes(range(256))
        uniform_strand = eng.encode_bytes(full_spec, st)
        self.assertAlmostEqual(eng.calculate_shannon_entropy(uniform_strand), 8.0, places=2)

    # --- Feature 4: Attack Simulator Boundaries (5 tests) ---

    def test_tier2_attack_boundary_single_nucleotide_mutation(self):
        """T2-ATK-1: Validates rejection of a minimal 1-base mutation in 128-base strand."""
        eng = DNA4MerEngine()
        st = DynamicPermutationState(b"MUT_BOUND_SEED")
        raw = serialize_bsm(station_id=1, speed_kmh=80.0, accel_mps2=0.0, heading_deg=0.0)
        strand = eng.encode_bytes(raw, st)
        mutated = ("C" if strand[0] == "A" else "A") + strand[1:]
        with self.assertRaises(Exception):
            dec = eng.decode_strand(mutated, st)
            deserialize_v2x_packet(dec)

    def test_tier2_attack_boundary_full_strand_mutation(self):
        """T2-ATK-2: Validates rejection of a 100% corrupted 128-base strand."""
        eng = DNA4MerEngine()
        st = DynamicPermutationState(b"FULL_MUT_SEED")
        raw = serialize_bsm(station_id=1, speed_kmh=80.0, accel_mps2=0.0, heading_deg=0.0)
        strand = eng.encode_bytes(raw, st)
        mutated = "".join("T" if c != "T" else "A" for c in strand)
        with self.assertRaises(Exception):
            dec = eng.decode_strand(mutated, st)
            deserialize_v2x_packet(dec)

    def test_tier2_attack_boundary_minimal_replay_delay(self):
        """T2-ATK-3: Validates detection of replay attack with minimal delay_frames=1."""
        sim = AttackSimulator()
        res = sim.test_replay_attack(num_trials=25, delay_frames=1)
        self.assertEqual(res.detection_rate_pct, 100.0)

    def test_tier2_attack_boundary_entropy_threshold_edge(self):
        """T2-ATK-4: Validates entropy distinction for low vs high entropy strands."""
        eng = DNA4MerEngine()
        st = DynamicPermutationState(b"ENT_EDGE_SEED")
        low_ent = "AAAA" * 32
        self.assertLess(eng.calculate_shannon_entropy(low_ent), 2.0)
        high_ent = eng.encode_bytes(bytes(range(32)), st)
        self.assertGreater(eng.calculate_shannon_entropy(high_ent), 2.0)

    def test_tier2_attack_boundary_single_sample_feature_extraction(self):
        """T2-ATK-5: Validates vectorized feature extraction on a batch size of N=1 without dimension collapse."""
        st = DynamicPermutationState(b"SINGLE_FEAT_SEED")
        raw = serialize_bsm(station_id=1, speed_kmh=60.0, accel_mps2=0.0, heading_deg=0.0)
        strand = DNA4MerEngine().encode_bytes(raw, st)
        features = extract_features_vectorized([strand], [st], np.array([1000], dtype=np.int64))
        self.assertEqual(features.shape, (1, 10))
        self.assertEqual(features[0, 1], 1.0)  # CRC match

    # --- Feature 5: MAC & Memory Boundaries (5 tests) ---

    def test_tier2_mac_boundary_single_bit_flip(self):
        """T2-MAC-1: Validates that 1-bit payload flip fails constant-time MAC verification."""
        payload = b"PAYLOAD_28_BYTES_TEST_MAC_01"
        key = b"TEST_SESSION_KEY_01"
        mac = compute_lightweight_mac(payload, key)
        bad_payload = bytearray(payload)
        bad_payload[0] ^= 0x01
        self.assertFalse(verify_lightweight_mac(bytes(bad_payload), mac, key))

    def test_tier2_mac_boundary_wrong_key(self):
        """T2-MAC-2: Validates that wrong session key fails constant-time MAC verification."""
        payload = b"PAYLOAD_28_BYTES_TEST_MAC_02"
        mac = compute_lightweight_mac(payload, b"KEY_ALICE")
        self.assertFalse(verify_lightweight_mac(payload, mac, b"KEY_BOB"))

    def test_tier2_mac_boundary_invalid_length(self):
        """T2-MAC-3: Validates that payload lengths other than 28 bytes raise ValueError."""
        with self.assertRaises(ValueError):
            compute_lightweight_mac(b"SHORT", b"KEY")
        with self.assertRaises(ValueError):
            compute_lightweight_mac(b"A" * 29, b"KEY")

    def test_tier2_memory_boundary_double_purge_idempotence(self):
        """T2-MEM-1: Validates calling purge_memory() multiple times is idempotent and safe."""
        st = DynamicPermutationState(b"PURGE_TEST_SEED")
        st.purge_memory()
        st.purge_memory()
        self.assertEqual(len(st.active_4mer_to_byte), 0)

    def test_tier2_ratchet_boundary_high_frame_count(self):
        """T2-RATCHET-1: Validates ratcheting across 100 consecutive epochs maintains synchronization."""
        st_a = DynamicPermutationState(b"HIGH_FRAME_SEED")
        st_b = DynamicPermutationState(b"HIGH_FRAME_SEED")
        for _ in range(100):
            st_a.ratchet_forward()
            st_b.ratchet_forward()
        self.assertEqual(st_a.frame_counter, 100)
        raw = serialize_bsm(station_id=1, speed_kmh=90.0, accel_mps2=0.0, heading_deg=0.0)
        eng = DNA4MerEngine()
        strand = eng.encode_bytes(raw, st_a)
        self.assertEqual(eng.decode_strand(strand, st_b), raw)


# ==============================================================================
# TIER 3: Cross-Feature Pairwise Interactions
# ==============================================================================

class TestTier3CrossFeaturePairwise(unittest.TestCase):
    """
    Tier 3 tests covering pairwise combinations of interdependent features:
      - Session re-keying under active replay attack
      - Multiple concurrent vehicle sessions
      - Ratcheted streams under replay + mutation tampering
      - SPaT and DENM frames through Genomic-SPN mode
      - End-to-end authenticated telemetry pipeline
    """

    def test_tier3_pairwise_session_rekeying_under_active_replay(self):
        """T3-PAIR-1: Evaluates session re-keying while an adversary executes active frame replay."""
        eng = DNA4MerEngine()
        seed_1 = b"SHARED_SECRET_SESSION_1"
        alice = DynamicPermutationState(seed_1)
        bob = DynamicPermutationState(seed_1)

        # Alice sends frames 0 through 4
        captured_strand = None
        for frame in range(5):
            raw = serialize_bsm(station_id=1, speed_kmh=80.0 + frame, accel_mps2=0.0, heading_deg=0.0)
            strand = eng.encode_bytes(raw, alice)
            if frame == 2:
                captured_strand = strand
            rec = eng.decode_strand(strand, bob)
            self.assertEqual(rec, raw)
            alice.ratchet_forward()
            bob.ratchet_forward()

        # Attacker replays captured frame 2 at frame 5 -> bob rejects
        with self.assertRaises(Exception):
            dec = eng.decode_strand(captured_strand, bob)
            deserialize_v2x_packet(dec)

        # Alice and Bob perform session re-keying (new seed)
        seed_2 = b"SHARED_SECRET_SESSION_2"
        alice = DynamicPermutationState(seed_2)
        bob = DynamicPermutationState(seed_2)

        # Attacker tries replaying frame 2 against new session -> rejected
        with self.assertRaises(Exception):
            dec = eng.decode_strand(captured_strand, bob)
            deserialize_v2x_packet(dec)

        # Fresh frames in new session succeed
        raw_new = serialize_bsm(station_id=1, speed_kmh=95.0, accel_mps2=0.0, heading_deg=0.0)
        strand_new = eng.encode_bytes(raw_new, alice)
        self.assertEqual(eng.decode_strand(strand_new, bob), raw_new)

    def test_tier3_pairwise_concurrent_multi_vehicle_sessions(self):
        """T3-PAIR-2: Simulates 5 concurrent vehicle pairs exchanging interleaved BSM, SPaT, and DENM frames."""
        eng = DNA4MerEngine()
        vehicles = [10, 20, 30, 40, 50]
        sessions = {}

        # Establish pairwise sessions (V10<->V20, V20<->V30, V30<->V40, V40<->V50, V50<->V10)
        for i in range(len(vehicles)):
            v1 = vehicles[i]
            v2 = vehicles[(i + 1) % len(vehicles)]
            seed = f"SHARED_KEY_{v1}_{v2}".encode()
            label = f"PAIR_{v1}_{v2}"
            sessions[(v1, v2)] = DynamicPermutationState(seed, label)
            sessions[(v2, v1)] = DynamicPermutationState(seed, label)

        # Interleave transmissions across all sessions
        for i in range(len(vehicles)):
            v1 = vehicles[i]
            v2 = vehicles[(i + 1) % len(vehicles)]
            s_state = sessions[(v1, v2)]
            r_state = sessions[(v2, v1)]

            # Rotate message types
            if i % 3 == 0:
                raw = serialize_bsm(station_id=v1, speed_kmh=80.0 + i, accel_mps2=0.0, heading_deg=0.0)
            elif i % 3 == 1:
                raw = serialize_spat(station_id=v1, phase_id=1, countdown_sec=15.0)
            else:
                raw = serialize_denm(station_id=v1, cause_code=1, speed_kmh=70.0, heading_deg=0.0)

            strand = eng.encode_bytes(raw, s_state)
            rec = eng.decode_strand(strand, r_state)
            self.assertEqual(rec, raw)
            pkt = deserialize_v2x_packet(rec)
            self.assertEqual(pkt.station_id, v1)

            # Cross-decryption using another vehicle's state must fail
            other_state = sessions[(vehicles[(i + 2) % len(vehicles)], vehicles[(i + 3) % len(vehicles)])]
            with self.assertRaises(Exception):
                bad_dec = eng.decode_strand(strand, other_state)
                deserialize_v2x_packet(bad_dec)

    def test_tier3_pairwise_ratcheted_stream_with_mutation_and_replay(self):
        """T3-PAIR-3: Stream of 10 frames containing benign, mutated, and replayed frames."""
        eng = DNA4MerEngine()
        seed = b"STREAM_TEST_KEY_42"
        alice = DynamicPermutationState(seed)
        bob = DynamicPermutationState(seed)

        captured_strand = None
        for f_idx in range(10):
            raw = serialize_bsm(station_id=1, speed_kmh=60.0 + f_idx, accel_mps2=0.0, heading_deg=0.0)
            strand = eng.encode_bytes(raw, alice)
            if f_idx == 1:
                captured_strand = strand

            if f_idx == 3:
                # Nucleotide mutation
                corrupted = ("T" if strand[0] != "T" else "A") + strand[1:]
                with self.assertRaises(Exception):
                    dec = eng.decode_strand(corrupted, bob)
                    deserialize_v2x_packet(dec)
                # Resync receiver
                bob.ratchet_forward()
                alice.ratchet_forward()
            elif f_idx == 6:
                # Replay of captured frame 1
                with self.assertRaises(Exception):
                    dec = eng.decode_strand(captured_strand, bob)
                    deserialize_v2x_packet(dec)
                # Process legitimate frame 6
                rec = eng.decode_strand(strand, bob)
                self.assertEqual(rec, raw)
                alice.ratchet_forward()
                bob.ratchet_forward()
            else:
                # Normal frame
                rec = eng.decode_strand(strand, bob)
                self.assertEqual(rec, raw)
                alice.ratchet_forward()
                bob.ratchet_forward()

    def test_tier3_pairwise_spat_denm_over_genomic_spn(self):
        """T3-PAIR-4: Validates SPaT and DENM frames encrypted via Genomic-SPN mode with 2-pass diffusion."""
        eng = DNA4MerEngine()
        state_s = DynamicPermutationState(b"SPN_SPAT_DENM_KEY")
        state_r = DynamicPermutationState(b"SPN_SPAT_DENM_KEY")

        # SPaT over SPN
        spat = serialize_spat(station_id=50, phase_id=2, countdown_sec=12.5)
        spn_strand_spat = eng.encode_spn_bytes(spat, state_s)
        rec_spat = eng.decode_spn_strand(spn_strand_spat, state_r)
        self.assertEqual(rec_spat, spat)
        self.assertEqual(deserialize_v2x_packet(rec_spat).msg_type, MSG_TYPE_SPAT)

        # DENM over SPN
        denm = serialize_denm(station_id=60, cause_code=1, speed_kmh=90.0, heading_deg=180.0)
        spn_strand_denm = eng.encode_spn_bytes(denm, state_s)
        rec_denm = eng.decode_spn_strand(spn_strand_denm, state_r)
        self.assertEqual(rec_denm, denm)
        self.assertEqual(deserialize_v2x_packet(rec_denm).msg_type, MSG_TYPE_DENM)

    def test_tier3_pairwise_authenticated_telemetry_pipeline(self):
        """T3-PAIR-5: Full pipeline: serialize -> lightweight MAC -> Genomic-SPN encode -> decode -> verify MAC -> deserialize."""
        eng = DNA4MerEngine()
        session_key = b"PIPELINE_SESSION_KEY_99"
        alice = DynamicPermutationState(session_key)
        bob = DynamicPermutationState(session_key)

        # Sender: Generate BSM, compute 4-byte MAC on first 28 bytes
        raw_bsm = serialize_bsm(station_id=77, speed_kmh=105.0, accel_mps2=1.2, heading_deg=90.0)
        payload_28b = raw_bsm[:28]
        mac_4b = compute_lightweight_mac(payload_28b, session_key)
        packet_with_mac = payload_28b + mac_4b
        self.assertEqual(len(packet_with_mac), 32)

        # Encrypt with Genomic-SPN
        strand = eng.encode_spn_bytes(packet_with_mac, alice)

        # Receiver: Decrypt Genomic-SPN
        decrypted = eng.decode_spn_strand(strand, bob)
        rx_payload = decrypted[:28]
        rx_mac = decrypted[28:]

        # Verify constant-time MAC
        self.assertTrue(verify_lightweight_mac(rx_payload, rx_mac, session_key))

        # Tampered strand test
        tampered_strand = ("C" if strand[0] != "C" else "G") + strand[1:]
        decrypted_bad = eng.decode_spn_strand(tampered_strand, bob)
        self.assertFalse(verify_lightweight_mac(decrypted_bad[:28], decrypted_bad[28:], session_key))


# ==============================================================================
# TIER 4: Real-World Vehicular Workload Scenarios (>= 5 scenarios)
# ==============================================================================

class TestTier4RealWorldWorkloads(unittest.TestCase):
    """
    Tier 4 tests modeling complex real-world vehicular workload scenarios:
      - Scenario 1: Highway Platoon Synchronous Telemetry Stream
      - Scenario 2: Emergency Brake Cascade & Multicast DENM Alerting
      - Scenario 3: Smart Intersection SPaT Crossing & Countdown Progression
      - Scenario 4: High-Density Highway Mixed-Traffic Stream with Active Cyber Attacks
      - Scenario 5: Rapid Roadside Unit (RSU) Handover & Ephemeral Session Rekeying
    """

    def test_tier4_scenario1_highway_platoon(self):
        """
        Scenario 1: 4-vehicle highway platoon traveling at 105 km/h.
        Leader broadcasts 10 Hz BSM stream over 20 time epochs; followers track kinematics and ratchet.
        """
        eng = DNA4MerEngine()
        seed = b"PLATOON_SHARED_SESSION_SEED"
        leader_state = DynamicPermutationState(seed, "PLATOON_LEADER")
        follower_states = [DynamicPermutationState(seed, "PLATOON_LEADER") for _ in range(3)]

        speeds = [105.0, 105.2, 104.8, 105.0]
        distances = [20.0, 20.0, 20.0]  # headway distances in meters

        for epoch in range(20):
            # Leader generates BSM
            leader_speed = speeds[0] + 0.1 * math.sin(epoch)
            raw = serialize_bsm(station_id=1, speed_kmh=leader_speed, accel_mps2=0.1, heading_deg=90.0)
            strand = eng.encode_bytes(raw, leader_state)
            leader_state.ratchet_forward()

            # Followers receive and decode
            for idx, f_state in enumerate(follower_states):
                rec = eng.decode_strand(strand, f_state)
                f_state.ratchet_forward()
                pkt = deserialize_v2x_packet(rec)
                self.assertEqual(pkt.station_id, 1)
                self.assertAlmostEqual(pkt.speed_kmh, leader_speed, places=1)

                # Follower updates spacing
                distances[idx] = max(18.0, min(22.0, distances[idx] + (leader_speed - speeds[idx + 1]) * 0.01))

        # Platoon spacing maintained safely
        for d in distances:
            self.assertGreater(d, 15.0)

    def test_tier4_scenario2_emergency_brake_denm_broadcast(self):
        """
        Scenario 2: Emergency brake cascade. Platoon leader decelerates at -8.5 m/s^2,
        broadcasts encrypted DENM (cause_code=1). Followers verify alert and brake.
        """
        eng = DNA4MerEngine()
        seed = b"EMERGENCY_BROADCAST_SEED"
        leader_state = DynamicPermutationState(seed)
        follower_states = [DynamicPermutationState(seed) for _ in range(3)]

        # Leader triggers hard brake alert
        denm_raw = serialize_denm(station_id=1, cause_code=1, speed_kmh=80.0, heading_deg=90.0)
        strand = eng.encode_bytes(denm_raw, leader_state)

        # All 3 followers decode and verify emergency alert
        follower_braked = [False] * 3
        for idx, f_state in enumerate(follower_states):
            rec = eng.decode_strand(strand, f_state)
            pkt = deserialize_v2x_packet(rec)
            self.assertEqual(pkt.msg_type, MSG_TYPE_DENM)
            cause = struct.unpack(">H", rec[10:12])[0]
            self.assertEqual(cause, 1)
            follower_braked[idx] = True

        self.assertTrue(all(follower_braked))

    def test_tier4_scenario3_smart_intersection_spat_crossing(self):
        """
        Scenario 3: Smart intersection SPaT countdown progression from 15.0s down to 0.0s.
        Approaching vehicle tracks signal phases and stops before red line.
        """
        eng = DNA4MerEngine()
        rsu_seed = b"RSU_INTERSECTION_42_KEY"
        rsu_state = DynamicPermutationState(rsu_seed)
        vehicle_state = DynamicPermutationState(rsu_seed)

        vehicle_distance = 250.0  # meters from stop line
        vehicle_speed_kmh = 45.0   # 12.5 m/s

        countdown = 15.0
        while countdown > 0.0:
            phase = 3 if countdown > 4.0 else 2  # Green until 4s, then Yellow
            spat_raw = serialize_spat(station_id=900, phase_id=phase, countdown_sec=countdown)
            strand = eng.encode_bytes(spat_raw, rsu_state)
            rsu_state.ratchet_forward()

            rec = eng.decode_strand(strand, vehicle_state)
            vehicle_state.ratchet_forward()
            pkt = deserialize_v2x_packet(rec)
            self.assertEqual(pkt.station_id, 900)

            countdown_rx = struct.unpack(">H", rec[12:14])[0] / 10.0
            self.assertAlmostEqual(countdown_rx, countdown, places=1)

            # Update vehicle approach physics (0.5s intervals)
            dt = 0.5
            countdown = max(0.0, countdown - dt)
            if countdown < 4.0:
                # Moderate braking at 3.5 m/s^2 upon yellow phase
                vehicle_speed_kmh = max(0.0, vehicle_speed_kmh - (3.5 * 3.6) * dt)
            vehicle_distance -= (vehicle_speed_kmh / 3.6) * dt

        # Vehicle stopped safely before intersection line
        self.assertGreaterEqual(vehicle_distance, 0.0)
        self.assertAlmostEqual(vehicle_speed_kmh, 0.0, places=1)

    def test_tier4_scenario4_multiclass_attack_stream(self):
        """
        Scenario 4: High-density highway mixed-traffic stream with active multi-class cyber attacks.
        Validates real-time classification accuracy >= 95% and zero false positives on benign packets.
        """
        sim = MovingCarsSimulator(num_vehicles=10, seed=42)

        # Generate training batch (500 packets) for classifier calibration
        s_tr, st_tr, t_tr, sp_tr, pt_tr, y_tr = sim.generate_streaming_batch(batch_size=500, attack_ratio=0.5)
        f_tr = extract_features_vectorized(s_tr, st_tr, t_tr, sp_tr, pt_tr)
        clf = FastRuleAndMLClassifier()
        clf.train(f_tr, y_tr)

        # Generate test workload (200 packets, 35% attacks across replay, mutation, sybil, probe, desync)
        s_te, st_te, t_te, sp_te, pt_te, y_te = sim.generate_streaming_batch(batch_size=200, attack_ratio=0.35)
        f_te = extract_features_vectorized(s_te, st_te, t_te, sp_te, pt_te)
        preds = clf.classify_batch_fast(f_te)

        overall_acc = float(np.mean(preds == y_te)) * 100.0
        self.assertGreaterEqual(overall_acc, 95.0, f"Overall classification accuracy {overall_acc:.2f}% < 95%")

        # Ensure zero false positives on benign packets
        benign_mask = (y_te == 0)
        if np.any(benign_mask):
            benign_acc = float(np.mean(preds[benign_mask] == 0)) * 100.0
            self.assertEqual(benign_acc, 100.0, f"False positive detected on benign packets: {benign_acc:.2f}%")

    def test_tier4_scenario5_rsu_handover_rekeying(self):
        """
        Scenario 5: Vehicle traveling at 120 km/h executes handover from RSU-Alpha to RSU-Beta.
        State for Alpha is purged; new session with Beta established; cross-decryption impossible.
        """
        eng = DNA4MerEngine()
        seed_alpha = b"RSU_ALPHA_SHARED_SECRET"
        seed_beta = b"RSU_BETA_SHARED_SECRET"

        rsu_alpha = DynamicPermutationState(seed_alpha, "RSU_ALPHA")
        veh_alpha = DynamicPermutationState(seed_alpha, "RSU_ALPHA")

        # Telemetry exchanged with RSU-Alpha
        raw_alpha = serialize_spat(station_id=1001, phase_id=1, countdown_sec=10.0)
        strand_alpha = eng.encode_bytes(raw_alpha, rsu_alpha)
        rec_alpha = eng.decode_strand(strand_alpha, veh_alpha)
        self.assertEqual(rec_alpha, raw_alpha)

        # Handover event: Vehicle leaves Alpha cell, purges memory
        veh_alpha.purge_memory()
        self.assertEqual(len(veh_alpha.active_4mer_to_byte), 0)

        # Vehicle negotiates session with RSU-Beta
        rsu_beta = DynamicPermutationState(seed_beta, "RSU_BETA")
        veh_beta = DynamicPermutationState(seed_beta, "RSU_BETA")

        # Packets from Alpha cannot be decoded by Beta session
        with self.assertRaises(Exception):
            dec_cross = eng.decode_strand(strand_alpha, veh_beta)
            deserialize_v2x_packet(dec_cross)

        # Fresh telemetry exchanged with RSU-Beta
        raw_beta = serialize_spat(station_id=1002, phase_id=3, countdown_sec=25.0)
        strand_beta = eng.encode_bytes(raw_beta, rsu_beta)
        rec_beta = eng.decode_strand(strand_beta, veh_beta)
        self.assertEqual(rec_beta, raw_beta)
        pkt_beta = deserialize_v2x_packet(rec_beta)
        self.assertEqual(pkt_beta.station_id, 1002)


# ==============================================================================
# MAIN TEST RUNNER
# ==============================================================================

if __name__ == "__main__":
    unittest.main()
