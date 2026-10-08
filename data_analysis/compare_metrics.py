import pandas as pd
import numpy as np
import json

df = pd.read_csv('locations - locations.csv')

category_data = {}
for cat, group in df.groupby('Category'):
    category_data[cat] = {
        'ids': group['ID'].to_numpy(dtype=np.int32),
        'lats': group['Latitude'].to_numpy(dtype=np.float64),
        'longs': group['Longitude'].to_numpy(dtype=np.float64),
    }

def rank_manhattan(lat, lon, cat, rad, k=10):
    data = category_data[cat]
    dlat = data['lats'] - lat
    dlon = data['longs'] - lon
    dist_sq = dlat * dlat + dlon * dlon
    mask = dist_sq <= (rad * rad)
    if not np.any(mask):
        return []
    ids = data['ids'][mask]
    l1 = np.abs(dlat[mask]) + np.abs(dlon[mask])
    l2_sq = dist_sq[mask]
    order = np.lexsort((ids, l2_sq, l1))[:k]
    return ids[order].tolist()

def rank_euclidean(lat, lon, cat, rad, k=10):
    data = category_data[cat]
    dlat = data['lats'] - lat
    dlon = data['longs'] - lon
    dist_sq = dlat * dlat + dlon * dlon
    mask = dist_sq <= (rad * rad)
    if not np.any(mask):
        return []
    ids = data['ids'][mask]
    l2_sq = dist_sq[mask]
    order = np.lexsort((ids, l2_sq))[:k]
    return ids[order].tolist()

# Compare on 1000 random queries
np.random.seed(42)
test_cats = list(category_data.keys())
n_queries = 1000

total_jaccard = 0.0
total_exact_match = 0
order_mismatches = 0

for _ in range(n_queries):
    qlat = np.random.uniform(0.0, 1.0)
    qlon = np.random.uniform(0.0, 1.0)
    qcat = np.random.choice(test_cats)
    qrad = np.random.uniform(0.1, 0.4)
    
    m_res = rank_manhattan(qlat, qlon, qcat, qrad, k=10)
    e_res = rank_euclidean(qlat, qlon, qcat, qrad, k=10)
    
    if m_res == e_res:
        total_exact_match += 1
    
    set_m, set_e = set(m_res), set(e_res)
    intersection = len(set_m.intersection(set_e))
    union = len(set_m.union(set_e))
    jaccard = intersection / union if union > 0 else 1.0
    total_jaccard += jaccard
    
    if set_m == set_e and m_res != e_res:
        order_mismatches += 1

metric_comparison = {
    'total_queries_tested': n_queries,
    'exact_list_match_rate': total_exact_match / n_queries,
    'average_jaccard_similarity': total_jaccard / n_queries,
    'order_only_mismatches': order_mismatches / n_queries,
    'top_10_set_divergence_rate': 1.0 - (total_exact_match + order_mismatches) / n_queries
}

with open('data_analysis/metric_comparison.json', 'w') as f:
    json.dump(metric_comparison, f, indent=4)

print("Metric Comparison Results:")
print(json.dumps(metric_comparison, indent=2))
