"""
DNA-V2X: Ephemeral 4-Mer Genomic Permutation Cipher & Moving Target Defense
for Real-Time Vehicular Telemetry Streams.
"""

from .dna_4mer_engine import DNA4MerEngine, DynamicPermutationState
from .v2x_telemetry_schema import V2XTelemetryPacket, serialize_bsm, serialize_cam, serialize_spat, serialize_denm
from .attack_simulator import AttackSimulator, AttackResult
from .energy_profiler import EnergyProfiler, BenchmarkMetrics

__all__ = [
    "DNA4MerEngine",
    "DynamicPermutationState",
    "V2XTelemetryPacket",
    "serialize_bsm",
    "serialize_cam",
    "serialize_spat",
    "serialize_denm",
    "AttackSimulator",
    "AttackResult",
    "EnergyProfiler",
    "BenchmarkMetrics"
]
