"""
Moving Cars Mobility & V2X Channel Simulator for DNA-V2X.
Simulates realistic vehicle kinematics, platoon formations, highway dynamics,
and inter-vehicle ephemeral communication sessions across hundreds of connected vehicles.
"""

import time
import math
import numpy as np
from typing import List, Dict, Any, Tuple
from dataclasses import dataclass
from collections import deque

from .dna_4mer_engine import DNA4MerEngine, DynamicPermutationState, BASES
from .v2x_telemetry_schema import serialize_bsm, serialize_cam, serialize_spat, serialize_denm


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


class MovingCarsSimulator:
    """
    Simulates a high-density highway corridor (10 km, 4 lanes each direction)
    with N moving connected vehicles communicating at 10 Hz over 5.9 GHz DSRC / C-V2X.
    """
    def __init__(self, num_vehicles: int = 100, corridor_length_m: float = 10000.0, seed: int = 42):
        self.num_vehicles = num_vehicles
        self.corridor_length_m = corridor_length_m
        self.rng = np.random.RandomState(seed)
        self.engine = DNA4MerEngine()
        self.vehicles: Dict[int, ConnectedVehicle] = {}
        self.current_time_ms = int(time.time() * 1000) & 0xFFFFFFFF
        self._initialize_vehicle_fleet()

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

    def get_or_create_session(self, sender_id: int, receiver_id: int) -> Tuple[DynamicPermutationState, DynamicPermutationState]:
        """Establishes or retrieves pairwise ephemeral permutation session between two moving cars."""
        sender = self.vehicles[sender_id]
        receiver = self.vehicles[receiver_id]

        if receiver_id not in sender.session_states:
            # Pairwise ephemeral session key agreement
            pair_label = f"V2V_{min(sender_id, receiver_id)}_{max(sender_id, receiver_id)}"
            shared_secret = sender.master_seed + receiver.master_seed + pair_label.encode()
            sender.session_states[receiver_id] = DynamicPermutationState(shared_secret, pair_label)
            receiver.session_states[sender_id] = DynamicPermutationState(shared_secret, pair_label)

        return sender.session_states[receiver_id], receiver.session_states[sender_id]

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

    def generate_streaming_batch(
        self,
        batch_size: int = 10000,
        attack_ratio: float = 0.3,
        attack_types: List[int] = None
    ) -> Tuple[List[str], List[DynamicPermutationState], np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
        """
        Generates a batch of moving car telemetry packets (benign + targeted attack injections).
        Returns:
          dna_strands, receiver_states, current_timestamps, prev_speeds, prev_times, ground_truth_labels
        """
        if attack_types is None:
            attack_types = [1, 2, 3, 4, 5]  # All 5 attack vectors

        strands = []
        receiver_states = []
        curr_times = np.zeros(batch_size, dtype=np.int64)
        prev_speeds = np.zeros(batch_size, dtype=np.float32)
        prev_times = np.zeros(batch_size, dtype=np.int64)
        labels = np.zeros(batch_size, dtype=np.int32)

        v_ids = list(self.vehicles.keys())

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

            # Decide if benign or attack
            is_attack = bool(self.rng.rand() < attack_ratio)

            if not is_attack:
                # Class 0: BENIGN_TELEMETRY
                raw_pkt = serialize_bsm(
                    station_id=sender.vehicle_id,
                    speed_kmh=sender.speed_kmh,
                    accel_mps2=sender.accel_mps2,
                    heading_deg=sender.heading_deg,
                    latitude=37.7749 + (sender.pos_x_m / 111000.0),
                    longitude=-122.4194 + (sender.pos_y_m / 111000.0),
                    timestamp_ms=self.current_time_ms
                )
                strand = self.engine.encode_bytes(raw_pkt, s_state)
                # Receiver state matches sender at time of reception
                curr_r_state = DynamicPermutationState(r_state.master_seed, r_state.session_id)
                curr_r_state.frame_counter = r_state.frame_counter
                curr_r_state.active_byte_to_4mer = list(r_state.active_byte_to_4mer)
                curr_r_state.active_4mer_to_byte = dict(r_state.active_4mer_to_byte)
                curr_r_state._history = deque(r_state._history, maxlen=r_state._history_window_size)

                # Ratchet forward for next frame
                s_state.ratchet_forward()
                r_state.ratchet_forward()
                labels[i] = 0

            else:
                atk_type = int(self.rng.choice(attack_types))
                labels[i] = atk_type

                if atk_type == 1:
                    # Class 1: REPLAY_ATTACK (intercepted frame replayed after receiver ratchets)
                    # Ensure session has ratcheted so history exists
                    if len(r_state._history) < 2:
                        for _ in range(2):
                            s_state.ratchet_forward()
                            r_state.ratchet_forward()

                    delay = int(self.rng.randint(1, min(4, len(r_state._history))))
                    hist_s_state = s_state.get_historical_permutation(delay)
                    if hist_s_state is None:
                        s_state.ratchet_forward()
                        r_state.ratchet_forward()
                        delay = 1
                        hist_s_state = s_state.get_historical_permutation(delay)

                    old_time = (self.current_time_ms - int(self.rng.randint(500, 5000))) & 0xFFFFFFFF
                    raw_pkt = serialize_bsm(sender.vehicle_id, sender.speed_kmh, sender.accel_mps2, sender.heading_deg, timestamp_ms=old_time)
                    strand = self.engine.encode_bytes(raw_pkt, hist_s_state)

                    # Receiver is at current active state
                    curr_r_state = DynamicPermutationState(r_state.master_seed, r_state.session_id)
                    curr_r_state.frame_counter = r_state.frame_counter
                    curr_r_state.active_byte_to_4mer = list(r_state.active_byte_to_4mer)
                    curr_r_state.active_4mer_to_byte = dict(r_state.active_4mer_to_byte)
                    curr_r_state._history = deque(r_state._history, maxlen=r_state._history_window_size)

                elif atk_type == 2:
                    # Class 2: MUTATION_TAMPER (corrupted nucleotides)
                    raw_pkt = serialize_bsm(sender.vehicle_id, sender.speed_kmh, sender.accel_mps2, sender.heading_deg, timestamp_ms=self.current_time_ms)
                    strand_raw = self.engine.encode_bytes(raw_pkt, s_state)
                    curr_r_state = DynamicPermutationState(r_state.master_seed, r_state.session_id)
                    curr_r_state.frame_counter = r_state.frame_counter
                    curr_r_state.active_byte_to_4mer = list(r_state.active_byte_to_4mer)
                    curr_r_state.active_4mer_to_byte = dict(r_state.active_4mer_to_byte)
                    curr_r_state._history = deque(r_state._history, maxlen=r_state._history_window_size)

                    s_state.ratchet_forward()
                    r_state.ratchet_forward()

                    # Mutate random bases to distinct alternate nucleotides
                    strand_list = list(strand_raw)
                    mut_count = int(self.rng.randint(1, 6))
                    for _ in range(mut_count):
                        idx = int(self.rng.randint(0, len(strand_list)))
                        orig_b = strand_list[idx]
                        other_bases = [b for b in BASES if b != orig_b]
                        strand_list[idx] = self.rng.choice(other_bases)
                    strand = "".join(strand_list)

                elif atk_type == 3:
                    # Class 3: SYBIL_GHOST_INJECTION (attacker with fake seed / identity)
                    attacker_seed = f"ATTACKER_FAKE_KEY_{i}".encode()
                    attacker_state = DynamicPermutationState(attacker_seed, "SPOOFED_SESSION")
                    fake_pkt = serialize_bsm(
                        station_id=9999,
                        speed_kmh=float(self.rng.uniform(180.0, 240.0)),  # Impossible speed
                        accel_mps2=float(self.rng.uniform(18.0, 30.0)),    # Impossible acceleration jump
                        heading_deg=0.0,
                        timestamp_ms=self.current_time_ms
                    )
                    strand = self.engine.encode_bytes(fake_pkt, attacker_state)
                    curr_r_state = DynamicPermutationState(r_state.master_seed, r_state.session_id)
                    curr_r_state.frame_counter = r_state.frame_counter
                    curr_r_state.active_byte_to_4mer = list(r_state.active_byte_to_4mer)
                    curr_r_state.active_4mer_to_byte = dict(r_state.active_4mer_to_byte)
                    curr_r_state._history = deque(r_state._history, maxlen=r_state._history_window_size)

                elif atk_type == 4:
                    # Class 4: FREQUENCY_PROBE (repetitive low-entropy sequence probe)
                    probe_codon = self.rng.choice(["AAAA", "CCCC", "GGGG", "TTTT", "ATAT"])
                    strand = probe_codon * 32
                    curr_r_state = DynamicPermutationState(r_state.master_seed, r_state.session_id)
                    curr_r_state.frame_counter = r_state.frame_counter
                    curr_r_state.active_byte_to_4mer = list(r_state.active_byte_to_4mer)
                    curr_r_state.active_4mer_to_byte = dict(r_state.active_4mer_to_byte)
                    curr_r_state._history = deque(r_state._history, maxlen=r_state._history_window_size)

                elif atk_type == 5:
                    # Class 5: MITM_DESYNC (Desynchronized frame numbers / altered header bytes)
                    raw_pkt = serialize_bsm(sender.vehicle_id, sender.speed_kmh, sender.accel_mps2, sender.heading_deg, timestamp_ms=self.current_time_ms)
                    strand = self.engine.encode_bytes(raw_pkt, s_state)
                    # Desynced receiver state
                    desync_state = DynamicPermutationState(r_state.master_seed, r_state.session_id)
                    desync_state.frame_counter = r_state.frame_counter + int(self.rng.randint(2, 6))
                    desync_state._generate_epoch_permutation()
                    desync_state._history = deque(r_state._history, maxlen=r_state._history_window_size)
                    curr_r_state = desync_state

            strands.append(strand)
            receiver_states.append(curr_r_state)

        return strands, receiver_states, curr_times, prev_speeds, prev_times, labels
