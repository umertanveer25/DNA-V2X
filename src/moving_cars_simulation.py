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
                session_states={}
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
        """Updates kinematic positions and speeds according to Intelligent Driver Model (IDM)."""
        self.current_time_ms = (self.current_time_ms + int(dt_sec * 1000)) & 0xFFFFFFFF
        for vid, v in self.vehicles.items():
            # Acceleration noise
            v.accel_mps2 += float(self.rng.uniform(-0.2, 0.2))
            v.accel_mps2 = max(-6.0, min(3.0, v.accel_mps2))

            v.speed_kmh += (v.accel_mps2 * dt_sec * 3.6)
            v.speed_kmh = max(50.0, min(140.0, v.speed_kmh))

            speed_mps = v.speed_kmh / 3.6
            v.pos_x_m = (v.pos_x_m + speed_mps * dt_sec) % self.corridor_length_m

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
            s_id = int(self.rng.choice(v_ids))
            r_id = int(self.rng.choice(v_ids))
            while r_id == s_id:
                r_id = int(self.rng.choice(v_ids))

            sender = self.vehicles[s_id]
            receiver = self.vehicles[r_id]
            s_state, r_state = self.get_or_create_session(s_id, r_id)

            curr_times[i] = self.current_time_ms
            prev_speeds[i] = sender.speed_kmh
            prev_times[i] = (self.current_time_ms - 100) & 0xFFFFFFFF

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

                # Ratchet forward for next frame
                s_state.ratchet_forward()
                r_state.ratchet_forward()
                labels[i] = 0

            else:
                atk_type = int(self.rng.choice(attack_types))
                labels[i] = atk_type

                if atk_type == 1:
                    # Class 1: REPLAY_ATTACK (intercepted frame replayed after receiver ratchets)
                    old_time = (self.current_time_ms - int(self.rng.randint(500, 5000))) & 0xFFFFFFFF
                    raw_pkt = serialize_bsm(sender.vehicle_id, sender.speed_kmh, sender.accel_mps2, sender.heading_deg, timestamp_ms=old_time)
                    old_state = DynamicPermutationState(s_state.master_seed, s_state.session_id)
                    old_state.frame_counter = max(0, s_state.frame_counter - int(self.rng.randint(1, 4)))
                    old_state._generate_epoch_permutation()
                    strand = self.engine.encode_bytes(raw_pkt, old_state)
                    # Receiver is at current active state
                    curr_r_state = DynamicPermutationState(r_state.master_seed, r_state.session_id)
                    curr_r_state.frame_counter = r_state.frame_counter
                    curr_r_state.active_byte_to_4mer = list(r_state.active_byte_to_4mer)
                    curr_r_state.active_4mer_to_byte = dict(r_state.active_4mer_to_byte)

                elif atk_type == 2:
                    # Class 2: MUTATION_TAMPER (corrupted nucleotides)
                    raw_pkt = serialize_bsm(sender.vehicle_id, sender.speed_kmh, sender.accel_mps2, sender.heading_deg, timestamp_ms=self.current_time_ms)
                    strand_raw = self.engine.encode_bytes(raw_pkt, s_state)
                    curr_r_state = DynamicPermutationState(r_state.master_seed, r_state.session_id)
                    curr_r_state.frame_counter = r_state.frame_counter
                    curr_r_state.active_byte_to_4mer = list(r_state.active_byte_to_4mer)
                    curr_r_state.active_4mer_to_byte = dict(r_state.active_4mer_to_byte)

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

                elif atk_type == 4:
                    # Class 4: FREQUENCY_PROBE (repetitive low-entropy sequence probe)
                    probe_codon = self.rng.choice(["AAAA", "CCCC", "GGGG", "TTTT", "ATAT"])
                    strand = probe_codon * 32
                    curr_r_state = DynamicPermutationState(r_state.master_seed, r_state.session_id)
                    curr_r_state.frame_counter = r_state.frame_counter
                    curr_r_state.active_byte_to_4mer = list(r_state.active_byte_to_4mer)
                    curr_r_state.active_4mer_to_byte = dict(r_state.active_4mer_to_byte)

                elif atk_type == 5:
                    # Class 5: MITM_DESYNC (Desynchronized frame numbers / altered header bytes)
                    raw_pkt = serialize_bsm(sender.vehicle_id, sender.speed_kmh, sender.accel_mps2, sender.heading_deg, timestamp_ms=self.current_time_ms)
                    strand = self.engine.encode_bytes(raw_pkt, s_state)
                    # Desynced receiver state
                    desync_state = DynamicPermutationState(r_state.master_seed, r_state.session_id)
                    desync_state.frame_counter = r_state.frame_counter + int(self.rng.randint(2, 6))
                    desync_state._generate_epoch_permutation()
                    curr_r_state = desync_state

            strands.append(strand)
            receiver_states.append(curr_r_state)

        return strands, receiver_states, curr_times, prev_speeds, prev_times, labels
