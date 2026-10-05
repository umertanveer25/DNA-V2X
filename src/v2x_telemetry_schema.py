"""
Standards-Compliant V2X Telemetry Binary Packet Serializer & Deserializer.
Formats SAE J2735 (BSM / SPaT) and ETSI EN 302 637-2 (CAM / DENM) frames
into compact, zero-copy binary byte buffers for dynamic 4-mer DNA encoding.
"""

import struct
import zlib
import time
from dataclasses import dataclass
from typing import Dict, Any, Tuple


# Protocol Message Types
MSG_TYPE_BSM = 0x01   # SAE J2735 Basic Safety Message
MSG_TYPE_CAM = 0x02   # ETSI Cooperative Awareness Message
MSG_TYPE_SPAT = 0x03  # SAE Signal Phase & Timing
MSG_TYPE_DENM = 0x04  # ETSI Decentralized Hazard Notification
MSG_TYPE_CPM = 0x05   # ETSI Collective Perception Message


@dataclass
class V2XTelemetryPacket:
    msg_type: int
    station_id: int
    timestamp_ms: int
    speed_kmh: float
    accel_mps2: float
    heading_deg: float
    latitude: float
    longitude: float
    elevation_m: float
    safety_bitmask: int
    event_code: int = 0
    raw_payload_bytes: bytes = b""


def serialize_bsm(
    station_id: int,
    speed_kmh: float,
    accel_mps2: float,
    heading_deg: float,
    latitude: float = 37.7749,
    longitude: float = -122.4194,
    elevation_m: float = 15.0,
    brake_active: int = 0,
    abs_active: int = 0,
    timestamp_ms: int = None
) -> bytes:
    """
    Serializes a standard SAE J2735 BSM frame into a 32-byte packed binary format.
    Format:
      - Header: MsgType (uint8), Version (uint8), StationID (uint32), Timestamp (uint32) [10 bytes]
      - Kinematics: Speed (uint16 * 100), Accel (int16 * 100), Heading (uint16 * 10) [6 bytes]
      - Spatial: Latitude (int32 * 1e7), Longitude (int32 * 1e7), Elevation (int16) [10 bytes]
      - Safety: Bitmask (uint16) [2 bytes]
      - Integrity: CRC-32 (uint32) [4 bytes]
      Total = 32 bytes (which maps to exactly 32 4-mers = 128 DNA nucleotides).
    """
    if timestamp_ms is None:
        timestamp_ms = int(time.time() * 1000) & 0xFFFFFFFF

    safety_mask = (1 if brake_active else 0) | ((1 if abs_active else 0) << 1)

    speed_raw = int(max(0.0, min(250.0, speed_kmh)) * 100)
    accel_raw = int(max(-20.0, min(20.0, accel_mps2)) * 100)
    heading_raw = int((heading_deg % 360.0) * 10)
    lat_raw = int(latitude * 1e7)
    lon_raw = int(longitude * 1e7)
    elev_raw = int(elevation_m)

    payload = struct.pack(
        ">BBI I H h H i i h H",
        MSG_TYPE_BSM,
        1,  # Protocol version
        station_id & 0xFFFFFFFF,
        timestamp_ms & 0xFFFFFFFF,
        speed_raw,
        accel_raw,
        heading_raw,
        lat_raw,
        lon_raw,
        elev_raw,
        safety_mask
    )

    # Compute CRC32
    crc = zlib.crc32(payload)
    return payload + struct.pack(">I", crc)


def serialize_cam(
    station_id: int,
    speed_kmh: float,
    accel_mps2: float,
    heading_deg: float,
    latitude: float = 48.8566,
    longitude: float = 2.3522,
    elevation_m: float = 35.0,
    hazard_lights: int = 0,
    timestamp_ms: int = None
) -> bytes:
    """Serializes an ETSI CAM frame into 32-byte packed binary format."""
    if timestamp_ms is None:
        timestamp_ms = int(time.time() * 1000) & 0xFFFFFFFF

    safety_mask = (1 if hazard_lights else 0) << 2

    speed_raw = int(max(0.0, min(250.0, speed_kmh)) * 100)
    accel_raw = int(max(-20.0, min(20.0, accel_mps2)) * 100)
    heading_raw = int((heading_deg % 360.0) * 10)
    lat_raw = int(latitude * 1e7)
    lon_raw = int(longitude * 1e7)
    elev_raw = int(elevation_m)

    payload = struct.pack(
        ">BBI I H h H i i h H",
        MSG_TYPE_CAM,
        2,  # ETSI EN 302 637-2
        station_id & 0xFFFFFFFF,
        timestamp_ms & 0xFFFFFFFF,
        speed_raw,
        accel_raw,
        heading_raw,
        lat_raw,
        lon_raw,
        elev_raw,
        safety_mask
    )
    crc = zlib.crc32(payload)
    return payload + struct.pack(">I", crc)


def serialize_spat(
    station_id: int,
    phase_id: int,  # 1=RED, 2=YELLOW, 3=GREEN, 4=FLASHING
    countdown_sec: float,
    timestamp_ms: int = None
) -> bytes:
    """Serializes an SAE J2735 SPaT intersection signal timing frame."""
    if timestamp_ms is None:
        timestamp_ms = int(time.time() * 1000) & 0xFFFFFFFF

    countdown_raw = int(max(0.0, min(120.0, countdown_sec)) * 10)
    payload = struct.pack(
        ">BBI I H H 12x H",
        MSG_TYPE_SPAT,
        1,
        station_id & 0xFFFFFFFF,
        timestamp_ms & 0xFFFFFFFF,
        phase_id & 0xFFFF,
        countdown_raw,
        0
    )
    crc = zlib.crc32(payload)
    return payload + struct.pack(">I", crc)


def serialize_denm(
    station_id: int,
    cause_code: int,  # 1=HARD_BRAKE, 2=ROAD_HAZARD, 3=BLACK_ICE, 4=ACCIDENT
    speed_kmh: float,
    heading_deg: float,
    timestamp_ms: int = None
) -> bytes:
    """Serializes an ETSI DENM safety hazard alert frame."""
    if timestamp_ms is None:
        timestamp_ms = int(time.time() * 1000) & 0xFFFFFFFF

    speed_raw = int(max(0.0, min(250.0, speed_kmh)) * 100)
    heading_raw = int((heading_deg % 360.0) * 10)

    payload = struct.pack(
        ">BBI I H H H 10x H",
        MSG_TYPE_DENM,
        1,
        station_id & 0xFFFFFFFF,
        timestamp_ms & 0xFFFFFFFF,
        cause_code & 0xFFFF,
        speed_raw,
        heading_raw,
        0
    )
    crc = zlib.crc32(payload)
    return payload + struct.pack(">I", crc)


def deserialize_v2x_packet(raw_bytes: bytes) -> V2XTelemetryPacket:
    """
    Deserializes a 32-byte payload and verifies its internal CRC32 checksum.
    Raises ValueError on CRC mismatch or corrupt buffer.
    """
    if len(raw_bytes) != 32:
        raise ValueError(f"Invalid packet length: {len(raw_bytes)} bytes (expected 32 bytes).")

    payload = raw_bytes[:28]
    expected_crc = struct.unpack(">I", raw_bytes[28:])[0]
    actual_crc = zlib.crc32(payload)

    if actual_crc != expected_crc:
        raise ValueError(f"CRC Checksum Mismatch! Expected {expected_crc:#010x}, calculated {actual_crc:#010x}.")

    msg_type, ver, station_id, ts, spd_raw, acc_raw, hdg_raw, lat_raw, lon_raw, elev_raw, mask = struct.unpack(
        ">BBI I H h H i i h H", payload
    )

    return V2XTelemetryPacket(
        msg_type=msg_type,
        station_id=station_id,
        timestamp_ms=ts,
        speed_kmh=spd_raw / 100.0,
        accel_mps2=acc_raw / 100.0,
        heading_deg=hdg_raw / 10.0,
        latitude=lat_raw / 1e7,
        longitude=lon_raw / 1e7,
        elevation_m=float(elev_raw),
        safety_bitmask=mask,
        raw_payload_bytes=raw_bytes
    )
