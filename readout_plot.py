import pandas as pd
import matplotlib.pyplot as plt
import json
import numpy as np
import matplotlib.pyplot as plt
import matplotlib as mpl
import numpy as np
from typing import Union
from itertools import product
import pickle

plt.rcParams['figure.figsize'] = [15, 9]
# Set general font size
plt.rcParams['font.size'] = '24'
plt.rcParams['savefig.dpi'] = 200
mpl.rcParams['pdf.fonttype'] = 42
mpl.rcParams['ps.fonttype'] = 42

# colors = ['#82cfff', '#be95ff', '#ff7eb6', '#3ddbd9', '#c1c7cd']
colors =  ['#f0f9e8','#bae4bc','#7bccc4','#43a2ca','#0868ac']
cycler = mpl.cycler(color=colors, marker=['o', 's', '*', 'd', 'v']) #, '+', 's', '2', 'v', 'P'])
# cycler = mpl.cycler(color=colors)
mpl.rcParams['axes.prop_cycle'] = cycler

def set_hatches(ax, df):
    bars = ax.patches
    hatches = ''.join(h*len(df) for h in ['/', '\\', '|', '-', '+']) #, 'x', 'o', 'O', '.', '*'])
    for bar, hatch in zip(bars, hatches):
        bar.set_hatch(hatch)

fs = 40
fig, ax = plt.subplots(figsize=(23, 10), constrained_layout=True)

# Store data for creating common x-axis
all_unique_pairs = []
file_data = {}

files = ['assets/readout_stats_google.csv', 'assets/readout_stats_ibm_real.csv', 'assets/readout_stats_ibm_future.csv']
file_labels = ['Google', 'IBM Real', 'IBM Future']  # Custom labels for legend

for i, file in enumerate(files):
    print(f"\nProcessing {file}...")
    
    # Read the CSV file
    df = pd.read_csv(file)

    # Strip whitespace from column names
    df.columns = df.columns.str.strip()

    print(f"CSV shape: {df.shape}")
    print(f"Columns: {list(df.columns)}")

    # Parse JSON metadata
    df['metadata'] = df['json_metadata'].apply(json.loads)

    # Extract parameters safely
    df['rd'] = df['metadata'].apply(lambda x: x.get('rd', None))
    df['rdel'] = df['metadata'].apply(lambda x: x.get('rdel', 0))
    df['t1'] = df['metadata'].apply(lambda x: x.get('t1', None))
    df['t2'] = df['metadata'].apply(lambda x: x.get('t2', None))
    df['p'] = df['metadata'].apply(lambda x: x.get('p', None))

    # Calculate acceptance rate
    df['acceptance_rate'] = (df['shots'] - df['discards']) / df['shots']

    # Calculate readout error rate
    df['readout_error_rate'] = 0.991 - df['rdel']

    # Create (rd, readout_error_rate) pair labels for x-axis
    df['rd_rerr_pair'] = df.apply(lambda row: f"({int(row['rd'])} ns, {row['readout_error_rate']:.3f})", axis=1)

    # Get unique pairs and their acceptance rates with statistics
    unique_pairs = df.groupby(['rd', 'rdel']).agg({
        'acceptance_rate': ['mean', 'std', 'count'],
        'readout_error_rate': 'first',  # Should be same for all in group
        't1': 'first',  # Get T1 for legend
        't2': 'first'   # Get T2 for legend
    }).reset_index()

    # Flatten column names
    unique_pairs.columns = ['rd', 'rdel', 'acceptance_mean', 'acceptance_std', 'count', 'readout_error_rate', 't1', 't2']

    # Create pair labels with readout latency and error rate
    unique_pairs['rd_rerr_pair'] = unique_pairs.apply(
        lambda row: f"{int(row['rd'])},\n{row['readout_error_rate']:.3f}", axis=1
    )

    # Fill NaN standard deviations with 0 (for single measurements)
    unique_pairs['acceptance_std'] = unique_pairs['acceptance_std'].fillna(0)

    # Sort by rd first, then by rdel to get logical ordering
    unique_pairs = unique_pairs.sort_values(['rd', 'rdel']).reset_index(drop=True)

    print(f"Number of unique (rd, rdel) pairs: {len(unique_pairs)}")
    print(f"rdel values: {sorted(df['rdel'].unique())}")
    print(f"Acceptance rate range: {unique_pairs['acceptance_mean'].min():.3f} - {unique_pairs['acceptance_mean'].max():.3f}")
    
    # Get T1/T2 values for legend (convert to microseconds)
    t1_us = unique_pairs['t1'].iloc[0] * 1e6 if unique_pairs['t1'].iloc[0] is not None else 'N/A'
    t2_us = unique_pairs['t2'].iloc[0] * 1e6 if unique_pairs['t2'].iloc[0] is not None else 'N/A'
    
    # Create legend label
    if isinstance(t1_us, float) and isinstance(t2_us, float):
        legend_label = f'T₁={t1_us:.0f}μs, T₂={t2_us:.0f}μs'
    else:
        legend_label = f'T₁={t1_us}, T₂={t2_us}'

    # Store data for plotting
    all_unique_pairs.extend(unique_pairs['rd_rerr_pair'].tolist())
    file_data[file] = {
        'unique_pairs': unique_pairs,
        'legend_label': legend_label
    }
def extract_readout_latency(label):
    # Extract the number before "ns" from labels like "(750 ns, 0.941)"
    return int(label.split(',')[0].strip('('))

# Sort all_x_labels by readout latency instead of alphabetically
all_x_labels = sorted(list(set(all_unique_pairs)), key=extract_readout_latency)

# Plot each file's data
for i, (file, data) in enumerate(file_data.items()):
    unique_pairs = data['unique_pairs']
    legend_label = data['legend_label']
    
    # Create x positions based on the common x-axis
    x_positions = [all_x_labels.index(pair) for pair in unique_pairs['rd_rerr_pair']]
    
    # Plot acceptance rate vs (rd, readout_error_rate) pairs with error bars
    ax.errorbar(x_positions, unique_pairs['acceptance_mean'], 
                yerr=unique_pairs['acceptance_std'], 
                label=legend_label,
                markersize=20, capsize=5, capthick=3,
                elinewidth=3, ecolor='red',
                markeredgecolor='black', markeredgewidth=2)

# Set x-axis labels using all unique labels
ax.set_xticks(range(len(all_x_labels)))
ax.set_xticklabels(all_x_labels, rotation=0, fontsize=fs) 

plt.setp(ax.get_yticklabels(), fontsize=fs)
ax.tick_params(axis='both', which='major', length=20, width=3, direction='out')
ax.set_xlabel('Readout latency (ns), Readout fidelity', fontsize=fs)
ax.set_ylabel('Acceptance rate', fontsize=fs)
# ax.set_title('Magic state cultivation acceptance rates', fontsize=fs, fontweight='bold')
ax.grid(True, alpha=0.5, linestyle='--')
ax.legend(fontsize=fs, loc='best')

plt.tight_layout()
plt.savefig('postselection_rates.pdf', dpi=200, bbox_inches='tight')
plt.show()

print("\nFile saved: postselection_rates.pdf")

# import pandas as pd
# import matplotlib.pyplot as plt
# import json
# import numpy as np
# import matplotlib.pyplot as plt
# import matplotlib as mpl
# import numpy as np
# from typing import Union
# from itertools import product
# import pickle

# plt.rcParams['figure.figsize'] = [15, 9]
# # Set general font size
# plt.rcParams['font.size'] = '24'
# plt.rcParams['savefig.dpi'] = 200
# mpl.rcParams['pdf.fonttype'] = 42
# mpl.rcParams['ps.fonttype'] = 42

# # colors = ['#82cfff', '#be95ff', '#ff7eb6', '#3ddbd9', '#c1c7cd']
# colors =  ['#f0f9e8','#bae4bc','#7bccc4','#43a2ca','#0868ac']
# cycler = mpl.cycler(color=colors, marker=['o', 's', '*', 'd', 'v']) #, '+', 's', '2', 'v', 'P'])
# # cycler = mpl.cycler(color=colors)
# mpl.rcParams['axes.prop_cycle'] = cycler

# def set_hatches(ax, df):
#     bars = ax.patches
#     hatches = ''.join(h*len(df) for h in ['/', '\\', '|', '-', '+']) #, 'x', 'o', 'O', '.', '*'])
#     for bar, hatch in zip(bars, hatches):
#         bar.set_hatch(hatch)

# fs = 40
# fig, ax = plt.subplots(figsize=(20, 10), constrained_layout=True)

# for file in ['assets/readout_stats_google.csv', 'assets/readout_stats_ibm_real.csv', 'assets/readout_stats_ibm_future.csv']:
#     # Read the CSV file
#     df = pd.read_csv(file)

#     # Strip whitespace from column names
#     df.columns = df.columns.str.strip()

#     print(f"CSV shape: {df.shape}")
#     print(f"Columns: {list(df.columns)}")

#     # Parse JSON metadata
#     df['metadata'] = df['json_metadata'].apply(json.loads)

#     # Extract parameters safely
#     df['rd'] = df['metadata'].apply(lambda x: x.get('rd', None))
#     df['rdel'] = df['metadata'].apply(lambda x: x.get('rdel', 0))
#     df['t1'] = df['metadata'].apply(lambda x: x.get('t1', None))
#     df['t2'] = df['metadata'].apply(lambda x: x.get('t2', None))
#     df['p'] = df['metadata'].apply(lambda x: x.get('p', None))

#     # Calculate acceptance rate
#     df['acceptance_rate'] = (df['shots'] - df['discards']) / df['shots']

#     # Calculate readout error rate
#     df['readout_error_rate'] = 0.991 - df['rdel']

#     # Create (rd, readout_error_rate) pair labels for x-axis
#     df['rd_rerr_pair'] = df.apply(lambda row: f"({int(row['rd'])} ns, {row['readout_error_rate']:.3f})", axis=1)

#     # Get unique pairs and their acceptance rates with statistics
#     unique_pairs = df.groupby(['rd', 'rdel']).agg({
#         'acceptance_rate': ['mean', 'std', 'count'],
#         'readout_error_rate': 'first'  # Should be same for all in group
#     }).reset_index()

#     # Flatten column names
#     unique_pairs.columns = ['rd', 'rdel', 'acceptance_mean', 'acceptance_std', 'count', 'readout_error_rate']

#     # Create pair labels with readout latency and error rate
#     unique_pairs['rd_rerr_pair'] = unique_pairs.apply(
#         lambda row: f"({int(row['rd'])} ns, {row['readout_error_rate']:.3f})", axis=1
#     )

#     # Fill NaN standard deviations with 0 (for single measurements)
#     unique_pairs['acceptance_std'] = unique_pairs['acceptance_std'].fillna(0)

#     # Sort by rd first, then by rdel to get logical ordering
#     unique_pairs = unique_pairs.sort_values(['rd', 'rdel']).reset_index(drop=True)

#     print("\nData summary:")
#     print(f"Number of unique (rd, rdel) pairs: {len(unique_pairs)}")
#     print(f"rdel values: {sorted(df['rdel'].unique())}")
#     print(f"Acceptance rate range: {unique_pairs['acceptance_mean'].min():.3f} - {unique_pairs['acceptance_mean'].max():.3f}")

#     # Plot acceptance rate vs (rd, readout_error_rate) pairs with error bars
#     x_positions = range(len(unique_pairs))
#     ax.errorbar(x_positions, unique_pairs['acceptance_mean'], 
#                 yerr=unique_pairs['acceptance_std'], label=f'',
#                 markersize=20, capsize=5, capthick=3,
#                 ecolor='red', elinewidth=3,
#                 markeredgecolor='black', markeredgewidth=1)

#     # Set x-axis labels
#     ax.set_xticks(x_positions)
#     ax.set_xticklabels(unique_pairs['rd_rerr_pair'], rotation=45, ha='right', fontsize=fs)

# ax.set_xlabel('(Readout latency in ns, Readout error rate)', fontsize=fs)
# ax.set_ylabel('Acceptance Rate (Kept Shots / Total Shots)', fontsize=fs)
# ax.set_title('Magic state cultivation acceptance rates', fontsize=fs, fontweight='bold')
# ax.grid(True, alpha=0.5)

# # Add value annotations on points
# # for i, (x, y, std, count) in enumerate(zip(x_positions, unique_pairs['acceptance_mean'], 
# #                                           unique_pairs['acceptance_std'], unique_pairs['count'])):
# #     ax.annotate(f'{y:.3f}±{std:.3f}', (x, y), textcoords="offset points", 
# #                 xytext=(0,15), ha='center', fontsize=fs, 
# #                 bbox=dict(boxstyle="round,pad=0.3", facecolor="white", alpha=0.7))

# plt.tight_layout()
# plt.savefig('postselection_rates.png', dpi=300, bbox_inches='tight')
# plt.show()

# # Print summary statistics
# print("\n=== Summary Statistics ===")
# print("Acceptance rates by (rd, readout_error_rate) configuration:")
# for _, row in unique_pairs.iterrows():
#     print(f"  {row['rd_rerr_pair']}: {row['acceptance_mean']:.4f} ± {row['acceptance_std']:.4f} (n={row['count']})")

# print(f"\nOverall acceptance rate: {unique_pairs['acceptance_mean'].mean():.4f}")
# print(f"Best configuration: {unique_pairs.loc[unique_pairs['acceptance_mean'].idxmax(), 'rd_rerr_pair']} ({unique_pairs['acceptance_mean'].max():.4f})")
# print(f"Worst configuration: {unique_pairs.loc[unique_pairs['acceptance_mean'].idxmin(), 'rd_rerr_pair']} ({unique_pairs['acceptance_mean'].min():.4f})")

# print("\nFile saved: postselection_rates.png")



# # import pandas as pd
# # import matplotlib.pyplot as plt
# # import json
# # import numpy as np

# # # Read the CSV file
# # df = pd.read_csv('assets/readout_stats_google.csv')

# # # Strip whitespace from column names
# # df.columns = df.columns.str.strip()

# # print(f"CSV shape: {df.shape}")
# # print(f"Columns: {list(df.columns)}")

# # # Parse JSON metadata
# # df['metadata'] = df['json_metadata'].apply(json.loads)

# # # Extract parameters safely
# # df['rd'] = df['metadata'].apply(lambda x: x.get('rd', None))
# # df['rdel'] = df['metadata'].apply(lambda x: x.get('rdel', None))
# # df['t1'] = df['metadata'].apply(lambda x: x.get('t1', None))
# # df['t2'] = df['metadata'].apply(lambda x: x.get('t2', None))
# # df['p'] = df['metadata'].apply(lambda x: x.get('p', None))

# # # Calculate acceptance rate
# # df['acceptance_rate'] = (df['shots'] - df['discards']) / df['shots']

# # # Create (rd, rdel) pair labels for x-axis
# # df['rd_rdel_pair'] = df.apply(lambda row: f"({int(row['rd'])}, {row['rdel']})", axis=1)

# # # Get unique pairs and their acceptance rates with statistics
# # unique_pairs = df.groupby(['rd', 'rdel']).agg({
# #     'acceptance_rate': ['mean', 'std', 'count']
# # }).reset_index()

# # # Flatten column names
# # unique_pairs.columns = ['rd', 'rdel', 'acceptance_mean', 'acceptance_std', 'count']

# # # Create pair labels
# # unique_pairs['rd_rdel_pair'] = unique_pairs.apply(lambda row: f"({int(row['rd'])}, {row['rdel']})", axis=1)

# # # Fill NaN standard deviations with 0 (for single measurements)
# # unique_pairs['acceptance_std'] = unique_pairs['acceptance_std'].fillna(0)

# # print("\nData summary:")
# # print(f"Number of unique (rd, rdel) pairs: {len(unique_pairs)}")
# # print(f"Acceptance rate range: {unique_pairs['acceptance_mean'].min():.3f} - {unique_pairs['acceptance_mean'].max():.3f}")

# # # Create single plot
# # fig, ax = plt.subplots(figsize=(12, 6))

# # # Plot acceptance rate vs (rd, rdel) pairs with error bars
# # x_positions = range(len(unique_pairs))
# # ax.errorbar(x_positions, unique_pairs['acceptance_mean'], 
# #             yerr=unique_pairs['acceptance_std'],
# #             fmt='o', markersize=8, capsize=5, capthick=2,
# #             color='steelblue', ecolor='red', elinewidth=2,
# #             markeredgecolor='black', markeredgewidth=1)

# # # Set x-axis labels
# # ax.set_xticks(x_positions)
# # ax.set_xticklabels(unique_pairs['rd_rdel_pair'], rotation=0, fontsize=fs)

# # ax.set_xlabel('(Readout duration in nanoseconds, Increase in readout error rate)', fontsize=fs)
# # ax.set_ylabel('Acceptance Rate (Kept Shots / Total Shots)', fontsize=fs)
# # ax.set_title('Magic state cultivation acceptance rates', fontsize=fs, fontweight='bold')
# # ax.grid(True, alpha=0.5)

# # # Add value annotations on points
# # for i, (x, y, std, count) in enumerate(zip(x_positions, unique_pairs['acceptance_mean'], 
# #                                           unique_pairs['acceptance_std'], unique_pairs['count'])):
# #     ax.annotate(f'{y:.3f}±{std:.3f}', (x, y), textcoords="offset points", 
# #                 xytext=(0,15), ha='center', fontsize=fs, 
# #                 bbox=dict(boxstyle="round,pad=0.3", facecolor="white", alpha=0.7))

# # plt.tight_layout()
# # plt.savefig('postselection_rates.png', dpi=300, bbox_inches='tight')
# # plt.show()

# # # Print summary statistics
# # print("\n=== Summary Statistics ===")
# # print("Acceptance rates by (rd, rdel) configuration:")
# # for _, row in unique_pairs.iterrows():
# #     print(f"  {row['rd_rdel_pair']}: {row['acceptance_mean']:.4f} ± {row['acceptance_std']:.4f} (n={row['count']})")

# # print(f"\nOverall acceptance rate: {unique_pairs['acceptance_mean'].mean():.4f}")
# # print(f"Best configuration: {unique_pairs.loc[unique_pairs['acceptance_mean'].idxmax(), 'rd_rdel_pair']} ({unique_pairs['acceptance_mean'].max():.4f})")
# # print(f"Worst configuration: {unique_pairs.loc[unique_pairs['acceptance_mean'].idxmin(), 'rd_rdel_pair']} ({unique_pairs['acceptance_mean'].min():.4f})")

# # print("\nFile saved: postselection_rates.png")