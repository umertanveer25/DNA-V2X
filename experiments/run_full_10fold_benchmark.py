"""
Master Benchmark Execution Script for DNA-V2X.
Runs:
  - 10-Fold Cross-Validation x 30 Monte Carlo Random Splits (300 Runs)
  - Comparative Energy, Latency, Throughput, and Entropy Profiling
  - 17-Vector Cyber-Physical & Cryptanalytic Attack Evaluation
  - JSON and CSV Results Export
"""

import os
import sys
import json
import csv

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from benchmarks.kfold_monte_carlo import run_10fold_30split_benchmark


def main():
    output_dir = os.path.join(os.path.dirname(__file__), "..", "results")
    os.makedirs(output_dir, exist_ok=True)

    # Execute 300 runs (10-fold x 30 random splits)
    results = run_10fold_30split_benchmark(num_splits=30, n_splits_kfold=10, samples_per_split=1000)

    # 1. Export Master Results JSON
    json_path = os.path.join(output_dir, "dna_v2x_master_results.json")
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2)
    print(f"\n[DNA-V2X] Exported Master JSON: {json_path}")

    # 2. Export Summary Benchmark CSV (Table 1)
    csv_table1 = os.path.join(output_dir, "Table1_10Fold_30Split_Performance_Benchmark.csv")
    with open(csv_table1, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=results["summary_table"][0].keys())
        writer.writeheader()
        writer.writerows(results["summary_table"])
    print(f"[DNA-V2X] Exported Performance CSV: {csv_table1}")

    # 3. Export Attack Resistance CSV (Table 2)
    csv_table2 = os.path.join(output_dir, "Table2_Attack_Resistance_Evaluation.csv")
    with open(csv_table2, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["Attack Name", "Trials", "Breaches", "Mitigation Rate (%)", "Defense Mechanism"])
        writer.writeheader()
        for atk in results["attack_evaluations"]:
            writer.writerow({
                "Attack Name": atk["attack"],
                "Trials": atk["trials"],
                "Breaches": atk["breaches"],
                "Mitigation Rate (%)": f"{atk['detection_rate_pct']:.2f}%",
                "Defense Mechanism": atk["details"].get("defense", "Dynamic 4-Mer MTD")
            })
    print(f"[DNA-V2X] Exported Attack Evaluation CSV: {csv_table2}")

    print("\n" + "#" * 80)
    print("   ALL 300 EXPERIMENTAL EVALUATION RUNS SUCCESSFULLY COMPLETED & LOGGED!")
    print("#" * 80 + "\n")


if __name__ == "__main__":
    main()
