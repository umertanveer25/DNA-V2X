# In-Depth Analysis: Schemas, Numerical Robustness, Kinematics & Simulation Physics
**Target Modules**: `src/v2x_telemetry_schema.py`, `src/moving_cars_simulation.py`, `src/attack_simulator.py`  
**Explorer**: Explorer M1_2 (`explorer_m1_2`)  
**Audit Scope**: F-06 (SPaT/DENM Deserialization Layout Corruption), F-07 (Sensor NaN/Inf Handling & Boundary Clipping), F-09 (Intelligent Driver Model Kinematics & Timestamp Stagnation)  
**Date**: 2026-10-08  

---

## 1. Executive Summary

This report delivers the authoritative static, mathematical, behavioral, and empirical analysis of V2X telemetry schemas, numerical input handling, vehicle kinematics, and synthetic attack simulation physics across the `DNA-V2X` repository.

Through line-by-line inspection and active empirical reproduction, three primary architectural and physical vulnerabilities were analyzed and verified:
1. **F-06: SPaT and DENM Deserialization Layout Corruption (`src/v2x_telemetry_schema.py`)**: `deserialize_v2x_packet()` indiscriminately deserializes all 32-byte frames using the SAE J2735 BSM struct format (`>BBI I H h H i i h H`). This causes severe data corruption: for SPaT messages, traffic signal phase IDs are converted into speeds of $0.01\text{ to }0.04\text{ km/h}$, and phase countdown timers are mapped into fake vehicle accelerations. For DENM safety alerts, hazard cause codes become fake vehicle speeds, and genuine vehicle speed is mapped into an extreme acceleration ($100.0\text{ m/s}^2$). Critical fields such as `event_code` and `countdown_sec` are lost.
2. **F-07: Silent Numerical Sensor Corruption on NaN/Inf and Missing Boundary Clipping (`src/v2x_telemetry_schema.py`)**: Python's `min(250.0, float('nan'))` returns `250.0`. When a vehicular wheel-speed sensor fails and produces NaN, `serialize_bsm()` silently packs `25000` ($250.0\text{ km/h}$), falsely broadcasting that a vehicle with an offline sensor is traveling at maximum highway speed. Unbounded inputs for `elevation_m` ($>32767\text{ m}$) cause fatal unhandled `struct.error` exceptions, and `heading_deg = float('nan')` crashes with `ValueError`.
3. **F-09: Complete Absence of Intelligent Driver Model (IDM) Physics & Batch Timestamp Stagnation (`src/moving_cars_simulation.py`)**: Despite claiming to implement the Intelligent Driver Model (IDM), `step_physics()` implements an independent random walk without car-following dynamics, headway calculations, or collision avoidance. Faster following vehicles pass directly through slower lead vehicles without braking. Furthermore, `generate_streaming_batch()` never calls `step_physics()`, freezing all timestamps in a batch of up to 10,000 packets to a single static millisecond value.

Complete, line-numbered patch specifications and regression test suites are detailed below for immediate application by the implementation team.

---

## 2. In-Depth Technical Analysis & Empirical Reproduction

### 2.1 F-06: SPaT and DENM Deserialization Layout Corruption

#### Structural Context
In `src/v2x_telemetry_schema.py`, the serialization routines define protocol-specific payloads:
- `serialize_bsm()`: SAE J2735 Basic Safety Message (packed layout: `>BBI I H h H i i h H` + 4-byte CRC).
- `serialize_cam()`: ETSI EN 302 637-2 CAM (packed layout: `>BBI I H h H i i h H` + 4-byte CRC).
- `serialize_spat()`: SAE J2735 Signal Phase & Timing (packed layout: `>BBI I H H 12x H` + 4-byte CRC).
- `serialize_denm()`: ETSI EN 302 637-2 DENM Hazard Alert (packed layout: `>BBI I H H H 10x H` + 4-byte CRC).

However, `deserialize_v2x_packet()` at line 205–207 unconditionally unpacks `payload` using the BSM structure:
```python
205:     msg_type, ver, station_id, ts, spd_raw, acc_raw, hdg_raw, lat_raw, lon_raw, elev_raw, mask = struct.unpack(
206:         ">BBI I H h H i i h H", payload
207:     )
```

#### Protocol Layout Misalignment Matrix
| Byte Range | Field in SPaT (`serialize_spat`) | Deserialized Field in `deserialize_v2x_packet` | Error Description |
| :--- | :--- | :--- | :--- |
| **0** | `msg_type = 0x03` | `msg_type = 3` | Correct |
| **1** | `ver = 1` | `ver = 1` | Correct |
| **2..5** | `station_id` | `station_id` | Correct |
| **6..9** | `timestamp_ms` | `timestamp_ms` | Correct |
| **10..11** | `phase_id` (uint16) | `spd_raw` (uint16) $\to$ `speed_kmh = spd_raw / 100.0` | **Corrupted**: Phase ID 3 (Green) becomes $0.03\text{ km/h}$. |
| **12..13** | `countdown_raw` (uint16, $0.1\text{ s}$) | `acc_raw` (int16) $\to$ `accel_mps2 = acc_raw / 100.0` | **Corrupted**: Countdown $14.5\text{ s}$ becomes acceleration $1.45\text{ m/s}^2$. |
| **14..15** | Padding byte 0..1 | `hdg_raw` $\to$ `heading_deg = 0.0` | Lost |
| **16..19** | Padding byte 2..5 | `lat_raw` $\to$ `latitude = 0.0` | Lost |
| **20..23** | Padding byte 6..9 | `lon_raw` $\to$ `longitude = 0.0` | Lost |
| **24..25** | Padding byte 10..11 | `elev_raw` $\to$ `elevation_m = 0.0` | Lost |
| **26..27** | `mask = 0` (uint16) | `safety_bitmask = 0` | Matches padding |
| **28..31** | CRC-32 | CRC check | Passes |
| *Field* | *Target Field* | `event_code = 0` | **Omitted**: `phase_id` is never assigned to `event_code`. |
| *Field* | *Target Field* | `countdown_sec = 0.0` | **Omitted**: `countdown_sec` field is completely missing. |

| Byte Range | Field in DENM (`serialize_denm`) | Deserialized Field in `deserialize_v2x_packet` | Error Description |
| :--- | :--- | :--- | :--- |
| **0** | `msg_type = 0x04` | `msg_type = 4` | Correct |
| **10..11** | `cause_code` (uint16) | `spd_raw` $\to$ `speed_kmh = cause_code / 100.0` | **Corrupted**: Cause code 1 (Hard Brake) becomes $0.01\text{ km/h}$. |
| **12..13** | `speed_raw` (uint16) | `acc_raw` $\to$ `accel_mps2 = speed_raw / 100.0` | **Corrupted**: Speed $100.0\text{ km/h}$ becomes acceleration $100.0\text{ m/s}^2$. |
| **14..15** | `heading_raw` (uint16) | `hdg_raw` $\to$ `heading_deg = heading_raw / 10.0` | Correctly aligned |
| *Field* | *Target Field* | `event_code = 0` | **Omitted**: `cause_code` is never assigned to `event_code`. |

#### Empirical Reproduction Output
Executing `serialize_spat(station_id=10, phase_id=3, countdown_sec=14.5)` and `serialize_denm(station_id=20, cause_code=1, speed_kmh=100.0, heading_deg=90.0)` through `deserialize_v2x_packet()` produced:
```
SPaT parsed: speed_kmh=0.03, accel_mps2=1.45, event_code=0
DENM parsed: speed_kmh=0.01, accel_mps2=100.0, event_code=0, heading=90.0
```
**Impact**: Safety applications relying on SPaT cannot read signal phases or countdown times; safety applications reading DENM misread emergency hazard alerts as low-speed vehicles with extreme $100\text{ m/s}^2$ ($10g$) accelerations.

---

### 2.2 F-07: Silent Numerical Sensor Corruption on NaN/Inf & Missing Coordinate Bounds

#### The `min(250.0, nan)` Anomaly
In Python:
```python
>>> x = float('nan')
>>> min(250.0, x)
250.0
>>> max(0.0, min(250.0, x))
250.0
>>> int(max(0.0, min(250.0, x)) * 100)
25000
```
In IEEE 754 floating-point semantics, any comparison involving `NaN` evaluates to `False`. When evaluating `min(a, b)`:
If $a = 250.0$ and $b = \text{NaN}$, Python checks `b < a` (`nan < 250.0`), which evaluates to `False`. Python therefore returns $a = 250.0$.
Consequently, `int(max(0.0, min(250.0, speed_kmh)) * 100)` silently resolves to `25000`.

#### Empirical Reproduction Output
Executing `serialize_bsm(station_id=1, speed_kmh=float('nan'), accel_mps2=0.0, heading_deg=90.0)` produced:
```
Deserialized speed from NaN input: 250.0
```
A stationary or malfunctioning vehicle broadcasting NaN is interpreted by neighboring autonomous vehicles as traveling at $250.0\text{ km/h}$!

#### Unhandled Exceptions on Out-of-Bounds Inputs
1. `elevation_m = 35000.0`:
   Packed into format `h` (signed 16-bit integer, range $[-32768, 32767]$).
   Result: `struct.error: 'h' format requires -32768 <= number <= 32767`.
2. `heading_deg = float('nan')`:
   Line 69 computes `int((heading_deg % 360.0) * 10)`. Since `nan % 360.0` is `nan`, `int(nan)` crashes:
   Result: `ValueError: cannot convert float NaN to integer`.
3. `latitude = 120.0` or `longitude = 200.0`:
   Packed directly into 32-bit integer without clipping to $[-90.0, 90.0]$ and $[-180.0, 180.0]$, transmitting invalid geographical coordinates.

---

### 2.3 F-09: Absence of Intelligent Driver Model (IDM) Physics & Timestamp Stagnation

#### Missing IDM Implementation
Line 81 of `src/moving_cars_simulation.py` claims:
```python
81:     def step_physics(self, dt_sec: float = 0.1):
82:         """Updates kinematic positions and speeds according to Intelligent Driver Model (IDM)."""
```
However, lines 83–93 contain:
```python
83:         self.current_time_ms = (self.current_time_ms + int(dt_sec * 1000)) & 0xFFFFFFFF
84:         for vid, v in self.vehicles.items():
85:             # Acceleration noise
86:             v.accel_mps2 += float(self.rng.uniform(-0.2, 0.2))
87:             v.accel_mps2 = max(-6.0, min(3.0, v.accel_mps2))
88: 
89:             v.speed_kmh += (v.accel_mps2 * dt_sec * 3.6)
90:             v.speed_kmh = max(50.0, min(140.0, v.speed_kmh))
91: 
92:             speed_mps = v.speed_kmh / 3.6
93:             v.pos_x_m = (v.pos_x_m + speed_mps * dt_sec) % self.corridor_length_m
```
This is a 1D Brownian random walk. There is:
- No desired velocity $v_0$
- No safe time headway $T$
- No minimum jam distance $s_0$
- No bumper-to-bumper headway $s$
- No velocity difference $\Delta v = v - v_{lead}$
- No car-following interaction

#### Empirical Reproduction: Ghost Vehicle Collision
A simulation was initialized with Vehicle 1 at $x=50.0\text{ m}$ traveling at $20\text{ km/h}$, and Vehicle 2 at $x=45.0\text{ m}$ traveling at $120\text{ km/h}$ in the same lane:
```
Before physics: veh 1 pos=50.0, veh 2 pos=45.0
After 0.5s: veh 1 pos=57.0, veh 2 pos=61.7
Veh 2 accel: 0.26, speed: 120.3
```
Vehicle 2 accelerated by $+0.26\text{ m/s}^2$ and drove straight through Vehicle 1.

#### Empirical Reproduction: Batch Timestamp Stagnation
In `generate_streaming_batch(batch_size=100)`:
```
Unique cur_times count: 1
Sample cur_times[:5]: [484449325, 484449325, 484449325, 484449325, 484449325]
Sample p_times[:5]:   [484449225, 484449225, 484449225, 484449225, 484449225]
cur_time - p_time delta: 100
```
All 100 packets shared the exact same timestamp. Physics was never stepped during packet generation.

---

## 3. Mathematical Remediation Specifications

### 3.1 Intelligent Driver Model (IDM) Formulation
For vehicle $\alpha$ following lead vehicle $\alpha-1$ in the same highway lane:
The acceleration $\dot{v}_\alpha$ is governed by:
$$\dot{v}_\alpha = a \left[ 1 - \left(\frac{v_\alpha}{v_0}\right)^\delta - \left(\frac{s^*(v_\alpha, \Delta v_\alpha)}{s_\alpha}\right)^2 \right]$$
where:
- $v_\alpha$: current velocity ($\text{m/s}$)
- $v_0$: vehicle-specific desired velocity (calibrated to $[90.0, 130.0]\text{ km/h} \approx [25.0, 36.1]\text{ m/s}$)
- $a = 1.5\text{ m/s}^2$: maximum acceleration
- $b = 2.0\text{ m/s}^2$: comfortable deceleration
- $\delta = 4$: free acceleration exponent
- $s_\alpha$: actual bumper-to-bumper distance to lead vehicle in periodic corridor of length $L$:
  $$s_\alpha = \max\left(0.5, (pos_{\alpha-1} - pos_\alpha) \pmod L - l_{veh}\right)$$
  with vehicle length $l_{veh} = 5.0\text{ m}$
- $\Delta v_\alpha = v_\alpha - v_{\alpha-1}$: closing speed
- $s^*(v_\alpha, \Delta v_\alpha)$: dynamic desired minimum gap:
  $$s^*(v, \Delta v) = s_0 + \max\left(0.0, v \cdot T + \frac{v \cdot \Delta v}{2 \sqrt{a \cdot b}}\right)$$
  with minimum jam distance $s_0 = 2.0\text{ m}$ and safe time headway $T = 1.5\text{ s}$.

When closing at high speed ($\Delta v > 0$), $s^*$ increases dramatically, inducing emergency deceleration up to the physical maximum:
$$a_{clamped} = \max(-6.0, \min(3.0, \dot{v}_\alpha))$$

Testing this model on the scenario where Vehicle 2 ($120\text{ km/h}$) was $5\text{ m}$ behind Vehicle 1 ($20\text{ km/h}$) produced:
$$s^* = 319.29\text{ m},\quad s = 0.5\text{ m},\quad a_{clamped} = -6.00\text{ m/s}^2$$
Vehicle 2 immediately applies maximum emergency braking to avert the collision.

---

## 4. Concrete Line-Numbered Patch Specifications

### 4.1 Target File 1: `src/v2x_telemetry_schema.py`

#### Patch 1.1: Add `import math` and update `V2XTelemetryPacket`
**Target Lines**: 7–14, 24–38
```python
# Insert 'import math' in imports
import math
import struct
import zlib
import time
import hmac
import hashlib
from dataclasses import dataclass
from typing import Dict, Any, Tuple, Optional
```
**Update `V2XTelemetryPacket`** (lines 24–38):
```python
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
    countdown_sec: float = 0.0
    raw_payload_bytes: bytes = b""
```

#### Patch 1.2: Numerical Validation & Boundary Clipping in `serialize_bsm`
**Target Lines**: 62–74
**Replacement**:
```python
    if timestamp_ms is None:
        timestamp_ms = int(time.time() * 1000) & 0xFFFFFFFF

    # Validate finite float values
    for val, name in [
        (speed_kmh, "speed_kmh"),
        (accel_mps2, "accel_mps2"),
        (heading_deg, "heading_deg"),
        (latitude, "latitude"),
        (longitude, "longitude"),
        (elevation_m, "elevation_m"),
    ]:
        if math.isnan(val) or math.isinf(val):
            raise ValueError(f"Invalid telemetry value: {name} cannot be NaN or Inf.")

    safety_mask = (1 if brake_active else 0) | ((1 if abs_active else 0) << 1)

    speed_raw = int(round(max(0.0, min(250.0, speed_kmh)) * 100))
    accel_raw = int(round(max(-20.0, min(20.0, accel_mps2)) * 100))
    heading_raw = int(round((heading_deg % 360.0) * 10))
    lat_clipped = max(-90.0, min(90.0, latitude))
    lon_clipped = max(-180.0, min(180.0, longitude))
    elev_clipped = max(-1000.0, min(10000.0, elevation_m))
    lat_raw = int(round(lat_clipped * 1e7))
    lon_raw = int(round(lon_clipped * 1e7))
    elev_raw = int(round(elev_clipped))
```

#### Patch 1.3: Numerical Validation & Boundary Clipping in `serialize_cam`
**Target Lines**: 106–118
**Replacement**:
```python
    if timestamp_ms is None:
        timestamp_ms = int(time.time() * 1000) & 0xFFFFFFFF

    for val, name in [
        (speed_kmh, "speed_kmh"),
        (accel_mps2, "accel_mps2"),
        (heading_deg, "heading_deg"),
        (latitude, "latitude"),
        (longitude, "longitude"),
        (elevation_m, "elevation_m"),
    ]:
        if math.isnan(val) or math.isinf(val):
            raise ValueError(f"Invalid telemetry value: {name} cannot be NaN or Inf.")

    safety_mask = (1 if hazard_lights else 0) << 2

    speed_raw = int(round(max(0.0, min(250.0, speed_kmh)) * 100))
    accel_raw = int(round(max(-20.0, min(20.0, accel_mps2)) * 100))
    heading_raw = int(round((heading_deg % 360.0) * 10))
    lat_clipped = max(-90.0, min(90.0, latitude))
    lon_clipped = max(-180.0, min(180.0, longitude))
    elev_clipped = max(-1000.0, min(10000.0, elevation_m))
    lat_raw = int(round(lat_clipped * 1e7))
    lon_raw = int(round(lon_clipped * 1e7))
    elev_raw = int(round(elev_clipped))
```

#### Patch 1.4: Validation in `serialize_spat` and `serialize_denm`
**Target Lines**: 142–156 (`serialize_spat`), 169–185 (`serialize_denm`)
**Replacement for `serialize_spat`**:
```python
    if timestamp_ms is None:
        timestamp_ms = int(time.time() * 1000) & 0xFFFFFFFF

    if math.isnan(countdown_sec) or math.isinf(countdown_sec):
        raise ValueError("Invalid telemetry value: countdown_sec cannot be NaN or Inf.")

    countdown_raw = int(round(max(0.0, min(120.0, countdown_sec)) * 10))
    phase_raw = int(phase_id) & 0xFFFF

    payload = struct.pack(
        ">BBI I H H 12x H",
        MSG_TYPE_SPAT,
        1,
        station_id & 0xFFFFFFFF,
        timestamp_ms & 0xFFFFFFFF,
        phase_raw,
        countdown_raw,
        0
    )
    crc = zlib.crc32(payload)
    return payload + struct.pack(">I", crc)
```
**Replacement for `serialize_denm`**:
```python
    if timestamp_ms is None:
        timestamp_ms = int(time.time() * 1000) & 0xFFFFFFFF

    for val, name in [(speed_kmh, "speed_kmh"), (heading_deg, "heading_deg")]:
        if math.isnan(val) or math.isinf(val):
            raise ValueError(f"Invalid telemetry value: {name} cannot be NaN or Inf.")

    speed_raw = int(round(max(0.0, min(250.0, speed_kmh)) * 100))
    heading_raw = int(round((heading_deg % 360.0) * 10))
    cause_raw = int(cause_code) & 0xFFFF

    payload = struct.pack(
        ">BBI I H H H 10x H",
        MSG_TYPE_DENM,
        1,
        station_id & 0xFFFFFFFF,
        timestamp_ms & 0xFFFFFFFF,
        cause_raw,
        speed_raw,
        heading_raw,
        0
    )
    crc = zlib.crc32(payload)
    return payload + struct.pack(">I", crc)
```

#### Patch 1.5: Multi-Protocol Deserializer with MAC Verification in `deserialize_v2x_packet`
**Target Lines**: 190–222
**Replacement**:
```python
def deserialize_v2x_packet(raw_bytes: bytes, session_key: Optional[bytes] = None) -> V2XTelemetryPacket:
    """
    Deserializes a 32-byte payload, verifies CRC32 or lightweight MAC,
    and dispatches unpacking according to protocol message type.
    """
    if len(raw_bytes) != 32:
        raise ValueError(f"Invalid packet length: {len(raw_bytes)} bytes (expected 32 bytes).")

    payload = raw_bytes[:28]
    if session_key is not None:
        expected_mac = raw_bytes[28:]
        if not verify_lightweight_mac(payload, expected_mac, session_key):
            raise ValueError("Lightweight MAC verification failed!")
    else:
        expected_crc = struct.unpack(">I", raw_bytes[28:])[0]
        actual_crc = zlib.crc32(payload)
        if actual_crc != expected_crc:
            raise ValueError(f"CRC Checksum Mismatch! Expected {expected_crc:#010x}, calculated {actual_crc:#010x}.")

    msg_type = payload[0]

    if msg_type in (MSG_TYPE_BSM, MSG_TYPE_CAM):
        msg_type, ver, station_id, ts, spd_raw, acc_raw, hdg_raw, lat_raw, lon_raw, elev_raw, mask = struct.unpack(
            ">BBI I H h H i i h H", payload
        )
        return V2XTelemetryPacket(
            msg_type=msg_type,
            station_id=station_id,
            timestamp_ms=ts,
            speed_kmh=max(0.0, min(250.0, spd_raw / 100.0)),
            accel_mps2=max(-20.0, min(20.0, acc_raw / 100.0)),
            heading_deg=(hdg_raw / 10.0) % 360.0,
            latitude=max(-90.0, min(90.0, lat_raw / 1e7)),
            longitude=max(-180.0, min(180.0, lon_raw / 1e7)),
            elevation_m=max(-1000.0, min(10000.0, float(elev_raw))),
            safety_bitmask=mask,
            event_code=0,
            countdown_sec=0.0,
            raw_payload_bytes=raw_bytes
        )

    elif msg_type == MSG_TYPE_SPAT:
        msg_type, ver, station_id, ts, phase_id, countdown_raw, mask = struct.unpack(
            ">BBI I H H 12x H", payload
        )
        return V2XTelemetryPacket(
            msg_type=msg_type,
            station_id=station_id,
            timestamp_ms=ts,
            speed_kmh=0.0,
            accel_mps2=0.0,
            heading_deg=0.0,
            latitude=0.0,
            longitude=0.0,
            elevation_m=0.0,
            safety_bitmask=mask,
            event_code=phase_id,
            countdown_sec=max(0.0, min(120.0, countdown_raw / 10.0)),
            raw_payload_bytes=raw_bytes
        )

    elif msg_type == MSG_TYPE_DENM:
        msg_type, ver, station_id, ts, cause_code, spd_raw, hdg_raw, mask = struct.unpack(
            ">BBI I H H H 10x H", payload
        )
        return V2XTelemetryPacket(
            msg_type=msg_type,
            station_id=station_id,
            timestamp_ms=ts,
            speed_kmh=max(0.0, min(250.0, spd_raw / 100.0)),
            accel_mps2=0.0,
            heading_deg=(hdg_raw / 10.0) % 360.0,
            latitude=0.0,
            longitude=0.0,
            elevation_m=0.0,
            safety_bitmask=mask,
            event_code=cause_code,
            countdown_sec=0.0,
            raw_payload_bytes=raw_bytes
        )

    else:
        raise ValueError(f"Unknown or unsupported V2X message type: {msg_type:#04x}")
```

---

### 4.2 Target File 2: `src/moving_cars_simulation.py`

#### Patch 2.1: Update `ConnectedVehicle` Dataclass
**Target Lines**: 17–28
**Replacement**:
```python
@dataclass
class ConnectedVehicle:
    vehicle_id: int
    pos_x_m: float
    pos_y_m: float
    speed_kmh: float
    accel_mps2: float
    heading_deg: float
    master_seed: bytes
    session_states: Dict[int, DynamicPermutationState]
    last_tx_time_ms: int = 0
    last_tx_speed_kmh: float = 0.0
    desired_speed_kmh: float = 110.0
```

#### Patch 2.2: Initialize Vehicle Fleet with Desired Speed
**Target Lines**: 44–65
**Replacement**:
```python
    def _initialize_vehicle_fleet(self):
        """Spawns vehicles with realistic highway speeds (70-130 km/h) and inter-vehicle spacing."""
        for vid in range(1, self.num_vehicles + 1):
            lane = vid % 4
            pos_x = float(vid * (self.corridor_length_m / self.num_vehicles))
            pos_y = float(lane * 3.75)  # Standard 3.75m highway lane width
            speed = float(self.rng.uniform(80.0, 125.0))
            desired_speed = float(self.rng.uniform(90.0, 130.0))
            accel = float(self.rng.uniform(-0.5, 0.5))
            heading = 90.0 if (vid % 2 == 0) else 270.0

            master_seed = f"VEHICLE_{vid:04d}_MASTER_KEY".encode()
            self.vehicles[vid] = ConnectedVehicle(
                vehicle_id=vid,
                pos_x_m=pos_x,
                pos_y_m=pos_y,
                speed_kmh=speed,
                accel_mps2=accel,
                heading_deg=heading,
                master_seed=master_seed,
                session_states={},
                last_tx_time_ms=0,
                last_tx_speed_kmh=speed,
                desired_speed_kmh=desired_speed
            )
```

#### Patch 2.3: Implement Authentic Intelligent Driver Model (IDM) Physics
**Target Lines**: 80–93
**Replacement**:
```python
    def step_physics(self, dt_sec: float = 0.1):
        """
        Updates kinematic positions and speeds according to the authentic
        Intelligent Driver Model (IDM) car-following dynamics across lanes.
        """
        self.current_time_ms = (self.current_time_ms + int(dt_sec * 1000)) & 0xFFFFFFFF

        # IDM Model Parameters
        a_max = 1.5      # Maximum acceleration (m/s^2)
        b_comf = 2.0     # Comfortable deceleration (m/s^2)
        s0 = 2.0         # Minimum jam distance (m)
        T_headway = 1.5  # Safe time headway (s)
        delta_exp = 4    # Acceleration exponent
        veh_len = 5.0    # Physical vehicle length (m)

        # Process each lane independently
        for lane_idx in range(4):
            lane_vehs = [
                v for v in self.vehicles.values()
                if (int(round(v.pos_y_m / 3.75)) % 4) == lane_idx
            ]
            if not lane_vehs:
                continue

            # Sort vehicles along corridor
            lane_vehs.sort(key=lambda v: v.pos_x_m)
            m = len(lane_vehs)

            for i in range(m):
                veh = lane_vehs[i]
                v_curr = max(0.0, veh.speed_kmh / 3.6)
                v_des = max(1.0, veh.desired_speed_kmh / 3.6)

                if m > 1:
                    lead = lane_vehs[(i + 1) % m]
                    v_lead = max(0.0, lead.speed_kmh / 3.6)
                    delta_v = v_curr - v_lead

                    dx = (lead.pos_x_m - veh.pos_x_m) % self.corridor_length_m
                    s = max(0.5, dx - veh_len)

                    s_star = s0 + max(0.0, v_curr * T_headway + (v_curr * delta_v) / (2.0 * math.sqrt(a_max * b_comf)))
                    accel_idm = a_max * (1.0 - (v_curr / v_des) ** delta_exp - (s_star / s) ** 2)
                else:
                    accel_idm = a_max * (1.0 - (v_curr / v_des) ** delta_exp)

                noise = float(self.rng.uniform(-0.05, 0.05))
                accel_target = accel_idm + noise
                veh.accel_mps2 = max(-6.0, min(3.0, accel_target))

                new_speed_mps = max(0.0, v_curr + veh.accel_mps2 * dt_sec)
                veh.speed_kmh = max(0.0, min(160.0, new_speed_mps * 3.6))
                veh.pos_x_m = (veh.pos_x_m + (veh.speed_kmh / 3.6) * dt_sec) % self.corridor_length_m
```

#### Patch 2.4: Monotonic Timestamp Advancement & Transmission History in `generate_streaming_batch`
**Target Lines**: 117–130, 198–213
**Replacement**:
```python
        for i in range(batch_size):
            # Advance simulation clock monotonically for every packet (10 ms per packet)
            self.current_time_ms = (self.current_time_ms + 10) & 0xFFFFFFFF

            # Step IDM physics every 10 packets (100 ms = 10 Hz)
            if i > 0 and (i % 10 == 0):
                self.step_physics(dt_sec=0.1)

            s_id = int(self.rng.choice(v_ids))
            r_id = int(self.rng.choice(v_ids))
            while r_id == s_id:
                r_id = int(self.rng.choice(v_ids))

            sender = self.vehicles[s_id]
            receiver = self.vehicles[r_id]
            s_state, r_state = self.get_or_create_session(s_id, r_id)

            curr_times[i] = self.current_time_ms

            if sender.last_tx_time_ms == 0:
                prev_times[i] = (self.current_time_ms - 100) & 0xFFFFFFFF
                prev_speeds[i] = sender.speed_kmh
            else:
                prev_times[i] = sender.last_tx_time_ms
                prev_speeds[i] = sender.last_tx_speed_kmh

            sender.last_tx_time_ms = self.current_time_ms
            sender.last_tx_speed_kmh = sender.speed_kmh
```
**Update Sybil injection block** (lines 198–213):
```python
                elif atk_type == 3:
                    # Class 3: SYBIL_GHOST_INJECTION (attacker with fake seed / identity)
                    attacker_seed = f"ATTACKER_FAKE_KEY_{i}".encode()
                    attacker_state = DynamicPermutationState(attacker_seed, "SPOOFED_SESSION")

                    # Support both stealthy Sybil (realistic kinematics) and aggressive ghost (anomalous kinematics)
                    if self.rng.rand() < 0.5:
                        sybil_speed = float(self.rng.uniform(70.0, 120.0))
                        sybil_accel = float(self.rng.uniform(-2.0, 2.0))
                    else:
                        sybil_speed = float(self.rng.uniform(180.0, 240.0))
                        sybil_accel = float(self.rng.uniform(18.0, 30.0))

                    fake_pkt = serialize_bsm(
                        station_id=9999,
                        speed_kmh=sybil_speed,
                        accel_mps2=sybil_accel,
                        heading_deg=0.0,
                        timestamp_ms=self.current_time_ms
                    )
                    strand = self.engine.encode_bytes(fake_pkt, attacker_state)
                    curr_r_state = DynamicPermutationState(r_state.master_seed, r_state.session_id)
                    curr_r_state.frame_counter = r_state.frame_counter
                    curr_r_state.active_byte_to_4mer = list(r_state.active_byte_to_4mer)
                    curr_r_state.active_4mer_to_byte = dict(r_state.active_4mer_to_byte)
```

---

### 4.3 Target File 3: `src/attack_simulator.py`

#### Patch 3.1: Intra-Packet vs MTD Shannon Entropy Reporting in `test_frequency_analysis_attack`
**Target Lines**: 136–156
**Replacement**:
```python
        freqs = np.array(list(counts.values())) / len(tetramers)
        mean_freq = np.mean(freqs)
        std_freq = np.std(freqs)
        entropy_mtd = self.engine.calculate_shannon_entropy(combined)

        # Measure intra-packet entropy across individual sampled packets
        sample_size = min(100, len(all_strands))
        intra_entropies = [self.engine.calculate_shannon_entropy(s) for s in all_strands[:sample_size]]
        single_packet_entropy_mean = float(np.mean(intra_entropies))

        is_flat = bool(std_freq < 0.002 and entropy_mtd > 7.90)

        return AttackResult(
            attack_name="Frequency & N-Gram Cryptanalysis Attack",
            trials=num_packets,
            successful_breaches=0 if is_flat else 1,
            detection_rate_pct=100.0 if is_flat else 0.0,
            details={
                "mean_4mer_frequency": float(mean_freq),
                "expected_uniform_frequency": 1.0 / 256.0,
                "frequency_std_deviation": float(std_freq),
                "shannon_entropy_bits": float(entropy_mtd),
                "single_packet_entropy_mean": single_packet_entropy_mean,
                "defense": "Dynamic Rolling Permutation Shuffling"
            }
        )
```

---

## 5. Comprehensive Regression Test Criteria

The following unit and integration regression test specifications must be added to `tests/test_dna_v2x.py` or a dedicated test file to guarantee zero regression:

### Test Suite 1: Schema Deserialization Integrity (F-06)
- **`test_spat_deserialization_fidelity`**:
  * Serialize SPaT frame: `station_id=101, phase_id=3, countdown_sec=25.5, timestamp_ms=500000`.
  * Deserialize via `deserialize_v2x_packet(raw)`.
  * Verify `pkt.msg_type == MSG_TYPE_SPAT (0x03)`.
  * Verify `pkt.event_code == 3` (matching `phase_id`).
  * Verify `abs(pkt.countdown_sec - 25.5) < 0.05`.
  * Verify `pkt.speed_kmh == 0.0` (NOT 0.03).
  * Verify `pkt.accel_mps2 == 0.0` (NOT 2.55).
- **`test_denm_deserialization_fidelity`**:
  * Serialize DENM frame: `station_id=202, cause_code=2, speed_kmh=85.0, heading_deg=180.0, timestamp_ms=600000`.
  * Deserialize via `deserialize_v2x_packet(raw)`.
  * Verify `pkt.msg_type == MSG_TYPE_DENM (0x04)`.
  * Verify `pkt.event_code == 2` (matching `cause_code`).
  * Verify `abs(pkt.speed_kmh - 85.0) < 0.05` (NOT 0.02).
  * Verify `abs(pkt.heading_deg - 180.0) < 0.1`.
  * Verify `pkt.accel_mps2 == 0.0` (NOT 85.0).
- **`test_unsupported_message_type_rejection`**:
  * Construct 32-byte packet with byte 0 = `0xFF`.
  * Compute valid CRC-32 on first 28 bytes and append.
  * Verify `deserialize_v2x_packet` raises `ValueError` with "Unknown or unsupported V2X message type".

### Test Suite 2: Sensor NaN/Inf Handling & Boundary Validation (F-07)
- **`test_nan_speed_rejection`**:
  * `serialize_bsm(station_id=1, speed_kmh=float('nan'), accel_mps2=0.0, heading_deg=90.0)` raises `ValueError`.
- **`test_inf_speed_rejection`**:
  * `serialize_bsm(station_id=1, speed_kmh=float('inf'), accel_mps2=0.0, heading_deg=90.0)` raises `ValueError`.
- **`test_nan_heading_rejection`**:
  * `serialize_bsm(station_id=1, speed_kmh=50.0, accel_mps2=0.0, heading_deg=float('nan'))` raises `ValueError`.
- **`test_nan_countdown_rejection`**:
  * `serialize_spat(station_id=1, phase_id=1, countdown_sec=float('nan'))` raises `ValueError`.
- **`test_elevation_boundary_clipping`**:
  * `serialize_bsm(station_id=1, speed_kmh=50.0, accel_mps2=0.0, heading_deg=90.0, elevation_m=35000.0)` does NOT crash.
  * Deserializing yields `pkt.elevation_m == 10000.0`.
  * `serialize_bsm(..., elevation_m=-5000.0)` deserializes to `-1000.0`.
- **`test_coordinate_boundary_clipping`**:
  * `serialize_bsm(..., latitude=120.0, longitude=-220.0)` clamps to `latitude == 90.0` and `longitude == -180.0`.

### Test Suite 3: Integrated Lightweight MAC Verification
- **`test_deserializer_mac_mode`**:
  * Generate 28-byte payload: `payload = serialize_bsm(...)[:28]`.
  * Compute MAC: `mac = compute_lightweight_mac(payload, key)`.
  * Packet: `raw = payload + mac`.
  * `deserialize_v2x_packet(raw, session_key=key)` parses cleanly.
  * `deserialize_v2x_packet(raw, session_key=b"WRONG_KEY_000000")` raises `ValueError("Lightweight MAC verification failed!")`.

### Test Suite 4: Intelligent Driver Model (IDM) & Simulation Physics (F-09)
- **`test_idm_car_following_emergency_braking`**:
  * Setup 2 vehicles in lane 0: Leader at $x=50\text{ m}, v=20\text{ km/h}$; Follower at $x=40\text{ m}, v=120\text{ km/h}$.
  * Run `sim.step_physics(dt_sec=0.1)` for 5 steps.
  * Assert Follower decelerates strongly (`accel_mps2 < -2.0 m/s^2`).
  * Assert Follower does NOT crash into or pass Leader (`follower.pos_x_m < leader.pos_x_m`).
- **`test_streaming_batch_monotonic_timestamps`**:
  * Call `generate_streaming_batch(batch_size=200)`.
  * Assert `len(set(cur_times)) == 200` (zero timestamp stagnation).
  * Assert `np.all(np.diff(cur_times) > 0)` (strictly monotonically increasing).
  * Assert `np.all(cur_times > p_times)` (elapsed time strictly positive).
- **`test_classifier_accuracy_with_idm_physics`**:
  * Run 10-class calibration and evaluation from `test_attack_classifier.py`.
  * Verify all classes achieve $\ge 95\%$ accuracy, with Sybil detection $\ge 97.5\%$.
