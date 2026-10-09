# Handoff Report — Explorer M1_1 (Cryptography, Key Derivation & Memory Sanitization)

**Working Directory**: `C:\Users\umert\.gemini\antigravity\scratch\DNA-V2X\.agents\teamwork\explorer_m1_1`  
**Target File**: `src/dna_4mer_engine.py`  
**Target Vulnerabilities**: F-01, F-02, F-03, F-04 (Interface Contract)  
**Parent Orchestrator ID**: `8e427327-1383-435e-84f9-65791f49405e`  
**Handoff Type**: Hard (Investigation complete, patch specifications formulated)

---

## 1. Observation

Direct observations from static and behavioral analysis of the codebase:

1. **Fisher-Yates Keystream Slicing**:
   - Location: `src/dna_4mer_engine.py:70–74`
   - Verbatim code:
     ```python
     for i in range(255, 0, -1):
         offset = (255 - i) * 2
         val = struct.unpack(">H", keystream[offset : offset + 2])[0]
         j = val % (i + 1)
         indices[i], indices[j] = indices[j], indices[i]
     ```
   - Mathematical check: `val` is a 16-bit integer ($0 \le val \le 65535$, domain size $M=65536$).
   - Command: `python -c "k=255; M=65536; q, r = divmod(M, k); p0 = (q+1)/M; p_ideal = 1/k; print((p0 - p_ideal)/p_ideal * 100)"`
   - Result: `0.3875732421875014 %` relative bias for $k=255$.

2. **Memory Sanitization Deficiencies**:
   - Location: `src/dna_4mer_engine.py:99–107`
   - Verbatim code:
     ```python
     def purge_memory(self):
         """
         Secure zero-fill overwrite of active permutation structures in RAM.
         Prevents post-compromise memory dump key extraction.
         """
         if isinstance(self.active_byte_to_4mer, list):
             self.active_byte_to_4mer = ["AAAA"] * 256
         self.active_4mer_to_byte.clear()
     ```
   - Observed: `self.master_seed` is not modified. It remains in plaintext in the object instance.
   - Observed: Global cache `_PERM_CACHE` at line 26 and line 81 stores `(self.master_seed, self.frame_counter, self.session_id) -> (active_byte_to_4mer, active_4mer_to_byte)`. `purge_memory()` does not evict or wipe entries from `_PERM_CACHE`.

3. **Unbounded Global Permutation Cache**:
   - Location: `src/dna_4mer_engine.py:26, 80–82`
   - Verbatim code:
     ```python
     _PERM_CACHE = {}
     ...
     if len(_PERM_CACHE) < 50000:
         _PERM_CACHE[cache_key] = (list(self.active_byte_to_4mer), dict(self.active_4mer_to_byte))
     ```
   - Memory inspection: Each entry consumes $\approx 34.6\text{ KB}$. At 50,000 entries, memory usage reaches $1.65\text{ GB}$. Once 50,000 entries are stored, new insertions halt completely (`if len < 50000`), starving new streaming epochs without any LRU eviction policy.

4. **Ratchet One-Way Irreversibility & Replay Desync**:
   - Location: `src/dna_4mer_engine.py:93–95` vs `src/attack_classifier.py:121–138`
   - In `src/dna_4mer_engine.py`:
     ```python
     self.master_seed = hashlib.sha512(self.master_seed + b":RATCHET:FORWARD:" + extra).digest()[:32]
     ```
   - In `src/attack_classifier.py`:
     ```python
     chk_state = DynamicPermutationState(state.master_seed, state.session_id)
     chk_state.frame_counter = state.frame_counter - delay
     chk_state._generate_epoch_permutation()
     ```
   - Observed: At delay $d \ge 1$, `state.master_seed` is $S_t$, whereas the frame at $t - d$ was encoded with $S_{t-d}$. Because SHA-512 is pre-image resistant, $S_t \neq S_{t-d}$, generating a mismatched permutation. CRC-32 check fails on 100% of authentic replayed packets, routing them to line 185 (`features[i, 8] = 1.0`, Sybil Ghost Injection).

---

## 2. Logic Chain

1. **F-01 (Modulo Bias)**:
   - *From Observation 1*: `val` is drawn from $[0, 2^{16}-1]$. The number of outcomes is 65536.
   - When mapping onto $k = 255$, $65536 = 257 \times 255 + 1$. Residue $0$ receives 258 outcomes, while residues $1 \dots 254$ receive 257 outcomes.
   - The probability of residue 0 is $\frac{258}{65536} \approx 0.0039368$, compared to the uniform expectation $\frac{1}{255} \approx 0.0039216$.
   - This produces an uncorrected $+0.3876\%$ relative bias.
   - *Inference*: Substituting 32-bit integers (`>I`) with standard rejection threshold $\text{limit} = 2^{32} - (2^{32} \pmod k)$ guarantees that each valid residue has exactly $\frac{\text{limit}}{k}$ pre-images, completely eliminating modulo bias to $0.000000\%$.

2. **F-02 (Memory Sanitization)**:
   - *From Observation 2*: `purge_memory()` resets `self.active_byte_to_4mer` and clears `self.active_4mer_to_byte`, but leaves `self.master_seed` untouched and leaves `_PERM_CACHE` untouched.
   - *Inference*: A memory dump of the Python process easily recovers the master seed and all cached permutation tables. To achieve genuine zeroization, `purge_memory()` must zero `self.master_seed = b"\x00" * len(self.master_seed)`, zero all historical buffers, and evict the session's entries from `_PERM_CACHE`.

3. **F-03 (PFS Cache Bloat & ECU Crash Risk)**:
   - *From Observation 3*: `_PERM_CACHE` allows up to 50,000 entries ($\approx 1.65\text{ GB}$) and has no eviction mechanism.
   - *Inference*: Automotive ECUs have bounded memory (512 MB to 2 GB). Allocating 1.65 GB causes OOM crashes. Furthermore, holding past session keys across 50,000 frames violates Perfect Forward Secrecy.
   - *Inference*: Replacing `_PERM_CACHE` with a thread-safe bounded `PermutationLRUCache` (capacity 512 entries, $\approx 17.7\text{ MB}$ RAM) with LRU eviction and session zeroization solves both the memory crash hazard and the forward secrecy leak.

4. **F-04 Interface Contract (Historical Permutation Recovery)**:
   - *From Observation 4*: `attack_classifier.py` attempts to reconstruct past epochs by decrementing `frame_counter` against the current `master_seed`.
   - *Inference*: Because $S_{t-d}$ cannot be computed backward from $S_t$, the receiver cannot reconstruct past permutations without explicit state retention.
   - *Inference*: Adding a bounded historical ring buffer (`deque(maxlen=16)`) in `DynamicPermutationState` and exposing `get_historical_permutation(delay: int) -> Optional[DynamicPermutationState]` provides the exact interface required for the receiver to decode delayed frames within the ratchet window, correctly classifying Replay attacks.

---

## 3. Caveats

- **Scope boundary**: This investigation is strictly read-only and scopes the cryptographic and memory mechanisms in `src/dna_4mer_engine.py` and its interface contract with `src/attack_classifier.py` and `src/moving_cars_simulation.py`. Source code changes to other files (`v2x_telemetry_schema.py`, `attack_classifier.py`, `moving_cars_simulation.py`) are handled by their respective milestone tasks.
- **Python Memory Immutability**: In CPython, `bytes` objects are immutable in heap memory. Assigning `self.master_seed = b"\x00" * len(self.master_seed)` rebinds the attribute to a zeroed bytes object. When combined with GC reclamation, session cache eviction, and ring buffer zeroization, residual key exposure in active references is eliminated.
- **Ratchet Window Size**: The historical buffer size is set to $W=16$ (covering the protocol requirement of delay $1 \dots 8$ frames with safety headroom). Replays delayed by $> 16$ frames are correctly classified as expired/invalid (PFS guarantee).

---

## 4. Conclusion

1. `src/dna_4mer_engine.py` can be fully remediated without breaking existing API signatures.
2. The four concrete remediations are:
   - **F-01**: Implement 32-bit rejection sampling in `_generate_epoch_permutation()` to achieve $0.000000\%$ modulo bias.
   - **F-02**: Update `purge_memory()` to zero `self.master_seed`, wipe `self._history`, and evict all matching session entries from `_PERM_CACHE`.
   - **F-03**: Replace `_PERM_CACHE = {}` with a thread-safe `PermutationLRUCache` capped at 512 entries with LRU eviction and module functions `clear_permutation_cache()` and `get_permutation_cache_size()`.
   - **F-04**: Implement `self._history = deque(maxlen=16)` and `get_historical_permutation(delay: int) -> Optional[DynamicPermutationState]` to satisfy the ratchet replay window interface contract.
3. Detailed line-by-line patch specifications and regression test suites are documented in `analysis.md`.

---

## 5. Verification Method

To independently verify the findings, patch specifications, and regression tests:

1. **Verify Mathematical Modulo Bias**:
   ```powershell
   python -c "k=255; M=65536; q, r = divmod(M, k); p0 = (q+1)/M; p_ideal = 1/k; print('Bias:', (p0 - p_ideal)/p_ideal * 100, '%')"
   ```
   *Expected Output*: `Bias: 0.3875732421875014 %`

2. **Verify Proposed Implementation Prototype**:
   Run the verification prototype test script in `analysis.md` section 7 or execute:
   ```powershell
   python -m unittest discover tests/
   ```
   *Pass Condition*: All unit tests pass cleanly with zero regression.

3. **Inspect Analysis Report**:
   Inspect `C:\Users\umert\.gemini\antigravity\scratch\DNA-V2X\.agents\teamwork\explorer_m1_1\analysis.md` for the line-numbered before/after patch blocks and the 4 unit test specifications.
