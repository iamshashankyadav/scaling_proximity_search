import os
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

os.makedirs('data_analysis', exist_ok=True)
df = pd.read_csv('locations - locations.csv')

# Category map on 100x100 grid
cat_names = sorted(df['Category'].unique())
cat_to_int = {cat: i for i, cat in enumerate(cat_names)}

grid = np.zeros((100, 100), dtype=int)
for _, row in df.iterrows():
    r = int(round(row['Latitude'] * 99))
    c = int(round(row['Longitude'] * 99))
    grid[r, c] = cat_to_int[row['Category']]

# Plotting the 100x100 grid category map
plt.figure(figsize=(10, 8))
cmap = plt.colormaps['tab10'].resampled(len(cat_names))
im = plt.imshow(grid, origin='lower', cmap=cmap, extent=[0, 1, 0, 1])
cbar = plt.colorbar(im, ticks=range(len(cat_names)))
cbar.ax.set_yticklabels(cat_names)
plt.title('100x100 Grid Category Distribution (10,000 points)')
plt.xlabel('Longitude')
plt.ylabel('Latitude')
plt.tight_layout()
plt.savefig('data_analysis/grid_category_distribution.png', dpi=300)
plt.close()

# Let's also check category spatial correlation / Moran's I or runs test
print("Category distribution matrix shape:", grid.shape)
print("Categories:", cat_names)

# Save category coordinate stats
cat_stats = []
for cat in cat_names:
    sub = df[df['Category'] == cat]
    cat_stats.append({
        'Category': cat,
        'Count': len(sub),
        'Mean_Lat': float(sub['Latitude'].mean()),
        'Std_Lat': float(sub['Latitude'].std()),
        'Mean_Lon': float(sub['Longitude'].mean()),
        'Std_Lon': float(sub['Longitude'].std())
    })
cat_df = pd.DataFrame(cat_stats)
cat_df.to_csv('data_analysis/category_spatial_stats.csv', index=False)
print(cat_df)
