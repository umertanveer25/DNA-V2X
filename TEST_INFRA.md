# DNA-V2X: End-to-End Test Infrastructure Specification (TEST_INFRA.md)

## 1. Executive Summary & Document Overview

This document specifies the authoritative, opaque-box, requirement-driven test infrastructure for **DNA-V2X** (Ultra-Lightweight Ephemeral Genomic Cryptography and Cyber-Physical Threat Mitigation for Vehicle-to-Everything Networks).

The testing framework is architected strictly according to the **4-Tier Testing Methodology**:
- **Tier 1: Functional Feature Coverage** ($\ge 5$ test cases per feature across all core protocols and cryptographic subsystems).
- **Tier 2: Boundary Value Analysis & Edge Cases** ($\ge 5$ test cases per feature across extremal values, malformed inputs, numerical limits, and invalid states).
- **Tier 3: Cross-Feature Pairwise Interactions** (Systematic combinatorial testing of interdependent subsystems under concurrency, active attacks, and state evolutions).
- **Tier 4: Real-World Vehicular Workload Scenarios** ($\ge 5$ comprehensive, end-to-end multi-vehicle workload scenarios modeling realistic mobility, safety alerts, signal transitions, and adversarial environments).

All test cases are derived from the foundational requirements defined in `ORIGINAL_REQUEST.md`, `PROJECT.md`, SAE J2735 (BSM / SPaT), and ETSI EN 302 637-2 (CAM / DENM).

---

## 2. Test Philosophy: Opaque-Box, Requirement-Driven Methodology

### 2.1 Principle of Opaque-Box Evaluation
The DNA-V2X end-to-end test suite evaluates the system strictly via public interfaces, published schemas, observable protocol exchanges, and external behavioral contracts. Tests have **zero reliance** on implementation-private variables, monkey-patching, or internal branching assumptions.

### 2.2 Authority and Traceability
Expected outputs for every test case are established through authoritative derivations:
1. **Standards Specification**: Binary packing structures, bit allocations, byte widths, coordinate scaling factors ($10^7$ scaling for latitude/longitude), speed resolution ($10^{-2}$ m/s), and message identification tags conform to SAE J2735 and ETSI EN 302.
2. **Cryptographic Invariants**: The 4-mer codon universe is mathematically closed and bijective:
   $$\mathcal{U}_{4} = \{ (b_0, b_1, b_2, b_3) \mid b_i \in \{A, C, G, T\} \}, \quad |\mathcal{U}_{4}| = 4^4 = 256$$
   Every byte $b \in [0, 255]$ maps to a unique 4-mer under ephemeral permutation $\Pi_t$. Decryption is the exact algebraic inverse $\Pi_t^{-1}(\Pi_t(b)) = b$.
3. **Avalanche & Diffusion**: Genomic-SPN 2-pass diffusion guarantees avalanche effect where a 1-bit input alteration produces $\ge 40\%$ nucleotide variation in the 128-nucleotide ciphertext strand.
4. **Information Entropy**: Uniform byte distributions produce Shannon entropy approaching $H = -\sum_{i=1}^{256} p_i \log_2(p_i) \to 8.0$ bits/byte. Repetitive probes yield $H < 2.0$.

### 2.3 Progressive Testability & Deterministic Verification
Each test is fully self-contained, initializes its own cryptographic state, executes in bounded execution time ($< 100$ ms per test method), and cleans up resources. Non-deterministic elements (such as system timestamps or PRNG seeds) use fixed test fixtures or relative time drift tolerances.

---

## 3. Feature Inventory & Scope Mapping

The test suite systematically maps and verifies all features from the project architecture and audit inventory:

| Feature ID | Architectural Subsystem | Scope & Functionality | Tier Mapping |
|:---|:---|:---|:---|
| **F-01** | `src.v2x_telemetry_schema` | **BSM Telemetry Encoding/Decoding**: SAE J2735 Basic Safety Message 32-byte packing, kinematics, spatial coordinates, safety masks, and CRC-32 integrity. | Tier 1, Tier 2, Tier 3, Tier 4 |
| **F-02** | `src.v2x_telemetry_schema` | **SPaT Infrastructure Encoding**: SAE J2735 Signal Phase & Timing 32-byte serialization, phase IDs, countdown durations, intersection station IDs. | Tier 1, Tier 2, Tier 3, Tier 4 |
| **F-03** | `src.v2x_telemetry_schema` | **DENM Hazard Notification**: ETSI EN 302 637-2 Decentralized Environmental Notification Message 32-byte format, emergency cause codes, broadcast alerts. | Tier 1, Tier 2, Tier 3, Tier 4 |
| **F-04** | `src.dna_4mer_engine` | **Genomic 4-Mer Ephemeral Cipher**: 256-state bijective substitution, dynamic permutation generation, forward hash ratchet evolution (PFS), Genomic-SPN avalanche diffusion, and secure RAM purge. | Tier 1, Tier 2, Tier 3, Tier 4 |
| **F-05** | `src.v2x_telemetry_schema` | **Lightweight Cryptographic MAC**: 4-byte truncated HMAC-SHA256 constant-time verification for authenticated vehicular telemetry mode. | Tier 1, Tier 2, Tier 3 |
| **F-06** | `src.attack_simulator` | **Cyber-Physical Threat Invalidation**: Replay attacks, nucleotide mutation/bit-flipping, Sybil ghost vehicle injection, low-entropy frequency probes, and MITM desynchronization. | Tier 1, Tier 2, Tier 3, Tier 4 |
| **F-07** | `src.attack_classifier` | **Multi-Class Feature Extraction & Classification**: 10-dimensional real-time feature extraction and vectorized hybrid rule/ML classification (`FastRuleAndMLClassifier`). | Tier 1, Tier 2, Tier 3, Tier 4 |
| **F-08** | `src.moving_cars_simulation` | **Mobility Kinematics & Platoon Simulation**: Multi-vehicle highway corridor, dynamic pairwise session negotiation, physics stepping, and streaming batch generation. | Tier 3, Tier 4 |

---

## 4. Four-Tier Testing Methodology & Test Catalog

### 4.1 Tier 1: Functional Feature Coverage ($\ge 5$ tests per feature)

#### Feature 1: BSM Telemetry Serialization & Deserialization
1. `test_tier1_bsm_standard_roundtrip`: Verifies 32-byte binary serialization and deserialization for standard highway cruising telemetry.
2. `test_tier1_bsm_kinematics_fidelity`: Validates exact floating-point precision for speed ($0.01$ km/h), acceleration ($0.01$ m/s$^2$), and heading ($0.1^\circ$).
3. `test_tier1_bsm_coordinates_fidelity`: Verifies sub-meter spatial precision ($10^{-7}$ degrees) for latitude, longitude, and elevation.
4. `test_tier1_bsm_safety_bitmask_flags`: Validates individual and composite activation of braking and ABS flags.
5. `test_tier1_bsm_crc32_checksum_verification`: Ensures valid packets generate correct CRC-32 checksums verifiable against standard CRC-32 polynomial.

#### Feature 2: SPaT Intersection Telemetry Serialization & Deserialization
1. `test_tier1_spat_standard_roundtrip`: Verifies 32-byte serialization and deserialization across red, yellow, green, and flashing phases.
2. `test_tier1_spat_countdown_precision`: Validates 0.1-second resolution of signal countdown timers ($0.0$ to $120.0$ seconds).
3. `test_tier1_spat_station_id_fidelity`: Verifies intersection station identification across arbitrary 32-bit integer ranges.
4. `test_tier1_spat_timestamp_synchronization`: Ensures intersection epoch timestamps are accurately recorded and recovered.
5. `test_tier1_spat_crc32_integrity`: Validates CRC-32 integrity seal across valid SPaT payloads.

#### Feature 3: DENM Hazard Alert Serialization & Deserialization
1. `test_tier1_denm_hard_brake_alert`: Verifies serialization and deserialization of hard braking event alerts (cause code 1).
2. `test_tier1_denm_road_hazard_alert`: Verifies alert serialization for road hazards and black ice warnings (cause codes 2 and 3).
3. `test_tier1_denm_accident_notification`: Verifies accident emergency broadcast alert serialization (cause code 4).
4. `test_tier1_denm_vehicle_state_at_hazard`: Validates recording of vehicle speed and heading at the instant of hazard notification.
5. `test_tier1_denm_crc32_verification`: Ensures all DENM frames include valid CRC-32 checksums.

#### Feature 4: DNA-V2X 4-Mer Genomic Permutation & Encryption Lifecycle
1. `test_tier1_genomic_canonical_universe`: Verifies the 256-codon universe is mathematically complete, unique, and strictly 4-nucleotide words over $\{A, C, G, T\}$.
2. `test_tier1_genomic_bijective_roundtrip`: Validates 100% invertible byte-to-strand encoding and decoding across all 256 byte values.
3. `test_tier1_genomic_forward_ratchet_pfs`: Confirms rolling frame ratchet advances session state and alters ciphertexts for identical plaintext inputs (PFS).
4. `test_tier1_genomic_spn_avalanche_diffusion`: Verifies Genomic-SPN 2-pass diffusion achieves $>40\%$ nucleotide flip upon single-bit input change.
5. `test_tier1_genomic_memory_purge`: Validates `purge_memory()` completely wipes active permutation lookup tables and overwrites state in RAM.

#### Feature 5: Multi-Class Attack Detection & Classification
1. `test_tier1_attack_replay_detection`: Evaluates replay attack injection detection when intercepted frames are injected at later ratchet epochs.
2. `test_tier1_attack_mutation_detection`: Verifies immediate rejection of single and multi-nucleotide mutated strands via CRC and codon bijection.
3. `test_tier1_attack_sybil_detection`: Validates rejection of unauthorized vehicle frames generated with foreign or guessed cryptographic seeds.
4. `test_tier1_attack_frequency_probe_detection`: Verifies detection of repetitive, low-entropy cryptanalytic probes ($H < 2.0$ bits/byte).
5. `test_tier1_attack_mitm_desync_detection`: Validates detection and isolation of out-of-sync frames caused by state desynchronization.

---

### 4.2 Tier 2: Boundary Value Analysis & Edge Cases ($\ge 5$ tests per feature)

#### Feature 1: BSM Boundary Conditions
1. `test_tier2_bsm_boundary_speed_extremes`: Tests minimum ($0.0$ km/h), maximum boundary ($250.0$ km/h), and over-speed clamping.
2. `test_tier2_bsm_boundary_accel_extremes`: Tests maximum deceleration ($-20.0$ m/s$^2$) and acceleration ($+20.0$ m/s$^2$) boundary clipping.
3. `test_tier2_bsm_boundary_geographic_extremes`: Tests maximum latitude ($\pm 90.0^\circ$) and longitude ($\pm 180.0^\circ$) boundaries.
4. `test_tier2_bsm_boundary_heading_modulo`: Tests boundary angles ($0.0^\circ$, $359.9^\circ$, $360.0^\circ$, $720.0^\circ$) ensuring proper modulo $360^\circ$ wrapping.
5. `test_tier2_bsm_boundary_truncated_corrupted_crc`: Tests truncated payloads ($<32$ bytes), oversized buffers, and 1-bit flipped CRC bytes raising `ValueError`.

#### Feature 2: SPaT & DENM Boundary Conditions
1. `test_tier2_spat_boundary_countdown_limits`: Tests zero countdown ($0.0$ s), maximum countdown ($120.0$ s), and clamping of negative/excessive values.
2. `test_tier2_spat_boundary_phase_codes`: Tests extremal phase code boundaries ($0, 1, 4, 65535$).
3. `test_tier2_denm_boundary_cause_codes`: Tests boundary cause codes ($0, 1, 4, 65535$).
4. `test_tier2_denm_boundary_speed_heading`: Tests zero speed, max speed ($250.0$ km/h), and $360.0^\circ$ heading boundaries on hazard frames.
5. `test_tier2_spat_denm_corrupted_payload_rejection`: Tests single-byte payload tampering on SPaT and DENM frames triggering CRC failure.

#### Feature 3: Genomic 4-Mer Engine Boundaries & Corrupted Strands
1. `test_tier2_genomic_boundary_empty_strand`: Tests decoding of empty strings (`""`) raising appropriate length errors.
2. `test_tier2_genomic_boundary_non_multiple_of_4`: Tests non-multiple-of-4 strand lengths ($1, 2, 3, 5, 127$ nucleotides) raising `ValueError`.
3. `test_tier2_genomic_boundary_invalid_nucleotide_alphabet`: Tests strands containing invalid characters (`'N'`, `'X'`, `'Z'`, numbers, lowercase) triggering rejection.
4. `test_tier2_genomic_boundary_all_zero_and_all_ff_payloads`: Tests extreme byte payloads (`b"\x00"*32` and `b"\xFF"*32`) maintaining full invertibility.
5. `test_tier2_genomic_boundary_entropy_uniform_vs_monotonous`: Tests Shannon entropy calculation on all-identical strands ($H=0.0$) versus maximum uniform distribution ($H \approx 8.0$).

#### Feature 4: Attack Simulator & Classification Boundaries
1. `test_tier2_attack_boundary_single_nucleotide_mutation`: Tests minimal possible air mutation ($1$ base out of $128$ mutated) achieving $100\%$ detection.
2. `test_tier2_attack_boundary_full_strand_mutation`: Tests $100\%$ nucleotide corruption ($128$ bases mutated) failing verification.
3. `test_tier2_attack_boundary_minimal_replay_delay`: Tests minimum possible replay delay ($\Delta t = 1$ frame) successfully detected by ratchet disparity.
4. `test_tier2_attack_boundary_entropy_threshold_edge`: Tests feature extraction and classification right at entropy threshold boundaries ($1.99$ vs $2.01$).
5. `test_tier2_attack_boundary_single_sample_feature_extraction`: Tests vectorized feature extraction with $N=1$ batch size without dimension collapse.

#### Feature 5: Lightweight MAC & Memory Sanitization Boundaries
1. `test_tier2_mac_boundary_single_bit_flip`: Tests that a 1-bit alteration in the 28-byte payload invalidates the 4-byte MAC.
2. `test_tier2_mac_boundary_wrong_key`: Tests that valid payload verified against an incorrect session key returns `False`.
3. `test_tier2_mac_boundary_invalid_length`: Tests that payloads of length $\ne 28$ bytes raise `ValueError`.
4. `test_tier2_memory_boundary_double_purge_idempotence`: Tests calling `purge_memory()` multiple times in succession without exception.
5. `test_tier2_ratchet_boundary_high_frame_count`: Tests forward ratcheting across $10,000$ consecutive epochs without state desynchronization or arithmetic overflow.

---

### 4.3 Tier 3: Cross-Feature Pairwise Interactions

1. `test_tier3_pairwise_session_rekeying_under_active_replay`: Simulates active replay injection while communicating vehicles perform forward ratcheting and periodic session re-keying.
2. `test_tier3_pairwise_concurrent_multi_vehicle_sessions`: Simulates 5 concurrent vehicle pairs exchanging interleaved BSM, SPaT, and DENM frames without cross-session key interference.
3. `test_tier3_pairwise_ratcheted_stream_with_mutation_and_replay`: Interleaves nucleotide mutations, delayed packet replays, and benign packets into a single ratcheted communication channel.
4. `test_tier3_pairwise_spat_denm_over_genomic_spn`: Evaluates full SPaT and DENM lifecycle encrypted via Genomic-SPN mode with 2-pass diffusion, verifying successful decryption and CRC-32 validation.
5. `test_tier3_pairwise_authenticated_telemetry_pipeline`: Tests end-to-end telemetry pipeline: serialize BSM/SPaT/DENM $\to$ append 4-byte MAC $\to$ Genomic-SPN encryption $\to$ network transmission $\to$ decryption $\to$ constant-time MAC verification $\to$ packet deserialization.

---

### 4.4 Tier 4: Real-World Vehicular Workload Scenarios ($\ge 5$ Scenarios)

#### Scenario 1: Highway Platoon Synchronous Telemetry Stream
- **Mobility Model**: 4-vehicle highway platoon traveling at $105$ km/h with 20 m inter-vehicle headway.
- **Protocol**: Continuous 10 Hz BSM telemetry stream across 50 consecutive time epochs per vehicle ($200$ total packets).
- **Security**: Ephemeral forward ratchet advances after each transmission with dynamic permutation re-derivation.
- **Success Criteria**: 100% packet delivery, zero state desynchronization, exact kinematics tracking, 0% CRC failures.

#### Scenario 2: Emergency Brake Cascade & Multicast DENM Alerting
- **Mobility Model**: Platoon leader experiences sudden deceleration from $110$ km/h to $0$ km/h ($-8.5$ m/s$^2$ emergency braking).
- **Protocol**: Leader immediately generates prioritized ETSI DENM hazard frames (cause code 1) broadcasted to all trailing platoon vehicles.
- **Security**: High-security encrypted broadcast with lightweight MAC authentication.
- **Success Criteria**: All trailing vehicles receive, decrypt, authenticate, and process emergency alerts within real-time latency limits, triggering coordinated brake maneuvers.

#### Scenario 3: Smart Intersection SPaT Crossing & Countdown Progression
- **Mobility Model**: Vehicle approaching a signalized intersection at $45$ km/h from $150$ m distance.
- **Protocol**: Roadside Unit (RSU) broadcasts 10 Hz SPaT frames tracking phase transitions (GREEN $\to$ YELLOW $\to$ RED) and countdowns ($15.0$ s down to $0.0$ s).
- **Security**: Pairwise ephemeral permutation established between approaching vehicle and RSU.
- **Success Criteria**: Vehicle reliably tracks countdown timing, accurately identifies phase switches, and halts before the stop line upon RED phase onset.

#### Scenario 4: High-Density Highway Mixed-Traffic Stream with Active Cyber Attacks
- **Mobility Model**: 10 connected vehicles driving along a 10 km corridor at varying highway speeds ($80$ to $120$ km/h).
- **Protocol & Threat Model**: 500 streaming packets exchanged with a $35\%$ attack injection ratio comprising:
  - Benign BSM telemetry ($65\%$)
  - Out-of-epoch delayed packet replays ($10\%$)
  - In-flight nucleotide mutation / bit-flipping ($10\%$)
  - Unauthorized Sybil ghost vehicle injections ($10\%$)
  - Low-entropy cryptanalytic frequency probes ($5\%$)
- **Security**: Real-time 10-dimensional feature extraction and hybrid vectorized classification.
- **Success Criteria**: $\ge 95\%$ attack detection accuracy across all threat categories, $100\%$ pass rate for benign traffic.

#### Scenario 5: Rapid Roadside Unit (RSU) Handover & Ephemeral Session Rekeying
- **Mobility Model**: Vehicle traversing a smart highway corridor at $130$ km/h, transitioning coverage from RSU-Alpha to RSU-Beta.
- **Protocol**: Vehicle terminates session with RSU-Alpha, triggers complete memory purge of Alpha's cryptographic state, and negotiates new ephemeral seed and permutation state with RSU-Beta.
- **Security**: Complete RAM sanitization prevents post-handover state reconstruction (Forward Secrecy).
- **Success Criteria**: RSU-Alpha state fully purged; packets from RSU-Alpha cannot decrypt in RSU-Beta state; RSU-Beta session successfully exchanges authenticated SPaT/BSM frames.

---

## 5. Test Architecture & Execution Framework

### 5.1 Test Runners and Commands
The test suite is executable via standard Python test runners without external orchestration dependencies:

```bash
# Standard Python unittest runner (Recommended for zero-dependency execution)
python -m unittest tests/e2e/test_dna_v2x_e2e.py -v

# Pytest runner with timing and verbose output
python -m pytest tests/e2e/test_dna_v2x_e2e.py -v

# Full project test discovery
python -m unittest discover tests -v
```

### 5.2 Pass/Fail Semantics and Invalidation Criteria
- **Pass (Clean)**: All test assertions evaluate to true. Zero uncaught exceptions, zero segmentation faults, zero thread deadlocks.
- **Assertion Failure**: Numerical mismatch outside tolerances, unhandled boundary values, classification accuracy below $95\%$, or failure to detect simulated attacks.
- **Invalidation Condition**: Any test relying on hardcoded private implementation variables or facade bypasses will be considered invalid.

---

## 6. Coverage Thresholds & Quality Gates Summary Table

| Test Tier | Feature / Scope | Minimum Required | Implemented in Suite | Status |
|:---|:---|:---:|:---:|:---:|
| **Tier 1: Feature Coverage** | Feature 1: BSM Serialization | 5 | 5 | **COMPLETE** |
| | Feature 2: SPaT Serialization | 5 | 5 | **COMPLETE** |
| | Feature 3: DENM Serialization | 5 | 5 | **COMPLETE** |
| | Feature 4: Genomic 4-Mer Engine | 5 | 5 | **COMPLETE** |
| | Feature 5: Attack Detection & Classification | 5 | 5 | **COMPLETE** |
| **Tier 2: Boundary & Corner Cases** | Feature 1: BSM Boundaries | 5 | 5 | **COMPLETE** |
| | Feature 2: SPaT & DENM Boundaries | 5 | 5 | **COMPLETE** |
| | Feature 3: Genomic 4-Mer Boundaries | 5 | 5 | **COMPLETE** |
| | Feature 4: Attack Simulator Boundaries | 5 | 5 | **COMPLETE** |
| | Feature 5: MAC & Memory Boundaries | 5 | 5 | **COMPLETE** |
| **Tier 3: Pairwise Combinations** | Cross-Feature Interactions | 5 | 5 | **COMPLETE** |
| **Tier 4: Real-World Scenarios** | Vehicular Workload Scenarios | 5 | 5 | **COMPLETE** |
| **Total Test Methods** | **All Tiers Combined** | **$\ge 60$** | **60** | **COMPLETE** |

---

## 7. Traceability Matrix to Requirements

| Requirement / Issue | Addressed In Test Class / Method |
|:---|:---|
| F-01 (Fisher-Yates distribution) | `test_tier1_genomic_canonical_universe`, `test_tier1_genomic_bijective_roundtrip` |
| F-02 (Memory Sanitization) | `test_tier1_genomic_memory_purge`, `test_tier2_memory_boundary_double_purge_idempotence` |
| F-03 (PFS Cache Leakage) | `test_tier1_genomic_forward_ratchet_pfs`, `test_tier2_ratchet_boundary_high_frame_count` |
| F-04 (Replay vs Sybil Classification) | `test_tier1_attack_replay_detection`, `test_tier3_pairwise_session_rekeying_under_active_replay` |
| F-05 (Length Corruption vs Probe) | `test_tier2_genomic_boundary_non_multiple_of_4`, `test_tier1_attack_frequency_probe_detection` |
| F-06 (SPaT/DENM Deserialization) | `test_tier1_spat_standard_roundtrip`, `test_tier1_denm_hard_brake_alert`, `test_tier3_pairwise_spat_denm_over_genomic_spn` |
| F-07 (Kinematics & Spatial Limits) | `test_tier2_bsm_boundary_speed_extremes`, `test_tier2_bsm_boundary_accel_extremes`, `test_tier2_bsm_boundary_geographic_extremes` |
| F-08 (ML / Hybrid Decision) | `test_tier1_attack_frequency_probe_detection`, `test_tier4_scenario4_multiclass_attack_stream` |
| F-09 (IDM Physics Realism) | `test_tier4_scenario1_highway_platoon`, `test_tier4_scenario4_multiclass_attack_stream` |
