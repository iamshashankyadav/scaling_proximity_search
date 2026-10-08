import time
import numpy as np
import pandas as pd
from scipy.spatial import cKDTree

df = pd.read_csv('locations - locations.csv')

# Method 1: Pre-grouped NumPy arrays per category
category_data = {}
category_trees = {}

for cat, group in df.groupby('Category'):
    ids = group['ID'].to_numpy(dtype=np.int32)
    lats = group['Latitude'].to_numpy(dtype=np.float64)
    longs = group['Longitude'].to_numpy(dtype=np.float64)
    coords = np.column_stack((lats, longs))
    
    category_data[cat] = {
        'ids': ids,
        'lats': lats,
        'longs': longs,
        'coords': coords
    }
    category_trees[cat] = {
        'tree': cKDTree(coords),
        'ids': ids,
        'coords': coords
    }

def search_numpy_vectorized(lat, lon, cat, rad, k=10):
    if cat not in category_data:
        return []
    data = category_data[cat]
    dlat = data['lats'] - lat
    dlon = data['longs'] - lon
    r2 = rad * rad
    dist_sq = dlat * dlat + dlon * dlon
    
    # Filter points within circular radius
    mask = dist_sq <= r2
    if not np.any(mask):
        return []
    
    survivor_ids = data['ids'][mask]
    survivor_l1 = np.abs(dlat[mask]) + np.abs(dlon[mask])
    survivor_l2_sq = dist_sq[mask]
    
    n_survivors = len(survivor_ids)
    if n_survivors <= k:
        # Sort all survivors
        order = np.lexsort((survivor_ids, survivor_l2_sq, survivor_l1))
        return survivor_ids[order].tolist()
    
    # If more than k, we can sort or partition
    order = np.lexsort((survivor_ids, survivor_l2_sq, survivor_l1))[:k]
    return survivor_ids[order].tolist()

def search_kdtree(lat, lon, cat, rad, k=10):
    if cat not in category_trees:
        return []
    tree_obj = category_trees[cat]
    tree = tree_obj['tree']
    ids = tree_obj['ids']
    coords = tree_obj['coords']
    
    # Query all points within Euclidean radius
    indices = tree.query_ball_point([lat, lon], r=rad)
    if not indices:
        return []
    
    idx_arr = np.array(indices, dtype=np.int32)
    sub_coords = coords[idx_arr]
    sub_ids = ids[idx_arr]
    
    dlat = np.abs(sub_coords[:, 0] - lat)
    dlon = np.abs(sub_coords[:, 1] - lon)
    l1_dist = dlat + dlon
    l2_sq = dlat * dlat + dlon * dlon
    
    order = np.lexsort((sub_ids, l2_sq, l1_dist))[:k]
    return sub_ids[order].tolist()

# Verification: Test equivalence on 500 random queries
np.random.seed(42)
test_cats = list(category_data.keys())
n_queries = 500
test_queries = []
for _ in range(n_queries):
    qlat = np.random.uniform(0.0, 1.0)
    qlon = np.random.uniform(0.0, 1.0)
    qcat = np.random.choice(test_cats)
    qrad = np.random.uniform(0.1, 0.5)
    test_queries.append((qlat, qlon, qcat, qrad))

# Verify results match 100%
all_matched = True
for qlat, qlon, qcat, qrad in test_queries:
    res_np = search_numpy_vectorized(qlat, qlon, qcat, qrad, k=10)
    res_kd = search_kdtree(qlat, qlon, qcat, qrad, k=10)
    if res_np != res_kd:
        all_matched = False
        print(f"Mismatch for query ({qlat}, {qlon}, {qcat}, {qrad}): NP={res_np} vs KD={res_kd}")
        break

print(f"Algorithm Equivalence Test across {n_queries} queries: {'PASSED (100% Identical)' if all_matched else 'FAILED'}")

# Timing Benchmark
# 1. NumPy Vectorized
start = time.perf_counter()
for qlat, qlon, qcat, qrad in test_queries:
    search_numpy_vectorized(qlat, qlon, qcat, qrad, k=10)
np_time = (time.perf_counter() - start) / n_queries * 1000

# 2. KD-Tree
start = time.perf_counter()
for qlat, qlon, qcat, qrad in test_queries:
    search_kdtree(qlat, qlon, qcat, qrad, k=10)
kd_time = (time.perf_counter() - start) / n_queries * 1000

print(f"NumPy Vectorized Average Latency: {np_time:.4f} ms per query ({1000/np_time:.0f} QPS)")
print(f"cKDTree Average Latency:           {kd_time:.4f} ms per query ({1000/kd_time:.0f} QPS)")

# Save benchmark results
bench_df = pd.DataFrame([
    {'Algorithm': 'NumPy Vectorized Array Filter', 'Latency_ms': np_time, 'Throughput_QPS': 1000/np_time},
    {'Algorithm': 'SciPy cKDTree Ball Query + L1 Rerank', 'Latency_ms': kd_time, 'Throughput_QPS': 1000/kd_time}
])
bench_df.to_csv('data_analysis/benchmark_results.csv', index=False)
