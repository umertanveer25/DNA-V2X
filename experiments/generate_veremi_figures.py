import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
import os

os.makedirs('figures', exist_ok=True)
os.makedirs('results', exist_ok=True)

df = pd.read_csv('results/Table4_VeReMi_Benchmark.csv')
df['Precision (%)'] = df['Precision (%)'].str.rstrip('%').astype(float)
df['Recall (%)'] = df['Recall (%)'].str.rstrip('%').astype(float)
df['F1-Score (%)'] = df['F1-Score (%)'].str.rstrip('%').astype(float)

df_melted = df.melt(id_vars=['VeReMi Attack Category'], value_vars=['Precision (%)', 'Recall (%)', 'F1-Score (%)'], var_name='Metric', value_name='Score')

plt.figure(figsize=(10, 6))
sns.barplot(data=df_melted, x='VeReMi Attack Category', y='Score', hue='Metric', palette='viridis')
plt.title('VeReMi Benchmark Performance by Attack Category', fontsize=14)
plt.ylabel('Score (%)')
plt.xlabel('Category')
plt.ylim(0, 105)
plt.legend(loc='lower right')
plt.grid(axis='y', linestyle='--', alpha=0.7)
plt.tight_layout()

plt.savefig('results/Fig11_VeReMi_Benchmark_Performance.png', dpi=300)
plt.savefig('figures/Fig11_VeReMi_Benchmark_Performance.png', dpi=300)
print("Generated Fig11_VeReMi_Benchmark_Performance.png")
