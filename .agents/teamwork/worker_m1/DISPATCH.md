## 2026-10-08T19:03:31Z
You are Worker M1 (Milestone 1 Worker: Core Cryptography, Schemas & Numerical Remediation).
Your Working Directory: C:\Users\umert\.gemini\antigravity\scratch\DNA-V2X\.agents\teamwork\worker_m1
Project Root: C:\Users\umert\.gemini\antigravity\scratch\DNA-V2X
Authoritative Request: C:\Users\umert\.gemini\antigravity\scratch\DNA-V2X\.agents\teamwork\ORIGINAL_REQUEST.md
Scope Document: C:\Users\umert\.gemini\antigravity\scratch\DNA-V2X\PROJECT.md

Explorer Analysis Reports (Read these before implementing):
- Crypto/Memory: C:\Users\umert\.gemini\antigravity\scratch\DNA-V2X\.agents\teamwork\explorer_m1_1\analysis.md
- Schemas/Physics: C:\Users\umert\.gemini\antigravity\scratch\DNA-V2X\.agents\teamwork\explorer_m1_2\analysis.md
- Classifier/Profiler: C:\Users\umert\.gemini\antigravity\scratch\DNA-V2X\.agents\teamwork\explorer_m1_3\analysis.md

MANDATORY INTEGRITY WARNING:
DO NOT CHEAT. All implementations must be genuine. DO NOT hardcode test results, create dummy/facade implementations, or circumvent the intended task. A teamwork_preview_auditor will independently verify your work. Integrity violations WILL be detected and your work WILL be rejected.

File Write Boundaries (Exclusively owned):
- src/dna_4mer_engine.py
- src/v2x_telemetry_schema.py
- src/moving_cars_simulation.py
- src/attack_classifier.py
- src/energy_profiler.py

Tasks:
1. Implement in `src/dna_4mer_engine.py`:
   - 32-bit cryptographically unbiased rejection sampling for Fisher-Yates shuffle.
   - Master seed zeroing in `purge_memory()` and session eviction from cache.
   - `PermutationLRUCache` (512 entries max, thread-safe, LRU eviction, memory wiping).
   - Historical ring buffer `_history = deque(maxlen=16)` and `get_historical_permutation(delay: int) -> Optional[DynamicPermutationState]`.
2. Implement in `src/v2x_telemetry_schema.py`:
   - Multi-protocol deserializer in `deserialize_v2x_packet()` decoding BSM, CAM, SPaT, and DENM frames without field layout corruption. Add `countdown_sec` field to `V2XTelemetryPacket`.
   - Explicit `isnan()`/`isinf()` validation (raising `ValueError`) and boundary clamping for finite ranges.
3. Implement in `src/moving_cars_simulation.py`:
   - Authentic Intelligent Driver Model (IDM) car-following kinematics grouped by lane in `step_physics()`.
   - Monotonic simulation timestamp advancement across streaming batches.
4. Implement in `src/attack_classifier.py`:
   - Replay attack classification using `state.get_historical_permutation(delay)` in `extract_features_vectorized()` so legitimate replayed frames yield `f7 = 1.0` and Class 1 REPLAY_ATTACK.
   - Rule precedence fix in `classify_batch_fast()` so truncated packets classify as Class 2 MUTATION_TAMPER.
   - Hybrid decision boundary arbitration activating `HistGradientBoostingClassifier.predict()` for ambiguous/borderline samples.
5. Implement in `src/energy_profiler.py`:
   - `tracemalloc` peak heap tracking, CPU thread timing, and calibrated TDP energy modeling.
6. Verify your implementation:
   - Run `python -m unittest discover tests/ -v` and ensure 100% of tests pass cleanly.
   - Run verification commands proving each flaw (F-01 through F-10) is resolved.
7. Write your handoff report to `C:\Users\umert\.gemini\antigravity\scratch\DNA-V2X\.agents\teamwork\worker_m1\handoff.md` and send a message when done.
