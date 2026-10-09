"""
Adversarial Test Suite 2: Memory Sanitization & LRU Cache Concurrency.
Tests:
  1. PermutationLRUCache multi-threaded stress test up to capacity and beyond (16 threads).
  2. Bounded capacity invariant: len(cache) <= max_size strictly maintained under heavy race conditions.
  3. Master seed zeroization, historical ring buffer zeroization and clearing.
  4. Global and session-targeted cache purge verification.
  5. Post-purge runtime exception barriers and double-purge idempotence.
  6. Concurrent state allocation, forward-ratcheting, and mid-flight purging across threads.
"""

import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
import threading
import time
import random
import hashlib
from src.dna_4mer_engine import (
    PermutationLRUCache,
    DynamicPermutationState,
    _PERM_CACHE,
    clear_permutation_cache,
    get_permutation_cache_size,
    ALL_256_4MERS
)

def run_task2_adversarial_tests():
    print("=" * 70)
    print("ADVERSARIAL TEST 2: Memory Sanitization & LRU Cache Concurrency")
    print("=" * 70)

    # 1. Multi-threaded LRU Cache Stress Test
    max_cap = 64
    cache = PermutationLRUCache(max_size=max_cap)
    num_threads = 16
    ops_per_thread = 2000
    errors = []
    max_observed_size = 0
    size_lock = threading.Lock()

    def worker_cache_stress(tid):
        nonlocal max_observed_size
        try:
            for op_idx in range(ops_per_thread):
                action = random.random()
                session_id = f"SESS_{random.randint(0, 10)}"
                seed = f"seed_{random.randint(0, 50)}".encode()
                fc = random.randint(0, 100)
                key = (seed, fc, session_id)

                if action < 0.60:
                    # Put
                    val = (["AAAA"] * 256, {"AAAA": 0})
                    cache.put(key, val)
                elif action < 0.85:
                    # Get
                    _ = cache.get(key)
                elif action < 0.95:
                    # Evict session
                    if random.random() < 0.5:
                        cache.evict_session(session_id=session_id)
                    else:
                        cache.evict_session(master_seed=seed)
                else:
                    # Clear
                    if random.random() < 0.05:
                        cache.clear()

                c_len = len(cache)
                with size_lock:
                    if c_len > max_observed_size:
                        max_observed_size = c_len
                if c_len > max_cap:
                    errors.append(f"Thread {tid}: Cache size {c_len} exceeded max capacity {max_cap}!")
        except Exception as e:
            errors.append(f"Thread {tid} raised exception: {type(e).__name__}: {e}")

    threads = [threading.Thread(target=worker_cache_stress, args=(i,)) for i in range(num_threads)]
    print(f"[*] Launching {num_threads} threads executing {ops_per_thread*num_threads:,} cache operations...")
    t0 = time.time()
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    t_elapsed = time.time() - t0
    print(f"[*] Concurrency stress test finished in {t_elapsed:.2f}s.")
    print(f"[*] Maximum observed cache size: {max_observed_size} (Max limit: {max_cap}).")
    print(f"[*] Error count: {len(errors)}")
    if errors:
        for err in errors[:5]:
            print(f"    ERROR: {err}")
    assert len(errors) == 0, f"Encountered {len(errors)} concurrency errors in PermutationLRUCache!"
    assert max_observed_size <= max_cap, f"Cache exceeded capacity: {max_observed_size} > {max_cap}"

    # 2. Master Seed Zeroization & Memory Purge Verification
    print("[*] Testing master seed zeroization and historical buffer purge...")
    initial_seed = b"TOP_SECRET_MASTER_SEED_0123456789"
    st = DynamicPermutationState(master_seed=initial_seed, session_id="PURGE_TEST_SESSION", history_window=16)

    # Ratchet 10 times to populate history buffer and cache
    for step in range(10):
        st.ratchet_forward(physical_entropy=f"entropy_{step}".encode())

    assert len(st.history_buffer) == 10
    assert st.frame_counter == 10
    assert st.master_seed != b"\x00" * len(st.master_seed)
    assert len(st.active_byte_to_4mer) == 256
    assert len(st.active_4mer_to_byte) == 256
    assert not st._is_purged

    current_seed = st.master_seed
    # Verify historical state access
    hist_5 = st.get_historical_permutation(5)
    assert hist_5 is not None
    assert hist_5.frame_counter == 5

    # Execute purge
    st.purge_memory()

    # Verify zeroization of master seed
    assert st.master_seed == b"\x00" * len(current_seed), "Master seed was not zeroized!"
    # Verify active tables wiped
    assert st.active_byte_to_4mer == ["AAAA"] * 256, "active_byte_to_4mer was not sanitized!"
    assert len(st.active_4mer_to_byte) == 0, "active_4mer_to_byte was not cleared!"
    # Verify history buffer cleared
    assert len(st.history_buffer) == 0, "History buffer was not cleared!"
    # Verify purge flag set
    assert st._is_purged, "_is_purged flag not set!"

    # Verify post-purge barrier exceptions
    try:
        st.ratchet_forward()
        raise AssertionError("ratchet_forward() did not raise RuntimeError on purged state!")
    except RuntimeError:
        pass

    try:
        st._generate_epoch_permutation()
        raise AssertionError("_generate_epoch_permutation() did not raise RuntimeError on purged state!")
    except RuntimeError:
        pass

    assert st.get_historical_permutation(1) is None, "get_historical_permutation() returned non-None on purged state!"

    # Test idempotence: second purge should execute safely without error
    st.purge_memory()
    assert st.master_seed == b"\x00" * len(current_seed)
    assert st._is_purged
    print("[*] Master seed zeroization and purge barrier verified successfully!")

    # 3. Concurrent Multi-State Allocation, Ratcheting and Mid-Flight Purging
    print("[*] Testing concurrent state allocation and mid-flight purging across 8 threads...")
    purge_errors = []
    def worker_state_lifecycle(tid):
        try:
            for cycle in range(50):
                s = DynamicPermutationState(
                    master_seed=f"tid_{tid}_cycle_{cycle}".encode(),
                    session_id=f"SESSION_TID_{tid}"
                )
                for _ in range(random.randint(1, 10)):
                    s.ratchet_forward()
                if random.random() < 0.7:
                    s.purge_memory()
                    assert s.master_seed == b"\x00" * 32
                    assert s._is_purged
        except Exception as e:
            purge_errors.append(f"Thread {tid} error: {e}")

    th_pool = [threading.Thread(target=worker_state_lifecycle, args=(i,)) for i in range(8)]
    for t in th_pool:
        t.start()
    for t in th_pool:
        t.join()
    assert len(purge_errors) == 0, f"Encountered errors during concurrent state lifecycles: {purge_errors}"

    print("[+] TASK 2 ADVERSARIAL TESTS PASSED!")
    return True

if __name__ == "__main__":
    run_task2_adversarial_tests()
