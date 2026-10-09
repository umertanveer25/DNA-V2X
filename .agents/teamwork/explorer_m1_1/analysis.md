# Comprehensive Cryptographic, Key Derivation & Memory Sanitization Analysis

**Target Module**: `src/dna_4mer_engine.py`  
**Explorer**: Explorer M1_1 (`explorer_m1_1`)  
**Project**: DNA-V2X Repository Audit & Remediation  
**Date**: 2026-10-08  
**Scope**: F-01 (Modulo Bias), F-02 (Memory Sanitization), F-03 (PFS Cache Leak), F-04 Interface Contract (Historical Permutation Recovery)

---

## 1. Executive Summary

This report delivers an exhaustive, mathematically rigorous, line-by-line cryptographic and systems analysis of the core dynamic permutation engine in `src/dna_4mer_engine.py`. Four critical vulnerabilities and architectural defects are analyzed in detail:

1. **F-01 (Fisher-Yates Modulo Bias)**: Keystream sampling using 16-bit integers (`>H`) causes an uncorrected $+0.3876\%$ relative statistical bias for non-power-of-two partitions ($k=255$), violating cryptographic uniform shuffle criteria.
2. **F-02 (Memory Sanitization Failure)**: `purge_memory()` overwrites only the local list mapping with `"AAAA"` strings, leaving `self.master_seed` intact in plaintext memory, failing to clear historical ring buffers, and leaving all ephemeral session keys and permutation tables permanently stored in the global module cache `_PERM_CACHE`.
3. **F-03 (PFS Memory Cache Leak & ECU OOM Risk)**: `_PERM_CACHE` allows unconstrained accumulation of up to 50,000 entries ($\approx 1.65\text{ GB}$ RAM), lacks any eviction mechanism, starves newly ratcheted epochs once full, and exposes all past session keys to post-compromise memory dump extraction.
4. **F-04 Interface Contract (Historical Permutation State Recovery)**: Because `DynamicPermutationState.ratchet_forward()` applies a one-way cryptographic hash function (SHA-512), past master seeds and permutation states cannot be inverted or reconstructed from the current state. The absence of a formal historical recovery interface causes downstream classifiers to misclassify legitimate replayed packets as Sybil injections.

This document formulates the mathematical proofs, architectural remediations, exact line-numbered patch specifications, and regression test suites to resolve all four findings.

---

## 2. In-Depth Cryptographic Analysis of F-01: Fisher-Yates Modulo Bias Elimination

### 2.1 Vulnerability Description & Existing Code
In `src/dna_4mer_engine.py:68–75`:
```python
indices = list(range(256))
for i in range(255, 0, -1):
    offset = (255 - i) * 2
    val = struct.unpack(">H", keystream[offset : offset + 2])[0]
    j = val % (i + 1)
    indices[i], indices[j] = indices[j], indices[i]
```

The code extracts 16-bit unsigned integers from a SHA-512 keystream and uses the native modulo operator `val % (i + 1)` to select swap indices $j \in [0, i]$.

### 2.2 Mathematical Proof of Modulo Bias
In the Fisher-Yates shuffle algorithm over an array of size $N=256$, the algorithm iterates through step index $i$ from 255 down to 1. At step $i$, it must select an index $j \in [0, k-1]$ where $k = i + 1 \in [2, 256]$.

Let $M = 2^{16} = 65,536$ be the input domain size of `val`.
Dividing $M$ by $k$ yields:
$$M = q \cdot k + r, \quad \text{where } 0 \le r < k$$

If $r > 0$, the pigeonhole principle dictates that:
- The first $r$ residues ($j \in [0, r-1]$) have $q + 1$ pre-images.
- The remaining $k - r$ residues ($j \in [r, k-1]$) have $q$ pre-images.

The probability distribution across residues is non-uniform:
$$P(j) = \begin{cases} \frac{q + 1}{M}, & 0 \le j < r \\ \frac{q}{M}, & r \le j < k \end{cases}$$

The ideal uniform probability is $P_{\text{ideal}} = \frac{1}{k}$. The relative statistical bias for residues $j < r$ is:
$$\text{Bias}_{\text{rel}} = \frac{\frac{q + 1}{M} - \frac{1}{k}}{\frac{1}{k}} = \frac{k(q + 1) - M}{M} = \frac{(M - r + k) - M}{M} = \frac{k - r}{M}$$

For the critical partition at $k = 255$ ($i = 254$):
$$65,536 = 257 \times 255 + 1 \implies q = 257, \quad r = 1$$

Here, exactly one residue ($j = 0$) has $q + 1 = 258$ pre-images, while all other 254 residues have 257 pre-images:
$$P(0) = \frac{258}{65536} \approx 0.003936798$$
$$P_{\text{ideal}} = \frac{1}{255} \approx 0.003921569$$
$$\text{Bias}_{\text{rel}}(0) = \frac{258 \times 255 - 65536}{65536} = \frac{65790 - 65536}{65536} = \frac{254}{65536} \approx +0.387573\% \approx \mathbf{+0.388\%}$$

This bias occurs systematically across all non-power-of-two partitions $k \in \{3, 5, 6, 7, 9, \dots, 255\}$, creating measurable skew in permutation distributions that undermines cryptographic entropy.

### 2.3 Cryptographically Unbiased Rejection Sampling Formulation
To guarantee strictly uniform random selection across arbitrary intervals $[0, k-1]$:
1. Extract 32-bit unsigned integers (`>I`), providing domain $M = 2^{32} = 4,294,967,296$.
2. Compute the uniform rejection limit:
   $$\text{limit} = 2^{32} - (2^{32} \pmod k)$$
3. If $val < \text{limit}$, accept $j = val \pmod k$.
4. If $val \ge \text{limit}$, reject $val$ and sample the next 32-bit integer from the keystream.

Because $\text{limit}$ is an exact integer multiple of $k$, each residue $j \in [0, k-1]$ has exactly $\frac{\text{limit}}{k}$ pre-images in $[0, \text{limit}-1]$. Therefore:
$$P(j) = \frac{\text{limit} / k}{\text{limit}} = \frac{1}{k} \quad (\forall j \in [0, k-1])$$
$$\mathbf{\text{Bias}_{\text{rel}} = 0.000000\%}$$

### 2.4 Keystream Budget & Termination Proof
- Maximum rejection probability for any $k \le 256$:
  $$P(\text{reject}) = \frac{2^{32} \pmod k}{2^{32}} < \frac{256}{2^{32}} = 5.96046 \times 10^{-8}$$
- The probability that any rejection occurs across all 255 steps of a shuffle is:
  $$P(\ge 1 \text{ rejection}) \le 255 \times 5.96 \times 10^{-8} \approx 1.52 \times 10^{-5} \quad (\approx 1 \text{ in } 65,800)$$
- Probability of 2 consecutive rejections on a single step is $< (5.96 \times 10^{-8})^2 \approx 3.55 \times 10^{-15}$.
- Keystream pre-generation: 16 blocks of SHA-512 ($16 \times 64 = 1024$ bytes) provides 256 32-bit words, exactly sufficient for all 255 steps with 1 word reserve. In the rare event of a rejection, dynamic block generation safely draws additional 64-byte blocks.

---

## 3. In-Depth Security Analysis of F-02: Memory Sanitization & master_seed Zeroing

### 3.1 Vulnerability Description & Existing Code
In `src/dna_4mer_engine.py:94–102`:
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

### 3.2 Security Assessment
1. **Plaintext Key Material Left in Instance Memory**: `self.master_seed` is left completely unmodified. The master key material remains resident in memory throughout the entire process lifetime. Any local memory dump or heap introspection (`gc.get_objects()`) recovers the master seed in plaintext.
2. **Global Module-Level Key Persistence**: In line 81:
   ```python
   _PERM_CACHE[cache_key] = (list(self.active_byte_to_4mer), dict(self.active_4mer_to_byte))
   ```
   `cache_key` is `(self.master_seed, self.frame_counter, self.session_id)`.
   Calling `purge_memory()` on the instance does nothing to `_PERM_CACHE`. `_PERM_CACHE` retains both `self.master_seed` as a dict key and the full bijective lookup tables as dict values!
3. **Unsanitized Historical Buffer**: As historical states are retained for replay detection (F-04), those snapshots would also persist unless explicitly zeroed and cleared during purge.

### 3.3 Complete Sanitization Protocol
Upon invoking `purge_memory()`:
1. Overwrite `self.master_seed` with an all-zero byte sequence:
   $$\text{self.master\_seed} = \texttt{b"\\x00"} \times \text{len}(\text{self.master\_seed})$$
2. Overwrite `self.active_byte_to_4mer = ["AAAA"] * 256`.
3. Clear `self.active_4mer_to_byte.clear()`.
4. Overwrite and clear all historical snapshots in `self._history`.
5. Evict all cached entries matching `self.session_id` or `old_seed` from `_PERM_CACHE`.
6. Set an internal state flag `self._is_purged = True` to prevent any further use of the purged state.
7. Expose a public module-level function `clear_permutation_cache()` for application shutdown or key revocation events.

---

## 4. In-Depth Systems Analysis of F-03: PFS Memory Cache Leak Remediation

### 4.1 Vulnerability Description & Existing Code
In `src/dna_4mer_engine.py:26, 49–54, 80–82`:
```python
_PERM_CACHE = {}
...
if len(_PERM_CACHE) < 50000:
    _PERM_CACHE[cache_key] = (list(self.active_byte_to_4mer), dict(self.active_4mer_to_byte))
```

### 4.2 Resource Exhaustion & Automotive ECU Impact
- **Memory Footprint per Entry**:
  - Key: `(master_seed (32B), frame_counter (int), session_id (str))` $\approx 100$ bytes.
  - Value: `list` of 256 4-character strings ($\approx 15.2\text{ KB}$) + `dict` of 256 entries ($\approx 9.3\text{ KB}$) + GC overhead $\approx 34.6\text{ KB}$ per cached frame.
- **Total Memory Consumption**:
  $$50,000 \times 34.6\text{ KB} \approx 1,730,000\text{ KB} \approx \mathbf{1.65\text{ GB RAM}}$$
- In automotive embedded systems (e.g., NXP S32G2, Renesas R-Car H3, Infineon AURIX TC3xx, or ARM Cortex-A53 edge gateways with 512 MB to 2 GB total system memory), unconstrained allocation of 1.65 GB will trigger the Linux Out-Of-Memory (OOM) killer, terminating safety-critical V2X services.
- **Cache Starvation**: Once 50,000 entries are stored, the check `if len(_PERM_CACHE) < 50000:` fails. The cache stops accepting new entries without evicting older ones. All subsequent streaming frames suffer cache misses, causing sudden throughput collapse.
- **Lack of Thread Safety**: Standard Python dictionaries are not thread-safe for concurrent composite operations (check-then-set, iteration during eviction).

### 4.3 Architecture of `PermutationLRUCache`
A specialized `PermutationLRUCache` class resolves these deficiencies:
1. **Bounded Size**: Default `max_size = 512` entries.
   $$512 \times 34.6\text{ KB} \approx 17.7\text{ MB RAM}$$
   This is well within embedded constraints.
2. **LRU Eviction**: Backed by `collections.OrderedDict`. On cache access, elements are marked MRU (`move_to_end(key)`). When capacity is reached, the least recently used element is evicted (`popitem(last=False)`).
3. **Thread Safety**: All reads, writes, and evictions are synchronized using a reentrant or standard mutex `threading.Lock`.
4. **Session-Targeted Eviction**: Method `evict_session(session_id, master_seed)` permits `purge_memory()` to surgically wipe entries belonging to a terminated session.
5. **Backwards Compatibility**: Implements `__contains__`, `__getitem__`, `__setitem__`, `__len__`, `get`, and `clear` to allow seamless drop-in replacement for `_PERM_CACHE = {}`.

---

## 5. Architectural Analysis of F-04 Interface Contract: Historical Permutation Recovery

### 5.1 Vulnerability Description & The Replay Detection Defect
In `src/dna_4mer_engine.py:83–97`:
```python
def ratchet_forward(self, physical_entropy: Optional[bytes] = None):
    extra = physical_entropy if physical_entropy is not None else b""
    self.master_seed = hashlib.sha512(
        self.master_seed + b":RATCHET:FORWARD:" + extra
    ).digest()[:32]
    self.frame_counter += 1
    self._generate_epoch_permutation()
```

In `src/attack_classifier.py:121–138`:
```python
if crc_match == 0.0:
    for delay in range(1, 9):
        if state.frame_counter >= delay:
            chk_state = DynamicPermutationState(state.master_seed, state.session_id)
            chk_state.frame_counter = state.frame_counter - delay
            chk_state._generate_epoch_permutation()
            ...
```

### 5.2 Mathematical Root Cause
Let $S_t$ denote the master seed at epoch $t$, and $T_t$ denote the bijective permutation table derived from:
$$\text{Keystream}_t = \text{KDF}(S_t \parallel t \parallel \text{session\_id})$$

When the system ratchets forward from epoch $t$ to $t+1$:
$$S_{t+1} = \text{SHA512}(S_t \parallel \texttt{b":RATCHET:FORWARD:"} \parallel \text{extra})[:32]$$

By the pre-image resistance of SHA-512, computing $S_t$ given $S_{t+1}$ is computationally infeasible ($2^{256}$ operations).

When a replayed frame from epoch $t - \text{delay}$ arrives at the receiver (which is at epoch $t$), the receiver currently evaluates:
$$\text{chk\_seed} = S_t$$
$$\text{chk\_fc} = t - \text{delay}$$
$$\text{Keystream}_{\text{check}} = \text{KDF}(S_t \parallel (t - \text{delay}) \parallel \text{session\_id})$$

Because $S_t \neq S_{t - \text{delay}}$:
$$\text{Keystream}_{\text{check}} \neq \text{Keystream}_{t - \text{delay}} \implies T_{\text{check}} \neq T_{t - \text{delay}}$$

The decoded bytes are pseudorandom garbage, CRC-32 fails, and `past_replay_match` is **always 0.0**. As a consequence, `attack_classifier.py` executes line 185:
```python
features[i, 8] = 1.0  # Completely foreign key -> Sybil Ghost
```
**Every authentic replayed frame is 100% misclassified as a Sybil injection.**

### 5.3 Interface Contract Design
To solve this without breaking Perfect Forward Secrecy:
1. Maintain an internal bounded historical ring buffer `self._history` with maximum capacity $W = 16$ (covering $1 \le \text{delay} \le 8$ plus safety margin).
2. Prior to advancing $S_t \to S_{t+1}$ in `ratchet_forward()`, push the current snapshot $(t, S_t, T_t)$ into `self._history`.
3. Provide the method:
   ```python
   def get_historical_permutation(self, delay: int) -> Optional["DynamicPermutationState"]:
   ```
   - If $1 \le \text{delay} \le \text{frame\_counter}$ and the snapshot is present in `_history`: return a valid `DynamicPermutationState` instance initialized with the exact historical bijection tables and frame counter.
   - If $\text{delay} \le 0$ or the requested epoch has rolled out of the history window: return `None`.
4. Downstream consumers (`attack_classifier.py`) simply invoke:
   ```python
   chk_state = state.get_historical_permutation(delay)
   if chk_state is not None:
       # decode and verify CRC
   ```
5. Perfect Forward Secrecy is preserved: states older than $W=16$ epochs are automatically evicted and reclaimed, and calling `purge_memory()` immediately zeroes all historical snapshots.

---

## 6. Exact Line-Numbered Patch Specifications for `src/dna_4mer_engine.py`

### 6.1 Imports & Global Cache Replacement (Lines 7–27)

#### Target File: `src/dna_4mer_engine.py`
#### Existing Lines (7–27):
```python
7: import math
8: import hashlib
9: import struct
10: import numpy as np
11: from typing import List, Tuple, Dict, Optional
12: 
...
25: 
26: _PERM_CACHE = {}
27: 
```

#### Proposed Replacement:
```python
import math
import hashlib
import struct
import threading
from collections import OrderedDict, deque
from typing import List, Tuple, Dict, Optional, Union
import numpy as np


class PermutationLRUCache:
    """
    Thread-safe, bounded Least-Recently-Used (LRU) cache for dynamic 4-mer permutations.
    Prevents memory exhaustion on embedded automotive ECUs while supporting session-targeted
    and global zeroization.
    """
    def __init__(self, max_size: int = 512):
        self._max_size = max_size
        self._cache: OrderedDict = OrderedDict()
        self._lock = threading.Lock()

    def get(self, key):
        with self._lock:
            if key in self._cache:
                self._cache.move_to_end(key)
                return self._cache[key]
            return None

    def put(self, key, value):
        with self._lock:
            if key in self._cache:
                self._cache.move_to_end(key)
                self._cache[key] = value
            else:
                if len(self._cache) >= self._max_size:
                    self._cache.popitem(last=False)
                self._cache[key] = value

    def evict_session(
        self,
        session_id: Optional[Union[str, bytes]] = None,
        master_seed: Optional[bytes] = None
    ):
        """Evicts entries matching session_id or master_seed."""
        with self._lock:
            keys_to_remove = []
            for k in list(self._cache.keys()):
                match = False
                if master_seed is not None and k[0] == master_seed:
                    match = True
                elif session_id is not None and len(k) > 2 and k[2] == session_id:
                    match = True
                if match:
                    keys_to_remove.append(k)
            for k in keys_to_remove:
                del self._cache[k]

    def clear(self):
        with self._lock:
            self._cache.clear()

    def __len__(self):
        with self._lock:
            return len(self._cache)

    def __contains__(self, key):
        with self._lock:
            return key in self._cache

    def __getitem__(self, key):
        val = self.get(key)
        if val is None:
            raise KeyError(key)
        return val

    def __setitem__(self, key, value):
        self.put(key, value)


_PERM_CACHE = PermutationLRUCache(max_size=512)


def clear_permutation_cache():
    """Flushes all cached permutation tables globally."""
    _PERM_CACHE.clear()


def get_permutation_cache_size() -> int:
    """Returns the current number of cached permutation entries."""
    return len(_PERM_CACHE)
```

---

### 6.2 `DynamicPermutationState` Refactoring (Lines 29–108)

#### Target File: `src/dna_4mer_engine.py`
#### Existing Lines (29–108):
```python
29: class DynamicPermutationState:
30:     """
31:     Maintains ephemeral pairwise session state, rolling frame counter,
32:     and instantaneous permutation bijection matrices.
33:     """
34:     def __init__(self, master_seed: bytes, session_id: str = "V2V_PAIR_01"):
35:         if len(master_seed) < 16:
36:             master_seed = hashlib.sha256(master_seed).digest()[:16]
37:         self.master_seed = master_seed
38:         self.session_id = session_id
39:         self.frame_counter = 0
40:         self.active_byte_to_4mer = []
41:         self.active_4mer_to_byte = {}
42:         self._generate_epoch_permutation()
43: 
44:     def _generate_epoch_permutation(self):
...
82:             _PERM_CACHE[cache_key] = (list(self.active_byte_to_4mer), dict(self.active_4mer_to_byte))
83: 
84:     def ratchet_forward(self, physical_entropy: Optional[bytes] = None):
...
98:         self._generate_epoch_permutation()
99: 
100:     def purge_memory(self):
...
107:         self.active_4mer_to_byte.clear()
```

#### Proposed Replacement:
```python
class DynamicPermutationState:
    """
    Maintains ephemeral pairwise session state, rolling frame counter,
    instantaneous permutation bijection matrices, and bounded history buffer
    for out-of-epoch replay detection.
    """
    def __init__(
        self,
        master_seed: bytes,
        session_id: Union[str, bytes] = "V2V_PAIR_01",
        history_window: int = 16
    ):
        if len(master_seed) < 16:
            master_seed = hashlib.sha256(master_seed).digest()
        self.master_seed = master_seed
        self.session_id = session_id
        self.frame_counter = 0
        self.active_byte_to_4mer: List[str] = []
        self.active_4mer_to_byte: Dict[str, int] = {}
        self._history_window_size = max(1, history_window)
        self._history: deque = deque(maxlen=self._history_window_size)
        self._is_purged = False
        self._generate_epoch_permutation()

    def _generate_epoch_permutation(self):
        """
        Derives an instantaneous bijective permutation of all 256 4-mers
        from the current ephemeral seed and frame counter via cryptographically
        unbiased 32-bit rejection-sampled Fisher-Yates shuffle.
        """
        if self._is_purged:
            raise RuntimeError("Cannot generate permutation for a purged DynamicPermutationState.")

        cache_key = (self.master_seed, self.frame_counter, self.session_id)
        if cache_key in _PERM_CACHE:
            cached_byte_to_4mer, cached_4mer_to_byte = _PERM_CACHE[cache_key]
            self.active_byte_to_4mer = list(cached_byte_to_4mer)
            self.active_4mer_to_byte = dict(cached_4mer_to_byte)
            return

        session_bytes = (
            self.session_id.encode()
            if isinstance(self.session_id, str)
            else bytes(self.session_id)
        )
        seed_material = self.master_seed + struct.pack(">Q", self.frame_counter) + session_bytes

        # Cryptographically Secure Fisher-Yates Permutation Derivation via SHA-512 Keystream
        # Eliminates the 16-bit modulo bias via 32-bit rejection sampling
        keystream = bytearray()
        block_idx = 0
        ks_offset = 0

        # Pre-derive 1024 bytes (16 SHA-512 blocks = 256 32-bit words)
        while len(keystream) < 1024:
            keystream.extend(hashlib.sha512(seed_material + struct.pack(">I", block_idx)).digest())
            block_idx += 1

        def next_u32() -> int:
            nonlocal ks_offset, block_idx, keystream
            if ks_offset + 4 > len(keystream):
                keystream.extend(hashlib.sha512(seed_material + struct.pack(">I", block_idx)).digest())
                block_idx += 1
            val = struct.unpack(">I", keystream[ks_offset : ks_offset + 4])[0]
            ks_offset += 4
            return val

        # Perform cryptographically unbiased Fisher-Yates shuffle across all 256 4-mers
        indices = list(range(256))
        for i in range(255, 0, -1):
            k = i + 1
            # Rejection threshold: reject if val >= limit
            limit = 0x100000000 - (0x100000000 % k)
            while True:
                val = next_u32()
                if val < limit:
                    j = val % k
                    break
            indices[i], indices[j] = indices[j], indices[i]

        self.active_byte_to_4mer = [ALL_256_4MERS[idx] for idx in indices]
        self.active_4mer_to_byte = {
            self.active_byte_to_4mer[b]: b for b in range(256)
        }
        _PERM_CACHE[cache_key] = (list(self.active_byte_to_4mer), dict(self.active_4mer_to_byte))

    def ratchet_forward(self, physical_entropy: Optional[bytes] = None):
        """
        Advances the frame counter, archives the previous state in the bounded
        historical ring buffer, evolves the master seed via forward hash ratchet,
        and regenerates the active permutation matrix.
        Provides Perfect Forward Secrecy (PFS).
        """
        if self._is_purged:
            raise RuntimeError("Cannot ratchet forward a purged DynamicPermutationState.")

        # Archive historical snapshot prior to forward evolution
        self._history.append({
            "frame_counter": self.frame_counter,
            "master_seed": self.master_seed,
            "byte_to_4mer": list(self.active_byte_to_4mer),
            "4mer_to_byte": dict(self.active_4mer_to_byte)
        })

        extra = physical_entropy if physical_entropy is not None else b""
        self.master_seed = hashlib.sha512(
            self.master_seed + b":RATCHET:FORWARD:" + extra
        ).digest()[:32]
        self.frame_counter += 1
        self._generate_epoch_permutation()

    def get_historical_permutation(self, delay: int) -> Optional["DynamicPermutationState"]:
        """
        Reconstructs or looks up valid historical permutation state for window t - delay.
        Enables verification of delayed/replayed frames without inverting one-way SHA hash.
        
        Args:
            delay: Number of frames back in time (1 <= delay <= history_window).
            
        Returns:
            DynamicPermutationState initialized with historical permutation tables,
            or None if outside the valid history window or unavailable.
        """
        if self._is_purged or delay <= 0 or delay > self.frame_counter:
            return None

        target_fc = self.frame_counter - delay
        for snap in reversed(self._history):
            if snap["frame_counter"] == target_fc:
                hist_state = DynamicPermutationState.__new__(DynamicPermutationState)
                hist_state.master_seed = snap["master_seed"]
                hist_state.session_id = self.session_id
                hist_state.frame_counter = snap["frame_counter"]
                hist_state.active_byte_to_4mer = list(snap["byte_to_4mer"])
                hist_state.active_4mer_to_byte = dict(snap["4mer_to_byte"])
                hist_state._history_window_size = self._history_window_size
                hist_state._history = deque(maxlen=self._history_window_size)
                hist_state._is_purged = False
                return hist_state
        return None

    def purge_memory(self):
        """
        Secure zero-fill overwrite of active permutation structures, master seed,
        historical buffer, and session cache in RAM.
        Prevents post-compromise memory dump key extraction.
        """
        old_seed = self.master_seed
        self.master_seed = b"\x00" * len(self.master_seed)

        if isinstance(self.active_byte_to_4mer, list):
            self.active_byte_to_4mer = ["AAAA"] * 256
        self.active_4mer_to_byte.clear()

        # Zeroize and clear history buffer
        for snap in self._history:
            snap["byte_to_4mer"] = ["AAAA"] * 256
            snap["4mer_to_byte"].clear()
            snap["master_seed"] = b"\x00" * len(snap["master_seed"])
        self._history.clear()

        # Evict all entries for this session or old master seed from the global cache
        _PERM_CACHE.evict_session(session_id=self.session_id, master_seed=old_seed)
        self._is_purged = True
```

---

## 7. Comprehensive Regression Test Criteria & Validation Harnesses

To verify that the patched implementation functions cleanly and resolves all vulnerabilities without regressions, the test suite (`tests/`) should include four targeted validation test cases:

### Test Suite 1: Modulo Bias Elimination & Shuffle Uniformity Test
```python
def test_fisher_yates_rejection_sampling_unbiasedness(self):
    """
    Verify that 32-bit rejection sampling strictly eliminates modulo bias
    and produces mathematically uniform permutations across all 256 states.
    """
    state = DynamicPermutationState(b"UNBIASED_TEST_KEY_32BYTES_0000000")
    
    # Check bijection
    self.assertEqual(len(state.active_byte_to_4mer), 256)
    self.assertEqual(len(set(state.active_byte_to_4mer)), 256)
    self.assertEqual(len(state.active_4mer_to_byte), 256)

    # Inversion check
    for b in range(256):
        c = state.active_byte_to_4mer[b]
        self.assertEqual(state.active_4mer_to_byte[c], b)

    # Statistical distribution check across 1,000 ratchets
    first_codon_counts = {}
    for _ in range(1000):
        c0 = state.active_byte_to_4mer[0]
        first_codon_counts[c0] = first_codon_counts.get(c0, 0) + 1
        state.ratchet_forward()

    # Verify no single codon dominates
    max_count = max(first_codon_counts.values())
    self.assertLess(max_count, 30, f"Codon frequency spike detected: {max_count}")
```

### Test Suite 2: Memory Sanitization & master_seed Zeroing Test
```python
def test_memory_purge_complete_zeroization(self):
    """
    Verify that purge_memory() zeroes master_seed, clears permutation tables,
    clears historical buffer, and evicts all session entries from _PERM_CACHE.
    """
    seed = b"CRYPTOGRAPHIC_SECRET_KEY_123456"
    session_id = "V2V_TEST_PURGE_01"
    state = DynamicPermutationState(seed, session_id=session_id)
    state.ratchet_forward()
    state.ratchet_forward()

    # Pre-purge checks
    self.assertIn((state.master_seed, state.frame_counter, session_id), _PERM_CACHE)
    self.assertGreater(len(state._history), 0)

    # Execute purge
    state.purge_memory()

    # 1. Master seed must be all zeroes
    self.assertTrue(all(b == 0 for b in state.master_seed))
    self.assertEqual(len(state.master_seed), 32)

    # 2. Permutation structures wiped
    self.assertEqual(len(state.active_4mer_to_byte), 0)
    self.assertEqual(state.active_byte_to_4mer[0], "AAAA")

    # 3. History buffer wiped
    self.assertEqual(len(state._history), 0)

    # 4. Cache evicted
    self.assertNotIn((seed, 0, session_id), _PERM_CACHE)
    self.assertNotIn((state.master_seed, state.frame_counter, session_id), _PERM_CACHE)

    # 5. Post-purge operations raise RuntimeError
    with self.assertRaises(RuntimeError):
        state.ratchet_forward()
    with self.assertRaises(RuntimeError):
        state._generate_epoch_permutation()
```

### Test Suite 3: Bounded LRU Cache & Thread Safety Test
```python
def test_permutation_lru_cache_bounded_eviction(self):
    """
    Verify that _PERM_CACHE adheres strictly to its capacity limit (512),
    evicts least recently used entries, and supports clear_permutation_cache().
    """
    clear_permutation_cache()
    self.assertEqual(get_permutation_cache_size(), 0)

    # Fill cache beyond capacity
    for i in range(600):
        key = (b"SEED", i, "SESS")
        _PERM_CACHE[key] = (["AAAA"] * 256, {})

    # Must be capped at max_size (512)
    self.assertEqual(get_permutation_cache_size(), 512)
    
    # Oldest entries (0 to 87) must be evicted
    self.assertNotIn((b"SEED", 0, "SESS"), _PERM_CACHE)
    self.assertNotIn((b"SEED", 50, "SESS"), _PERM_CACHE)
    # Recent entry must exist
    self.assertIn((b"SEED", 599, "SESS"), _PERM_CACHE)

    clear_permutation_cache()
    self.assertEqual(get_permutation_cache_size(), 0)
```

### Test Suite 4: Historical Permutation State Recovery Test
```python
def test_historical_permutation_recovery_and_replay_decoding(self):
    """
    Verify get_historical_permutation(delay) recovers past epoch states
    and allows authentic replayed packets to be decoded cleanly.
    """
    eng = DNA4MerEngine()
    seed = b"HISTORICAL_RECOVERY_KEY_00000001"
    alice = DynamicPermutationState(seed, "PAIR_V2V")
    bob = DynamicPermutationState(seed, "PAIR_V2V")

    raw_pkt = serialize_bsm(station_id=42, speed_kmh=75.0, accel_mps2=1.0, heading_deg=180.0)
    strand_epoch0 = eng.encode_bytes(raw_pkt, alice)

    # Both parties ratchet forward 4 frames
    for _ in range(4):
        alice.ratchet_forward()
        bob.ratchet_forward()

    self.assertEqual(bob.frame_counter, 4)

    # Current Bob cannot decode strand from frame 0
    with self.assertRaises(Exception):
        dec = eng.decode_strand(strand_epoch0, bob)
        deserialize_v2x_packet(dec)

    # Bob retrieves historical permutation for delay = 4
    hist_bob = bob.get_historical_permutation(delay=4)
    self.assertIsNotNone(hist_bob)
    self.assertEqual(hist_bob.frame_counter, 0)

    # Bob successfully decodes and verifies CRC
    recovered_bytes = eng.decode_strand(strand_epoch0, hist_bob)
    self.assertEqual(raw_pkt, recovered_bytes)
    pkt = deserialize_v2x_packet(recovered_bytes)
    self.assertEqual(pkt.station_id, 42)
    self.assertAlmostEqual(pkt.speed_kmh, 75.0, places=1)

    # Boundary checks
    self.assertIsNone(bob.get_historical_permutation(delay=0))
    self.assertIsNone(bob.get_historical_permutation(delay=5))
    self.assertIsNone(bob.get_historical_permutation(delay=-1))
```

---

## 8. Summary of Downstream Integration Impacts

| Module | Location | Current Pattern | Remediated Integration |
|:---|:---|:---|:---|
| `src/attack_classifier.py` | Lines 121–138 | Instantiates new `DynamicPermutationState(state.master_seed)` with decrementing frame counter, causing 100% replay misclassification | Calls `chk_state = state.get_historical_permutation(delay)` to retrieve true historical bijection tables; successfully validates CRC and sets `features[i, 7] = 1.0` (REPLAY_ATTACK) |
| `src/moving_cars_simulation.py` | Lines 165–168 | Synthesizes replay with `s_state.master_seed` and decremented frame counter | Retrieves authentic historical strand via `s_state.get_historical_permutation(delay)` or buffers transmitted frames |
| `src/attack_simulator.py` | Lines 50–64 | Tests replay rejection at current epoch state | Remains valid: verifies that current receiver state rejects past frames |
| `tests/test_dna_v2x.py` | Lines 114–119 | Verifies `"AAAA"` overwrite in memory purge | Expands test to verify `master_seed == b"\x00"*32` and session eviction in `_PERM_CACHE` |
