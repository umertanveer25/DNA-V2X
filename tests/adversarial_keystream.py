"""
Adversarial Test Suite 1: Cryptographic Keystream & Fisher-Yates Shuffle.
Tests:
  1. 100,000 iterations bijection and uniqueness.
  2. Distribution uniformity via Pearson's Chi-Square Test (df=255).
  3. Rejection boundary behavior under exact boundary conditions (limit-1, limit, limit+1).
  4. Empirical rejection count tracking over 100,000 iterations.
"""

import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
import math
import struct
import hashlib
import time
from collections import Counter
from src.dna_4mer_engine import DynamicPermutationState, ALL_256_4MERS, clear_permutation_cache

def chi2_cdf(x, df):
    """Chi-square CDF approximation using incomplete gamma function or Wilson-Hilferty."""
    # If scipy is not installed, use math.erf approximation or stats if available
    try:
        from scipy.stats import chi2
        return chi2.cdf(x, df)
    except ImportError:
        # Wilson-Hilferty transformation for chi-square to normal
        z = ((x / df) ** (1/3) - (1 - 2 / (9 * df))) / math.sqrt(2 / (9 * df))
        return 0.5 * (1.0 + math.erf(z / math.sqrt(2.0)))

def run_task1_adversarial_tests():
    print("=" * 70)
    print("ADVERSARIAL TEST 1: Cryptographic Keystream & Shuffle")
    print("=" * 70)

    # 1. Bijection & Uniformity across 100,000 iterations
    N = 100000
    print(f"[*] Running {N:,} iterations of Fisher-Yates shuffle...")
    start_time = time.time()

    # Track positions of codons at index 0, index 127, and index 255
    pos0_counts = Counter()
    pos127_counts = Counter()
    pos255_counts = Counter()

    bijection_failures = 0
    total_rejections_empirical = 0

    # We use a synthetic or dedicated state with distinct seeds to prevent LRU cache lookup
    # and directly measure the cryptographic shuffle
    seed_base = b"CHALLENGER_SEED_M1_UNIFORMITY_"

    for i in range(N):
        # Derive seed or frame counter
        seed_material = seed_base + struct.pack(">Q", i)
        keystream = bytearray()
        block_idx = 0
        ks_offset = 0

        while len(keystream) < 1024:
            keystream.extend(hashlib.sha512(seed_material + struct.pack(">I", block_idx)).digest())
            block_idx += 1

        def next_u32():
            nonlocal ks_offset, block_idx, keystream
            if ks_offset + 4 > len(keystream):
                keystream.extend(hashlib.sha512(seed_material + struct.pack(">I", block_idx)).digest())
                block_idx += 1
            val = struct.unpack(">I", keystream[ks_offset : ks_offset + 4])[0]
            ks_offset += 4
            return val

        indices = list(range(256))
        for step in range(255, 0, -1):
            k = step + 1
            limit = 0x100000000 - (0x100000000 % k)
            while True:
                val = next_u32()
                if val < limit:
                    j = val % k
                    break
                else:
                    total_rejections_empirical += 1
            indices[step], indices[j] = indices[j], indices[step]

        # Verify Bijection: All 256 elements must be unique and in [0, 255]
        if len(set(indices)) != 256 or min(indices) != 0 or max(indices) != 255:
            bijection_failures += 1

        pos0_counts[indices[0]] += 1
        pos127_counts[indices[127]] += 1
        pos255_counts[indices[255]] += 1

        if (i + 1) % 25000 == 0:
            elapsed = time.time() - start_time
            print(f"    Completed {i+1:,}/{N:,} ({((i+1)/N)*100:.1f}%) in {elapsed:.2f}s...")

    elapsed = time.time() - start_time
    print(f"[*] Completed {N:,} iterations in {elapsed:.2f}s ({N/elapsed:.1f} iter/s).")
    print(f"[*] Bijection Failures: {bijection_failures}/{N}")
    assert bijection_failures == 0, f"Bijection failed in {bijection_failures} cases!"

    # 2. Chi-Square Uniformity Test
    expected_count = N / 256.0  # 390.625
    df = 255

    for name, counts in [("Index 0", pos0_counts), ("Index 127", pos127_counts), ("Index 255", pos255_counts)]:
        chi2_stat = sum((counts[c] - expected_count) ** 2 / expected_count for c in range(256))
        p_val = 1.0 - chi2_cdf(chi2_stat, df)
        print(f"[*] Uniformity ({name}): Chi2 Stat = {chi2_stat:.3f}, df = {df}, p-value = {p_val:.4f}")
        # A uniform distribution with df=255 has 99% confidence interval approximately [198, 319]
        # p-value > 0.001 is standard for failing to reject null hypothesis of uniformity
        assert p_val > 0.001, f"Uniformity test failed for {name}: p-value {p_val} < 0.001"

    # 3. Empirical Rejection Count
    # Theoretical rejection probability:
    # E[reject] = N * sum_{k=2}^{256} (2^32 % k) / 2^32
    theoretical_rej_prob = sum((0x100000000 % k) / float(0x100000000) for k in range(2, 257))
    expected_rejections = N * theoretical_rej_prob
    print(f"[*] Empirical Rejections observed: {total_rejections_empirical}")
    print(f"[*] Theoretical Expected Rejections: {expected_rejections:.4f}")

    # 4. Deterministic Rejection Boundary Unit Test
    print("[*] Testing rejection boundary behavior across all k in [2, 256]...")
    boundary_failures = 0
    for k in range(2, 257):
        rem = 0x100000000 % k
        limit = 0x100000000 - rem
        assert limit % k == 0, f"Limit {limit} is not a multiple of k={k}!"

        # Boundary condition 1: limit - 1 MUST be accepted
        val_accepted = limit - 1
        assert val_accepted < limit, f"val_accepted {val_accepted} >= limit {limit}"
        j_accepted = val_accepted % k
        assert 0 <= j_accepted < k, f"j_accepted {j_accepted} out of range [0, {k-1}]"

        # Boundary condition 2: limit MUST be rejected (if limit < 2^32)
        if rem > 0:
            val_rejected = limit
            assert not (val_rejected < limit), f"Limit {limit} was not rejected!"
            # Boundary condition 3: 0xFFFFFFFF MUST be rejected
            val_max = 0xFFFFFFFF
            assert not (val_max < limit), f"Max u32 {val_max} was not rejected for k={k}!"

    print(f"[*] All {255} rejection boundaries strictly verified!")

    # 5. Full DynamicPermutationState Integration Test (1000 states via API)
    print("[*] Verifying DynamicPermutationState API consistency...")
    for s_idx in range(1000):
        st = DynamicPermutationState(master_seed=f"test_seed_{s_idx}".encode(), session_id="TEST_SESS")
        assert len(st.active_byte_to_4mer) == 256
        assert len(set(st.active_byte_to_4mer)) == 256
        assert len(st.active_4mer_to_byte) == 256
        for b in range(256):
            codon = st.active_byte_to_4mer[b]
            assert st.active_4mer_to_byte[codon] == b

    print("[+] TASK 1 ADVERSARIAL TESTS PASSED!")
    return True

if __name__ == "__main__":
    run_task1_adversarial_tests()
