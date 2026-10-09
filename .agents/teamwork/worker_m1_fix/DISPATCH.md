# DISPATCH — Worker M1 Fix (Consolidated Classifier Remediation)

## Role & Scope
You are Worker M1 Fix. Your task is to apply the consolidated fixes for BUG-01, FLAW-02, and ANOMALY-03 directly to `src/attack_classifier.py`.
File exclusively owned: `src/attack_classifier.py`

## Explorer Patch References
1. BUG-01 (Integer Overflow on Windows):
   `C:\Users\umert\.gemini\antigravity\scratch\DNA-V2X\.agents\teamwork\explorer_m1_fix1\bug01_integer_overflow.patch`
   `C:\Users\umert\.gemini\antigravity\scratch\DNA-V2X\.agents\teamwork\explorer_m1_fix1\analysis.md`
2. FLAW-02 (Replay Window Truncation):
   `C:\Users\umert\.gemini\antigravity\scratch\DNA-V2X\.agents\teamwork\explorer_m1_fix2\flaw_02_replay_window.patch`
   `C:\Users\umert\.gemini\antigravity\scratch\DNA-V2X\.agents\teamwork\explorer_m1_fix2\analysis.md`
3. ANOMALY-03 (Low-Delay Replay Discrimination):
   `C:\Users\umert\.gemini\antigravity\scratch\DNA-V2X\.agents\teamwork\explorer_m1_fix3\proposed_attack_classifier.patch`
   `C:\Users\umert\.gemini\antigravity\scratch\DNA-V2X\.agents\teamwork\explorer_m1_fix3\analysis.md`

## Mandatory Integrity Warning
DO NOT CHEAT. All implementations must be genuine. DO NOT hardcode test results, create dummy/facade implementations, or circumvent the intended task. A forensic auditor will independently verify your work. Integrity violations WILL be detected and your work WILL be rejected.

## Tasks
1. In `src/attack_classifier.py`:
   - Cast all timestamp difference calculations (`curr_time`, `parsed_ts`, `ts_diff`) to native Python `int` to prevent unsigned 32-bit scalar subtraction overflow on 64-bit Windows.
   - Dynamically search up to the full history window (`max_history = min(getattr(state, "frame_counter", 0), getattr(state, "_history_window_size", 16))`) over `range(1, max_history + 1)`.
   - Update the drift threshold for replayed frames from `> 200.0` to `> 50.0` ms so 10 Hz replays at $d=1$ (100 ms) and $d=2$ (200 ms) correctly classify as Class 1 `REPLAY_ATTACK`.
2. Verification:
   - Run `python tests/adversarial_ratchet_replay.py` and verify all delays $d = 1 \dots 15$ pass cleanly.
   - Run `python -m unittest discover tests/ -v` and verify 100% pass rate.
   - Run `python -m unittest tests/e2e/test_dna_v2x_e2e.py -v`.
3. Deliver handoff report to `C:\Users\umert\.gemini\antigravity\scratch\DNA-V2X\.agents\teamwork\worker_m1_fix\handoff.md`.

## 2026-10-08T19:54:49Z
[Message] timestamp=2026-10-08T19:54:49Z sender=8e427327-1383-435e-84f9-65791f49405e priority=MESSAGE_PRIORITY_HIGH content=You are Worker M1 Fix (Consolidated Classifier Remediation).
Your Working Directory: C:\Users\umert\.gemini\antigravity\scratch\DNA-V2X\.agents\teamwork\worker_m1_fix
Project Root: C:\Users\umert\.gemini\antigravity\scratch\DNA-V2X
Authoritative Request: C:\Users\umert\.gemini\antigravity\scratch\DNA-V2X\.agents\teamwork\ORIGINAL_REQUEST.md
Dispatch: C:\Users\umert\.gemini\antigravity\scratch\DNA-V2X\.agents\teamwork\worker_m1_fix\DISPATCH.md

Explorer Patch Specifications:
- BUG-01 (Overflow on Windows): C:\Users\umert\.gemini\antigravity\scratch\DNA-V2X\.agents\teamwork\explorer_m1_fix1\bug01_integer_overflow.patch
- FLAW-02 (Replay Window Truncation): C:\Users\umert\.gemini\antigravity\scratch\DNA-V2X\.agents\teamwork\explorer_m1_fix2\flaw_02_replay_window.patch
- ANOMALY-03 (Low-Delay Replay): C:\Users\umert\.gemini\antigravity\scratch\DNA-V2X\.agents\teamwork\explorer_m1_fix3\proposed_attack_classifier.patch

MANDATORY INTEGRITY WARNING:
DO NOT CHEAT. All implementations must be genuine. DO NOT hardcode test results, create dummy/facade implementations, or circumvent the intended task. A forensic auditor will independently verify your work. Integrity violations WILL be detected and your work WILL be rejected.

File Exclusively Owned: `src/attack_classifier.py`

Apply the consolidated fixes to `src/attack_classifier.py`:
1. Native Python `int` coercion for timestamp calculations to eliminate OverflowError.
2. Dynamic history window query `range(1, max_history + 1)` where `max_history = min(getattr(state, "frame_counter", 0), getattr(state, "_history_window_size", 16))`.
3. Set drift threshold to `50.0 ms`.

Run all test suites and verification harnesses:
- `python tests/adversarial_ratchet_replay.py`
- `python -m unittest discover tests/ -v`
- `python -m unittest tests/e2e/test_dna_v2x_e2e.py -v`

Write handoff to `C:\Users\umert\.gemini\antigravity\scratch\DNA-V2X\.agents\teamwork\worker_m1_fix\handoff.md` and send a message when complete.
