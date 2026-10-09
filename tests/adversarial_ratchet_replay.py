"""
Adversarial Test Suite 3: Ratchet Replay Verification & Sybil Discrimination.
Tests:
  1. Multi-frame streaming ratchets across t = 0 .. 16 epochs.
  2. Replay injection at arbitrary delays d = 1 .. 15.
  3. Empirical measurement of replay detection (Class 1: REPLAY_ATTACK) vs
     Sybil discrimination (Class 3: SYBIL_GHOST_INJECTION).
  4. Investigation of classifier window bounds (e.g., delay 1..8 vs delay 9..15).
  5. Investigation of temporal drift threshold (drift <= 200ms vs drift > 200ms).
"""

import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
import time
import numpy as np
from src.dna_4mer_engine import DNA4MerEngine, DynamicPermutationState
from src.v2x_telemetry_schema import serialize_bsm, deserialize_v2x_packet
from src.attack_classifier import extract_features_vectorized, FastRuleAndMLClassifier, CLASS_NAMES

def run_task3_adversarial_tests():
    print("=" * 70)
    print("ADVERSARIAL TEST 3: Ratchet Replay Verification & Sybil Discrimination")
    print("=" * 70)

    engine = DNA4MerEngine()
    classifier = FastRuleAndMLClassifier()

    # Step 1: Initialize Alice (Transmitter) and Bob (Receiver) with matching session
    master_seed = b"V2X_SECRET_PAIR_KEY_2026_M1_TEST"
    session_id = "V2V_PAIR_CHALLENGER"
    
    alice = DynamicPermutationState(master_seed, session_id, history_window=16)
    bob = DynamicPermutationState(master_seed, session_id, history_window=16)

    # Pre-generate a streaming sequence of 17 valid frames (t = 0 .. 16)
    # Using 10 Hz timing: each frame is 100 ms apart
    base_ts = 100000000  # Within uint32
    history_frames = []      # (t, strand, raw_bytes, ts_ms)

    print("[*] Generating multi-frame streaming ratchet from t = 0 to t = 16...")
    for t in range(17):
        ts_ms = base_ts + t * 100
        bsm_bytes = serialize_bsm(
            station_id=101,
            speed_kmh=60.0 + t * 0.5,
            accel_mps2=0.5,
            heading_deg=90.0,
            timestamp_ms=ts_ms
        )
        strand = engine.encode_bytes(bsm_bytes, alice)
        history_frames.append({
            "epoch": t,
            "strand": strand,
            "bytes": bsm_bytes,
            "ts_ms": ts_ms
        })
        # Advance Alice
        if t < 16:
            alice.ratchet_forward()
            bob.ratchet_forward()

    assert alice.frame_counter == 16
    assert bob.frame_counter == 16
    print(f"[*] Alice and Bob synchronized at epoch t = {bob.frame_counter}.")
    print(f"[*] Bob history buffer size: {len(bob.history_buffer)} / {bob._history_window_size}")

    # Verify Bob's history buffer holds epochs 0..15
    hist_epochs = [snap["frame_counter"] for snap in bob.history_buffer]
    print(f"[*] Bob history epochs present: {hist_epochs}")

    # Step 2: Test Replay Packets at current receiver epoch t = 16
    # Current receiver time is epoch 16 time:
    curr_time_ms = base_ts + 16 * 100

    print("\n[*] Testing replay injection at current epoch t=16 for delays d = 1 .. 15:")
    print("    Format: Delay | Past Epoch | Stale Drift (ms) | f7 (Replay) | f8 (Sybil) | Class Pred | Status")
    print("    " + "-" * 75)

    # Part A: Test with np.uint32 to document empirical OverflowError bug
    print("[*] Sub-test 3A: Testing with np.uint32 timestamp (standard C uint32 array)...")
    try:
        past_9_frame = history_frames[7] # delay 9
        feat_uint32 = extract_features_vectorized(
            dna_strands=[past_9_frame["strand"]],
            receiver_states=[bob],
            current_timestamps_ms=np.array([curr_time_ms], dtype=np.uint32)
        )
        print("    [!] Unexpected: No overflow occurred.")
    except OverflowError as oe:
        print(f"    [CONFIRMED BUG BUG-01] extract_features_vectorized() raises OverflowError on Windows with np.uint32 timestamps: {oe}")

    # Part B: Test with np.int64 across delays 1..15 to analyze classification logic
    print("\n[*] Sub-test 3B: Testing replay injection across delays d = 1 .. 15 (using int64 timestamps):")
    print("    Format: Delay | Past Epoch | Stale Drift (ms) | f7 (Replay) | f8 (Sybil) | Class Pred | Status")
    print("    " + "-" * 75)

    delay_results = {}
    for delay in range(1, 16):
        past_epoch = 16 - delay
        past_frame = history_frames[past_epoch]
        replayed_strand = past_frame["strand"]
        drift_ms = curr_time_ms - past_frame["ts_ms"]

        features = extract_features_vectorized(
            dna_strands=[replayed_strand],
            receiver_states=[bob],
            current_timestamps_ms=np.array([curr_time_ms], dtype=np.int64)
        )

        pred = classifier.classify_batch_fast(features)[0]
        class_str = CLASS_NAMES[pred]
        f7_replay = features[0, 7]
        f8_sybil = features[0, 8]

        status = "PASS" if pred == 1 else "ANOMALY"
        print(f"    d={delay:2d}   | Epoch {past_epoch:2d}  | {drift_ms:4d} ms           | {f7_replay:.1f}         | {f8_sybil:.1f}        | {pred} ({class_str:15s}) | {status}")
        delay_results[delay] = {
            "past_epoch": past_epoch,
            "drift_ms": drift_ms,
            "f7": f7_replay,
            "f8": f8_sybil,
            "pred": pred,
            "class_name": class_str
        }

    # Step 3: Test Sybil Ghost Injection Discrimination
    print("\n[*] Testing Sybil Ghost Injection (unauthorized key)...")
    sybil_seed = b"MALICIOUS_ATTACKER_FOREIGN_KEY_XX"
    sybil_state = DynamicPermutationState(sybil_seed, session_id="V2V_PAIR_CHALLENGER")
    sybil_bsm = serialize_bsm(
        station_id=666,
        speed_kmh=120.0,
        accel_mps2=0.0,
        heading_deg=0.0,
        timestamp_ms=curr_time_ms
    )
    sybil_strand = engine.encode_bytes(sybil_bsm, sybil_state)

    sybil_feat = extract_features_vectorized(
        dna_strands=[sybil_strand],
        receiver_states=[bob],
        current_timestamps_ms=np.array([curr_time_ms], dtype=np.int64)
    )
    sybil_pred = classifier.classify_batch_fast(sybil_feat)[0]
    sybil_class = CLASS_NAMES[sybil_pred]
    print(f"[*] Sybil Feature f7 (replay): {sybil_feat[0, 7]}, f8 (sybil): {sybil_feat[0, 8]}")
    print(f"[*] Sybil Classification: {sybil_pred} ({sybil_class})")
    assert sybil_pred == 3, f"Sybil injection not classified as SYBIL_GHOST_INJECTION! Got {sybil_pred} ({sybil_class})"
    print("[*] Sybil discrimination verified: Class 3 correctly assigned!")

    # Step 4: Analyze Delay Results
    print("\n[*] ANALYSIS OF DELAY REPLAY RESULTS:")
    # Check delays 1, 2: drift is 100ms and 200ms. Drift threshold is > 200ms in extract_features_vectorized:
    # If drift <= 200ms, past_replay_match sets f7 = 0.0 and desync_window_match = 1.0!
    # Check delays 3..8: drift is 300ms..800ms.
    # Check delays 9..15: range(1, 9) in extract_features_vectorized cuts off at delay 8!
    for d, res in delay_results.items():
        print(f"    Delay {d}: pred={res['pred']} ({res['class_name']}), f7={res['f7']}, f8={res['f8']}")

    return delay_results

if __name__ == "__main__":
    run_task3_adversarial_tests()
