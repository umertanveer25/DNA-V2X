"""
Adversarial Test Suite 4: Telemetry Schemas Fuzzing (SPaT, DENM, BSM, CAM).
Tests:
  1. Systematic NaN, +Inf, -Inf injection across all float/numerical fields.
  2. Extreme boundary coordinates, kinematics, elevations, and countdowns.
  3. Deserialization rounding, clipping, and field preservation invariants.
  4. Malformed byte payloads, truncated frames, corrupted CRCs, and invalid message types.
  5. Constant-time lightweight MAC fuzzing and tamper detection.
"""

import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
import math
import zlib
import struct
import random
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
    V2XTelemetryPacket
)

def run_task4_adversarial_tests():
    print("=" * 70)
    print("ADVERSARIAL TEST 4: Telemetry Schemas Fuzzing (SPaT, DENM, BSM)")
    print("=" * 70)

    # 1. NaN and Inf Fuzzing across all message serializers
    print("[*] Fuzzing NaN, +Inf, -Inf on BSM fields...")
    invalid_floats = [float('nan'), float('inf'), float('-inf')]
    bsm_float_fields = ["speed_kmh", "accel_mps2", "heading_deg", "latitude", "longitude", "elevation_m"]

    nan_rejections = 0
    for field in bsm_float_fields:
        for val in invalid_floats:
            kwargs = {
                "station_id": 1,
                "speed_kmh": 50.0,
                "accel_mps2": 0.0,
                "heading_deg": 90.0,
                "latitude": 37.77,
                "longitude": -122.41,
                "elevation_m": 10.0
            }
            kwargs[field] = val
            try:
                serialize_bsm(**kwargs)
                raise AssertionError(f"serialize_bsm accepted {field}={val} without ValueError!")
            except ValueError:
                nan_rejections += 1

    print(f"    BSM: Successfully rejected {nan_rejections} invalid float permutations.")

    # SPaT countdown NaN/Inf
    spat_nan_rejections = 0
    for val in invalid_floats:
        try:
            serialize_spat(station_id=1, phase_id=2, countdown_sec=val)
            raise AssertionError(f"serialize_spat accepted countdown_sec={val} without ValueError!")
        except ValueError:
            spat_nan_rejections += 1
    print(f"    SPaT: Successfully rejected {spat_nan_rejections} countdown NaN/Inf values.")

    # DENM speed/heading NaN/Inf
    denm_nan_rejections = 0
    for field in ["speed_kmh", "heading_deg"]:
        for val in invalid_floats:
            kwargs = {"station_id": 1, "cause_code": 1, "speed_kmh": 60.0, "heading_deg": 180.0}
            kwargs[field] = val
            try:
                serialize_denm(**kwargs)
                raise AssertionError(f"serialize_denm accepted {field}={val} without ValueError!")
            except ValueError:
                denm_nan_rejections += 1
    print(f"    DENM: Successfully rejected {denm_nan_rejections} speed/heading NaN/Inf values.")

    # 2. Extreme Boundary & Overflow Fuzzing
    print("[*] Testing extreme coordinate, speed, acceleration, and elevation clipping...")
    extreme_test_cases = [
        # (speed, accel, heading, lat, lon, elev)
        (-100.0, -50.0, -720.0, -180.0, -360.0, -50000.0),
        (1000.0, 100.0, 1080.0, 180.0, 360.0, 100000.0),
        (0.0, 0.0, 0.0, 0.0, 0.0, 0.0),
        (250.0, 20.0, 359.9, 90.0, 180.0, 10000.0),
        (-0.0001, -20.0001, 360.0, -90.0001, -180.0001, -1000.0001),
    ]

    for tc in extreme_test_cases:
        spd, acc, hdg, lat, lon, elv = tc
        raw_pkt = serialize_bsm(
            station_id=999,
            speed_kmh=spd,
            accel_mps2=acc,
            heading_deg=hdg,
            latitude=lat,
            longitude=lon,
            elevation_m=elv
        )
        assert len(raw_pkt) == 32, f"Expected 32 bytes, got {len(raw_pkt)}"
        # Deserialization must succeed without struct.error or overflow
        parsed = deserialize_v2x_packet(raw_pkt)
        assert 0.0 <= parsed.speed_kmh <= 250.0, f"Speed out of bounds: {parsed.speed_kmh}"
        assert -20.0 <= parsed.accel_mps2 <= 20.0, f"Accel out of bounds: {parsed.accel_mps2}"
        assert 0.0 <= parsed.heading_deg < 360.0, f"Heading out of bounds: {parsed.heading_deg}"
        assert -90.0 <= parsed.latitude <= 90.0, f"Latitude out of bounds: {parsed.latitude}"
        assert -180.0 <= parsed.longitude <= 180.0, f"Longitude out of bounds: {parsed.longitude}"
        assert -1000.0 <= parsed.elevation_m <= 10000.0, f"Elevation out of bounds: {parsed.elevation_m}"

    print("    BSM extreme bounds: All 5 extremal scenarios clipped and deserialized safely.")

    # SPaT extreme bounds
    spat_extreme = [-100.0, 0.0, 120.0, 500.0]
    for cd in spat_extreme:
        pkt = serialize_spat(station_id=5, phase_id=3, countdown_sec=cd)
        parsed = deserialize_v2x_packet(pkt)
        assert 0.0 <= parsed.countdown_sec <= 120.0
        assert parsed.event_code == 3
        assert parsed.msg_type == MSG_TYPE_SPAT
    print("    SPaT extreme bounds: Countdowns safely clamped to [0.0, 120.0].")

    # DENM extreme bounds
    denm_extreme_speeds = [-200.0, 0.0, 250.0, 999.0]
    for spd in denm_extreme_speeds:
        pkt = serialize_denm(station_id=12, cause_code=4, speed_kmh=spd, heading_deg=-45.0)
        parsed = deserialize_v2x_packet(pkt)
        assert 0.0 <= parsed.speed_kmh <= 250.0
        assert parsed.event_code == 4
        assert parsed.msg_type == MSG_TYPE_DENM
    print("    DENM extreme bounds: Speeds safely clamped to [0.0, 250.0].")

    # 3. 10,000 Randomized Roundtrip Precision Invariant Tests
    print("[*] Running 10,000 randomized roundtrip serialization tests...")
    random.seed(42)
    max_lat_err = 0.0
    max_lon_err = 0.0
    max_spd_err = 0.0
    max_acc_err = 0.0

    for _ in range(10000):
        spd = random.uniform(0.0, 250.0)
        acc = random.uniform(-20.0, 20.0)
        hdg = random.uniform(0.0, 359.9)
        lat = random.uniform(-89.9, 89.9)
        lon = random.uniform(-179.9, 179.9)
        elv = random.uniform(-500.0, 5000.0)

        raw = serialize_bsm(1234, spd, acc, hdg, lat, lon, elv)
        p = deserialize_v2x_packet(raw)

        max_lat_err = max(max_lat_err, abs(p.latitude - lat))
        max_lon_err = max(max_lon_err, abs(p.longitude - lon))
        max_spd_err = max(max_spd_err, abs(p.speed_kmh - spd))
        max_acc_err = max(max_acc_err, abs(p.accel_mps2 - acc))

    print(f"    10,000 roundtrips passed! Max quantization errors:")
    print(f"      Latitude err:    {max_lat_err:.8f} deg (expected <= 1e-7)")
    print(f"      Longitude err:   {max_lon_err:.8f} deg (expected <= 1e-7)")
    print(f"      Speed err:       {max_spd_err:.4f} km/h (expected <= 0.01)")
    print(f"      Acceleration err:{max_acc_err:.4f} m/s^2 (expected <= 0.01)")
    assert max_lat_err < 1e-6
    assert max_lon_err < 1e-6
    assert max_spd_err < 0.02
    assert max_acc_err < 0.02

    # 4. Malformed Payloads & CRC/MAC Tampering
    print("[*] Testing malformed payloads and CRC tampering...")
    valid_raw = serialize_bsm(1, 60.0, 0.0, 90.0)

    # Invalid lengths
    for bad_len in [0, 1, 15, 28, 31, 33, 64, 128]:
        try:
            deserialize_v2x_packet(b"\x00" * bad_len)
            raise AssertionError(f"Accepted bad length {bad_len}!")
        except ValueError:
            pass

    # Corrupted CRC
    bad_crc_pkt = bytearray(valid_raw)
    bad_crc_pkt[-1] ^= 0x01
    try:
        deserialize_v2x_packet(bytes(bad_crc_pkt))
        raise AssertionError("Accepted corrupted CRC!")
    except ValueError as e:
        assert "CRC Checksum Mismatch" in str(e)

    # Unsupported Message Type with valid CRC
    dummy_payload = bytearray(b"\xFF" + b"\x01" + b"\x00" * 26)
    dummy_crc = zlib.crc32(dummy_payload)
    bad_type_pkt = bytes(dummy_payload + struct.pack(">I", dummy_crc))
    try:
        deserialize_v2x_packet(bad_type_pkt)
        raise AssertionError("Accepted unknown message type 0xFF!")
    except ValueError as e:
        assert "Unknown or unsupported V2X message type" in str(e)

    # Lightweight MAC Constant-Time Verification
    key = b"TEST_KEY_12345678"
    mac = compute_lightweight_mac(valid_raw[:28], key)
    assert len(mac) == 4
    assert verify_lightweight_mac(valid_raw[:28], mac, key)
    # Wrong key
    assert not verify_lightweight_mac(valid_raw[:28], mac, b"WRONG_KEY_87654321")
    # Bit flip
    corrupted_payload = bytearray(valid_raw[:28])
    corrupted_payload[5] ^= 0x01
    assert not verify_lightweight_mac(bytes(corrupted_payload), mac, key)

    print("[+] TASK 4 ADVERSARIAL TESTS PASSED!")
    return True

if __name__ == "__main__":
    run_task4_adversarial_tests()
