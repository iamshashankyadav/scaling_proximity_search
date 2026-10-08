import os
import json
import pandas as pd
import numpy as np

os.makedirs('data_analysis', exist_ok=True)

df = pd.read_csv('locations - locations.csv')

# Basic Analysis
analysis = {}
analysis['total_rows'] = len(df)
analysis['columns'] = df.columns.tolist()
analysis['missing_values'] = df.isnull().sum().to_dict()
analysis['id_min'] = int(df['ID'].min())
analysis['id_max'] = int(df['ID'].max())
analysis['id_unique_count'] = int(df['ID'].nunique())

# Grid Spacing Analysis
lats = np.sort(df['Latitude'].unique())
longs = np.sort(df['Longitude'].unique())
lat_diffs = np.diff(lats)
long_diffs = np.diff(longs)

analysis['latitude_unique_count'] = len(lats)
analysis['longitude_unique_count'] = len(longs)
analysis['latitude_min'] = float(lats.min())
analysis['latitude_max'] = float(lats.max())
analysis['longitude_min'] = float(longs.min())
analysis['longitude_max'] = float(longs.max())
analysis['lat_diff_min'] = float(lat_diffs.min())
analysis['lat_diff_max'] = float(lat_diffs.max())
analysis['long_diff_min'] = float(long_diffs.min())
analysis['long_diff_max'] = float(long_diffs.max())

# Duplicate check
duplicates = df.duplicated(subset=['Latitude', 'Longitude']).sum()
analysis['duplicate_coordinate_pairs'] = int(duplicates)

# Category distribution
cat_counts = df['Category'].value_counts().to_dict()
analysis['categories'] = {k: int(v) for k, v in cat_counts.items()}

# Check ordering
# Is ID perfectly 1..10000?
analysis['ids_sequential_1_to_10000'] = bool((df['ID'].values == np.arange(1, len(df) + 1)).all())

# Check grid indexing mapping: row = round(lat * 99), col = round(long * 99)
row_idx = np.round(df['Latitude'].values * 99).astype(int)
col_idx = np.round(df['Longitude'].values * 99).astype(int)
grid_id_expected = row_idx * 100 + col_idx + 1
analysis['row_col_matches_id'] = bool((grid_id_expected == df['ID'].values).all())

# Save summary to json and txt
with open('data_analysis/dataset_summary.json', 'w') as f:
    json.dump(analysis, f, indent=4)

with open('data_analysis/dataset_summary.txt', 'w') as f:
    f.write("=== DATASET COMPREHENSIVE ANALYSIS ===\n\n")
    for k, v in analysis.items():
        f.write(f"{k}: {v}\n")

print("Analysis complete! Summary saved to data_analysis/")
print(json.dumps(analysis, indent=2))
