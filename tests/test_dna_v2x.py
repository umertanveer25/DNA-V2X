"""
Comprehensive Unit Test Suite for DNA-V2X Engine, Telemetry Schemas, Attack Simulator, and Benchmarks.
"""

import unittest
import numpy as np
import time

from src.dna_4mer_engine import (
    ALL_256_4MERS,
    DynamicPermutationState,
    DNA4MerEngine,
    BASES
)
from src.v2x_telemetry_schema import (
    serialize_bsm,
    serialize_cam,
    serialize_spat,
    serialize_denm,
    deserialize_v2x_packet,
    MSG_TYPE_BSM,
    MSG_TYPE_CAM,
    MSG_TYPE_SPAT,
    MSG_TYPE_DENM
)
from src.attack_simulator import (
    AttackSimulator,
    AttackResult
)
from src.energy_profiler import EnergyProfiler
from benchmarks.baseline_ciphers import BaselineCiphers


class TestDNA4MerEngine(unittest.TestCase):
    def setUp(self):
        self.engine = DNA4MerEngine()
        self.seed_alice = b"OBUSHAREDSECRET1"
        self.seed_bob = b"OBUSHAREDSECRET1"
        self.state_alice = DynamicPermutationState(self.seed_alice, "PAIR_V2V_1001_1002")
        self.state_bob = DynamicPermutationState(self.seed_bob, "PAIR_V2V_1001_1002")

    def test_canonical_universe(self):
        """Verify the 4-mer universe contains exactly 256 unique 4-character codons."""
        self.assertEqual(len(ALL_256_4MERS), 256)
        self.assertEqual(len(set(ALL_256_4MERS)), 256)
        for codon in ALL_256_4MERS:
            self.assertEqual(len(codon), 4)
            for char in codon:
                self.assertIn(char, BASES)

    def test_permutation_bijection(self):
        """Verify dynamic state creates a strictly bijective 1:1 mapping between 0-255 and 256 4-mers."""
        self.assertEqual(len(self.state_alice.active_byte_to_4mer), 256)
        self.assertEqual(len(set(self.state_alice.active_byte_to_4mer)), 256)
        self.assertEqual(len(self.state_alice.active_4mer_to_byte), 256)

        # Invertibility check
        for b in range(256):
            codon = self.state_alice.active_byte_to_4mer[b]
            recovered_b = self.state_alice.active_4mer_to_byte[codon]
            self.assertEqual(b, recovered_b)

    def test_symmetric_encoding_decoding(self):
        """Verify Alice can encode arbitrary telemetry bytes and Bob correctly decodes them."""
        raw_telemetry = serialize_bsm(
            station_id=101,
            speed_kmh=88.5,
            accel_mps2=-2.4,
            heading_deg=180.0,
            latitude=37.7749,
            longitude=-122.4194,
            elevation_m=12.0,
            brake_active=1
        )
        self.assertEqual(len(raw_telemetry), 32)

        strand = self.engine.encode_bytes(raw_telemetry, self.state_alice)
        self.assertEqual(len(strand), 128)  # 32 bytes * 4 nucleotides

        decoded_bytes = self.engine.decode_strand(strand, self.state_bob)
        self.assertEqual(raw_telemetry, decoded_bytes)

        # Deserialize and verify parsed packet
        packet = deserialize_v2x_packet(decoded_bytes)
        self.assertEqual(packet.station_id, 101)
        self.assertAlmostEqual(packet.speed_kmh, 88.5, places=1)
        self.assertAlmostEqual(packet.accel_mps2, -2.4, places=1)
        self.assertEqual(packet.safety_bitmask & 1, 1)

    def test_forward_ratchet_pfs(self):
        """Verify ratchet evolution alters cipher dictionary across consecutive frames."""
        raw_data = b"VEHICLE_CRITICAL_TELEMETRY_DATA!"  # 32 bytes
        strand_f0 = self.engine.encode_bytes(raw_data, self.state_alice)

        # Ratchet forward on Alice and Bob
        self.state_alice.ratchet_forward()
        self.state_bob.ratchet_forward()

        strand_f1 = self.engine.encode_bytes(raw_data, self.state_alice)

        # Ciphertexts for identical telemetry must differ completely
        self.assertNotEqual(strand_f0, strand_f1)

        # Bob at frame 1 correctly decodes frame 1 strand
        decoded_f1 = self.engine.decode_strand(strand_f1, self.state_bob)
        self.assertEqual(raw_data, decoded_f1)

        # An attacker using frame 0 state cannot decode frame 1 strand
        state_eavesdropper_f0 = DynamicPermutationState(self.seed_alice, "PAIR_V2V_1001_1002")
        with self.assertRaises(Exception):
            dec = self.engine.decode_strand(strand_f1, state_eavesdropper_f0)
            deserialize_v2x_packet(dec)

    def test_memory_purge(self):
        """Verify secure RAM zero-fill purge."""
        self.state_alice.purge_memory()
        self.assertEqual(len(self.state_alice.active_4mer_to_byte), 0)
        self.assertEqual(self.state_alice.active_byte_to_4mer[0], "AAAA")

    def test_shannon_entropy(self):
        """Verify entropy calculation approaches 8.0 bits/byte on uniform payloads."""
        # 256 unique bytes
        full_spectrum = bytes(range(256))
        strand = self.engine.encode_bytes(full_spectrum, self.state_alice)
        entropy = self.engine.calculate_shannon_entropy(strand)
        self.assertAlmostEqual(entropy, 8.0, places=2)

        # Base frequencies should be uniform (0.25 each)
        freqs = self.engine.calculate_base_frequencies(strand)
        for base in BASES:
            self.assertAlmostEqual(freqs[base], 0.25, places=2)

    def test_genomic_spn_invertibility_and_avalanche(self):
        """Verify Genomic-SPN exact decoding invertibility and >40% avalanche nucleotide diffusion."""
        payload1 = b"VEHICLE_CRITICAL_TELEMETRY_0123!"  # 32 bytes
        # Flip exactly 1 bit in the last byte
        payload2 = bytearray(payload1)
        payload2[-1] ^= 0x01
        payload2 = bytes(payload2)

        strand1 = self.engine.encode_spn_bytes(payload1, self.state_alice)
        strand2 = self.engine.encode_spn_bytes(payload2, self.state_alice)

        # Invertibility check
        recovered1 = self.engine.decode_spn_strand(strand1, self.state_bob)
        recovered2 = self.engine.decode_spn_strand(strand2, self.state_bob)
        self.assertEqual(payload1, recovered1)
        self.assertEqual(payload2, recovered2)

        # Avalanche check: count differing nucleotides
        diff_count = sum(1 for c1, c2 in zip(strand1, strand2) if c1 != c2)
        diff_ratio = diff_count / len(strand1)
        self.assertGreaterEqual(diff_ratio, 0.40, f"Avalanche ratio too low: {diff_ratio:.2%}")

    def test_physical_entropy_ratchet(self):
        """Verify cross-layer physical entropy alters forward ratchet evolution."""
        csi_antenna_state_1 = b"RF_CSI_MULTIPATH_ESTIMATE_VEHICLE_A"
        csi_antenna_state_2 = b"RF_CSI_MULTIPATH_ESTIMATE_VEHICLE_B"

        state_1 = DynamicPermutationState(b"SHARED_MASTER_SEED")
        state_2 = DynamicPermutationState(b"SHARED_MASTER_SEED")

        # Ratchet with matching physical entropy
        state_1.ratchet_forward(physical_entropy=csi_antenna_state_1)
        state_2.ratchet_forward(physical_entropy=csi_antenna_state_1)
        self.assertEqual(state_1.master_seed, state_2.master_seed)

        # Ratchet with mismatched physical entropy
        state_2.ratchet_forward(physical_entropy=csi_antenna_state_2)
        state_1.ratchet_forward(physical_entropy=csi_antenna_state_1)
        self.assertNotEqual(state_1.master_seed, state_2.master_seed)



class TestV2XSchemas(unittest.TestCase):
    def test_all_message_types_serialization(self):
        """Verify BSM, CAM, SPaT, and DENM serialization and CRC verification."""
        # BSM
        bsm_bytes = serialize_bsm(station_id=1, speed_kmh=60.0, accel_mps2=1.2, heading_deg=90.0)
        pkt_bsm = deserialize_v2x_packet(bsm_bytes)
        self.assertEqual(pkt_bsm.msg_type, MSG_TYPE_BSM)

        # CAM
        cam_bytes = serialize_cam(station_id=2, speed_kmh=45.0, accel_mps2=0.0, heading_deg=270.0, hazard_lights=1)
        pkt_cam = deserialize_v2x_packet(cam_bytes)
        self.assertEqual(pkt_cam.msg_type, MSG_TYPE_CAM)

        # SPaT
        spat_bytes = serialize_spat(station_id=3, phase_id=3, countdown_sec=14.5)
        pkt_spat = deserialize_v2x_packet(spat_bytes)
        self.assertEqual(pkt_spat.msg_type, MSG_TYPE_SPAT)

        # DENM
        denm_bytes = serialize_denm(station_id=4, cause_code=1, speed_kmh=100.0, heading_deg=0.0)
        pkt_denm = deserialize_v2x_packet(denm_bytes)
        self.assertEqual(pkt_denm.msg_type, MSG_TYPE_DENM)

    def test_corrupted_crc_detection(self):
        """Verify corrupted bytes fail deserialization."""
        bsm_bytes = serialize_bsm(station_id=1, speed_kmh=60.0, accel_mps2=1.2, heading_deg=90.0)
        corrupted = bytearray(bsm_bytes)
        corrupted[5] ^= 0xFF  # Flip bits
        with self.assertRaises(ValueError):
            deserialize_v2x_packet(bytes(corrupted))

    def test_lightweight_mac_verification(self):
        """Verify constant-time 4-byte lightweight MAC computation and verification."""
        from src.v2x_telemetry_schema import compute_lightweight_mac, verify_lightweight_mac
        payload = b"PAYLOAD_28_BYTES_TESTING_01!"
        key = b"SYMMETRIC_SESSION_KEY_01"
        mac = compute_lightweight_mac(payload, key)
        self.assertEqual(len(mac), 4)
        self.assertTrue(verify_lightweight_mac(payload, mac, key))
        self.assertFalse(verify_lightweight_mac(payload, b"WRNG", key))
        self.assertFalse(verify_lightweight_mac(b"MODIFIED_PAYLOAD_28_BYTES_01", mac, key))


class TestAttackSimulator(unittest.TestCase):
    def setUp(self):
        self.simulator = AttackSimulator()

    def test_replay_attack_detection(self):
        res = self.simulator.test_replay_attack(num_trials=50, delay_frames=3)
        self.assertEqual(res.detection_rate_pct, 100.0)
        self.assertEqual(res.successful_breaches, 0)

    def test_mutation_attack_detection(self):
        res = self.simulator.test_mutation_tamper_attack(num_trials=50, num_mutations=1)
        self.assertEqual(res.detection_rate_pct, 100.0)
        self.assertEqual(res.successful_breaches, 0)

    def test_frequency_analysis_defense(self):
        res = self.simulator.test_frequency_analysis_attack(num_packets=1000)
        self.assertEqual(res.detection_rate_pct, 100.0)
        self.assertGreater(res.details["shannon_entropy_bits"], 7.8)

    def test_sybil_injection_detection(self):
        res = self.simulator.test_sybil_ghost_injection(num_trials=50)
        self.assertEqual(res.detection_rate_pct, 100.0)
        self.assertEqual(res.successful_breaches, 0)


class TestBaselinesAndProfiler(unittest.TestCase):
    def test_all_baselines(self):
        bc = BaselineCiphers()
        data = serialize_bsm(1, 50.0, 0.0, 90.0)

        # DNA-V2X
        c_dna = bc.encrypt_dna_v2x(data)
        self.assertEqual(bc.decrypt_dna_v2x(c_dna), data)

        # AES-GCM
        c_aes = bc.encrypt_aes_gcm(data)
        self.assertEqual(bc.decrypt_aes_gcm(c_aes), data)

        # ChaCha20
        c_chacha = bc.encrypt_chacha20(data)
        self.assertEqual(bc.decrypt_chacha20(c_chacha), data)

        # ECDSA
        c_ecdsa = bc.sign_ecdsa(data)
        self.assertEqual(bc.verify_ecdsa(c_ecdsa), data)

        # Static DNA
        c_sdna = bc.encrypt_static_dna(data)
        self.assertEqual(bc.decrypt_static_dna(c_sdna), data)

        # Plaintext
        c_pt = bc.encrypt_plaintext(data)
        self.assertEqual(bc.decrypt_plaintext(c_pt), data)

    def test_energy_profiler(self):
        profiler = EnergyProfiler(power_watt_rating=2.5)
        self.assertAlmostEqual(profiler.power_watt, 2.5, places=1)
        # 10 microseconds at 2.5W -> 25 uJ
        metrics = profiler.profile_algorithm(
            "Test",
            lambda p: p,
            lambda c: c,
            b"test" * 8,
            iterations=50
        )
        self.assertGreater(metrics.throughput_pkts_sec, 0)



if __name__ == "__main__":
    unittest.main()
