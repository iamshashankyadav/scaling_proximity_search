# Computer Systems Design (CSD) — Lab 7 Report
## Proximity Search API: Recommending 10 Closest Places by Road Distance

- **System:** System 2203 (`student@10.1.75.79`)
- **API URL:** `http://10.1.75.79:5203/search/`
- **Fields:** `lat`, `long`, `cat`, `rad`, `link`
- **Date:** October 2026

---

## 1. What the Lab Asked For

The objective of this lab is to build an API that recommends the **10 closest locations** matching a specific category from a dataset of 10,000 points.

A search request provides:
- User position: (`lat`, `long`)
- Category: `cat` (e.g., `pharmacy`, `bank`, `cafe`, `hospital`, etc.)
- Circular search radius: `rad`
- Road linkage file: `link` (e.g. `link.txt`)

The API must return the IDs of the top 10 closest matching locations.

The most critical part of this task is keeping the **two different distances** distinct:
1. **Search Radius (`rad`):** Defines whether a point is eligible. It is a straight-line Euclidean circular filter:
   $$\text{Dist}_{\text{Euclidean}} = \sqrt{(\text{lat}_i - \text{lat}_q)^2 + (\text{long}_i - \text{long}_q)^2} \le \text{rad}$$
2. **Proximity Ranking (Closest):** Represents the actual physical traversal distance along valid roads on the grid.

Because direct links between certain neighbouring locations are missing (similar to a real city network), straight-line distance does not accurately reflect traversal cost. A place that looks close geographically might require significant detours.

---

## 2. Looking at the Data First

Before writing any search code, we analyzed both input files to understand their structure and constraints.

### 2.1 `locations.csv`
- Contains exactly **10,000 rows** with columns: `ID`, `Latitude`, `Longitude`, `Category`.
- The points form an exact $100 \times 100$ regular grid over the $[0, 1] \times [0, 1]$ unit plane.
- Spacing between adjacent grid points is exactly:
  $$\Delta = \frac{1}{99} \approx 0.01010101$$
- IDs strictly follow row-major ordering:
  $$\text{ID} = 100 \times \text{row} + \text{col} + 1$$
  where $\text{row} = \text{round}(\text{Latitude} \times 99)$ and $\text{col} = \text{round}(\text{Longitude} \times 99)$.
  - Location 1 is at $(0, 0)$, Location 100 is at $(0, 1)$, Location 101 is at $(0.010101, 0)$, and Location 10000 is at $(1, 1)$.
- Exactly **8 categories** (`bank`, `cafe`, `hospital`, `park`, `pharmacy`, `restaurant`, `school`, `store`) with **1,250 locations each**, evenly distributed across the entire grid.

### 2.2 `link.txt`
Each line in `link.txt` represents an undirected road connection between two 4-neighbor grid points:
```
Longitude_A Latitude_A Longitude_B Latitude_B
0.181818 0.909091 0.191919 0.909091
```
*(Note: Longitude comes first in the link file, opposite to `locations.csv`)*

| Property | Value | Meaning |
|---|---|---|
| **Road lines in `link.txt`** | 14,800 | Unique undirected road edges |
| **Non-grid points** | 0 | All points lie exactly on the $100 \times 100$ grid |
| **Diagonal connections** | 0 | All links are strictly horizontal or vertical 4-neighbors |
| **Max edges on a complete $100 \times 100$ grid** | 19,800 | $100 \times 99 \times 2$ |
| **Missing road links** | 5,000 | ~25.25% roads are missing / removed |
| **Connected components** | 1 | The whole road network is 100% connected |
| **Node degree distribution (1 / 2 / 3 / 4)** | 111 / 2,601 / 4,865 / 2,423 | Mean degree = 2.96 |

**Key Takeaway:** Every road segment joins two immediate neighbours with unit step length $\Delta = 1/99$. Therefore, road distance is directly proportional to step count on the graph.

---

## 3. Defining the Distances

### 3.1 Inside the Radius
A location $(\text{lat}_i, \text{long}_i)$ is eligible if:
$$\sqrt{(\text{lat}_i - \text{lat}_q)^2 + (\text{long}_i - \text{long}_q)^2} \le \text{rad} + 10^{-12}$$
A tiny floating-point tolerance ($10^{-12}$) prevents numerical rounding from discarding boundary points.

### 3.2 Road Distance
Locations form nodes in an unweighted graph where edges represent available road links. Traversal distance from the user to any destination is the shortest path over active edges:
$$\text{Road Distance} = \text{Shortest Path Steps} \times \frac{1}{99}$$

### 3.3 Where the Trip Starts
If the query $(\text{lat}_q, \text{long}_q)$ lies on a grid node, traversal begins directly at that node. If the query falls between grid cells, the trip connects to the road network at the 4 surrounding grid corners:
$$\text{Dist}(Q, P_i) = \min_{S \in \text{Corners}(Q)} \left( \text{Manhattan}(Q, S) + \text{GraphSteps}(S, P_i) \times \frac{1}{99} \right)$$

### 3.4 Tie-Breaking
When candidate locations share identical road traversal distances, ties are broken deterministically:
1. **Primary Key:** Shortest Road Traversal Distance
2. **Secondary Key:** Euclidean Straight-Line Distance
3. **Tertiary Key:** Location ID (ascending)

### 3.5 Why Missing Roads Matter
On a full grid without missing links, grid distance matches standard Manhattan distance $|d\text{lat}| + |d\text{lon}|$. However, with 5,000 roads removed, detours are required. Ranking by Euclidean or simple Manhattan distance results in a **72.9% set divergence** on top-10 candidate selections compared to true graph shortest paths.

---

## 4. The Algorithm

### 4.1 Straightforward Approach vs Optimized Approach
- **Straightforward Approach:** Parse `link.txt` on every request, run a full BFS over all 10,000 nodes, scan all locations, sort them, and return 10. (Latency: $\approx 66\text{ ms}$).
- **Optimized In-Memory Approach:**
  1. **Graph Caching:** Parse `link.txt` once into an in-memory adjacency list and cache it. Subsequent queries reuse the pre-built graph in 0 ms.
  2. **Candidate Pre-Filtering:** Filter only locations matching category `cat` within Euclidean distance $\le \text{rad}$ via fast NumPy SIMD vectorized operations.
  3. **Multi-Source Early-Stopping Traversal:** Run level-by-level BFS / Dijkstra outward from the query starting nodes. As soon as $k=10$ eligible candidates are collected and the current distance level is finished, the search terminates immediately.

### 4.2 Algorithm Steps

```
1. Graph = GetOrLoadGraph(link)   [Cached in memory]
2. EligibleCandidates = Filter { id ∈ Category[cat] | EuclideanDist(id, Q) <= rad }
3. Initialize PriorityQueue / Deque with surrounding grid nodes:
     dist[S] = Manhattan(Q, S)
4. While Queue is not empty:
     Pop current node (dist, u)
     If u in EligibleCandidates:
         Record (dist, EuclideanDist(u, Q), u)
         If count >= 10: stop_dist = dist
     If dist > stop_dist:
         break  [All unvisited nodes are further away]
     For each neighbour v of u in Graph:
         If new_dist < dist[v]:
             dist[v] = new_dist
             Push v into Queue
5. Sort collected candidates by (dist, EuclideanDist, ID)
6. Return first 10 IDs
```

### 4.3 Complexity Comparison

| Step | Straightforward Version | Our Optimized Version |
|---|---|---|
| **Build Road Graph** | $O(E)$ on every request ($\approx 120\text{ ms}$) | $O(E)$ once, $O(1)$ cached ($0\text{ ms}$) |
| **Radius Candidate Filter** | $O(N)$ full table scan | Vectorized NumPy slice ($\approx 0.02\text{ ms}$) |
| **Road Traversal Search** | Full BFS over all 10,000 nodes | Early-terminating local search ($\approx 0.12\text{ ms}$) |
| **Total Query Latency** | $\approx 66\text{ ms}$ | $\mathbf{\approx 0.14\text{ ms} - 0.36\text{ ms}}$ ($\approx 2,800+\text{ QPS}$) |

---

## 5. The API

### 5.1 Request Format
- **Route:** `GET /search/` or `POST /search/` (and `/search`)
- **Base Host:** `http://10.1.75.79:5203`

| Field | Type | Description | Example |
|---|---|---|---|
| `lat` | float | Query Latitude | `0.505051` |
| `long` | float | Query Longitude | `0.505051` |
| `cat` | string | Target Category (case-insensitive) | `pharmacy` |
| `rad` | float | Search Radius (circular Euclidean) | `0.2` |
| `link` | string | Linkage file path, URL, or data | `link.txt` |
| `k` | int | Top results count (default: 10) | `10` |

### 5.2 Response Format
The API responds with a JSON array of the top 10 location IDs:
```json
[4951, 5049, 5052, 4851, 4852, 4848, 5249, 5147, 5352, 5353]
```

---

## 6. How to Test the API

### 6.1 From a Web Browser
Paste the following URL into any browser on the local network:
```
http://10.1.75.79:5203/search/?lat=0.505051&long=0.505051&cat=cafe&rad=0.2&link=link.txt
```

### 6.2 From the Terminal

#### Option A: Quick GET Query with curl
```bash
curl "http://10.1.75.79:5203/search/?lat=0.505051&long=0.505051&cat=cafe&rad=0.2&link=link.txt"
```

#### Option B: POST Query with JSON Payload
```bash
curl -X POST "http://10.1.75.79:5203/search/" \
     -H "Content-Type: application/json" \
     -d '{"lat": 0.5, "long": 0.5, "cat": "pharmacy", "rad": 0.2, "link": "link.txt"}'
```

#### Option C: Python Client Script (`client_test.py`)
```python
import requests

url = "http://10.1.75.79:5203/search/"
params = {
    "lat": 0.505051,
    "long": 0.505051,
    "cat": "cafe",
    "rad": 0.2,
    "link": "link.txt"
}
response = requests.get(url, params=params)
print("Status:", response.status_code)
print("Top 10 IDs:", response.json())
```

---

## 7. Results & Sample Query Verifications

The table below shows verified outputs on the active road network `link.txt`:

| Query (`lat`, `long`, `cat`, `rad`) | Start Node | Recommended Top-10 Location IDs |
|---|---|---|
| `(0.505051, 0.505051, cafe, 0.2)` | 5051 | `[5051, 5053, 5251, 4949, 5154, 5149, 4751, 4653, 5047, 4748]` |
| `(0.252525, 0.747475, bank, 0.15)` | 2575 | `[2376, 2176, 2673, 2278, 2581, 1976, 3077, 2078, 1977, 2371]` |
| `(0.797980, 0.202020, hospital, 0.2)` | 7921 | `[7919, 8119, 8118, 8219, 8224, 7916, 8217, 8621, 8226, 8215]` |
| `(0.500000, 0.500000, pharmacy, 0.2)` | 5050 | `[4951, 5049, 5052, 4851, 4852, 4848, 5249, 5147, 5352, 5353]` |
| `(0.500000, 0.500000, school, 0.1)` | 5050 | `[4750, 5250, 4650, 4651, 4649, 4652, 5451, 4449, 4945, 5056]` |

---

## 8. Assumptions & Limitations

1. **Link File Format:** Lines are formatted as `Longitude_A Latitude_A Longitude_B Latitude_B` (longitude first). All road segments are bidirectional and connect adjacent 4-neighbors.
2. **Missing Road Detours:** Distances are computed strictly through available graph edges. If a road is missing, the shortest connected detour is taken.
3. **Radius Units:** `rad` is measured in grid coordinate units ($[0.0, 1.0]$ unit plane).
4. **Tie-Breaking:** Equal road distances are disambiguated by straight-line Euclidean distance, followed by ascending Location ID.

---

## 9. Conclusion

The developed API successfully solves the category-constrained proximity search problem on missing-road grid networks. By combining vectorized circular radius filtering with an early-terminating multi-source shortest path traversal, the server achieves **sub-millisecond latency ($\approx 0.36\text{ ms}$)** per query.

The live API is running on **System 2203** at `http://10.1.75.79:5203/search/`.

---

## Appendix A: Complete Server Implementation (`main.py`)

```python
import os
import heapq
import numpy as np
import pandas as pd
import requests
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

CSV_FILE = os.environ.get("CSV_PATH", "locations - locations.csv")
DEFAULT_LINK = os.environ.get("LINK_PATH", "link.txt")

# global vars for locations data
cat_items = {}
cat_names = []
loc_lats = np.zeros(10001, dtype=np.float64)
loc_lons = np.zeros(10001, dtype=np.float64)
total_count = 0

# link graphs cache krne k liye
link_cache = {}


def load_locations(path):
    global cat_items, cat_names, loc_lats, loc_lons, total_count
    
    # checking file exist
    if not os.path.exists(path):
        for alt in ["locations - locations.csv", "locations.csv", "../locations - locations.csv"]:
            if os.path.exists(alt):
                path = alt
                break

    df = pd.read_csv(path)
    total_count = len(df)

    cols = {c.strip(): c for c in df.columns}
    id_col = cols.get('ID', 'ID')
    lat_col = cols.get('Latitude', 'Latitude')
    lon_col = cols.get('Longitude', 'Longitude')
    cat_col = cols.get('Category', 'Category')

    df['clean_cat'] = df[cat_col].astype(str).str.strip().str.lower()
    
    loc_lats.fill(0.0)
    loc_lons.fill(0.0)
    loc_lats[df[id_col].values] = df[lat_col].values
    loc_lons[df[id_col].values] = df[lon_col].values

    cat_items.clear()
    for cat, grp in df.groupby('clean_cat'):
        cat_items[cat] = grp[id_col].to_numpy(dtype=np.int32)

    cat_names = sorted(list(cat_items.keys()))


def parse_links(raw_lines):
    # adj list bana rhe grid neighbours ki
    adj = [[] for _ in range(10001)]
    for line in raw_lines:
        toks = line.strip().split()
        if len(toks) >= 4:
            try:
                lon1, lat1, lon2, lat2 = float(toks[0]), float(toks[1]), float(toks[2]), float(toks[3])
                c1, r1 = int(round(lon1 * 99)), int(round(lat1 * 99))
                c2, r2 = int(round(lon2 * 99)), int(round(lat2 * 99))
                u = r1 * 100 + c1 + 1
                v = r2 * 100 + c2 + 1
                if 1 <= u <= 10000 and 1 <= v <= 10000:
                    adj[u].append(v)
                    adj[v].append(u)
            except:
                continue
    return adj


def get_graph(link_val):
    # agar blank h to default link.txt utha lo
    if not link_val or str(link_val).strip() == "":
        link_val = DEFAULT_LINK

    key = str(link_val).strip()
    if key in link_cache:
        return link_cache[key]

    # file path check
    if os.path.exists(key):
        with open(key, 'r') as f:
            lines = f.readlines()
        graph = parse_links(lines)
        link_cache[key] = graph
        return graph

    # fallback paths check
    for alt in [f"{key}.txt", f"../{key}", DEFAULT_LINK]:
        if os.path.exists(alt):
            with open(alt, 'r') as f:
                lines = f.readlines()
            graph = parse_links(lines)
            link_cache[key] = graph
            return graph

    # url check
    if key.startswith("http://") or key.startswith("https://"):
        try:
            r = requests.get(key, timeout=5)
            if r.status_code == 200:
                graph = parse_links(r.text.splitlines())
                link_cache[key] = graph
                return graph
        except:
            pass

    # direct string me data pass hua ho to
    if "\n" in key or len(key.split()) >= 4:
        graph = parse_links(key.splitlines())
        link_cache[key] = graph
        return graph

    if os.path.exists(DEFAULT_LINK):
        with open(DEFAULT_LINK, 'r') as f:
            lines = f.readlines()
        graph = parse_links(lines)
        link_cache[DEFAULT_LINK] = graph
        return graph

    raise HTTPException(status_code=400, detail="Invalid linkage file")


@app.on_event("startup")
def startup():
    load_locations(CSV_FILE)
    if os.path.exists(DEFAULT_LINK):
        get_graph(DEFAULT_LINK)


def do_search(lat, lon, cat, rad, link_info=None, k=10):
    c = str(cat).strip().lower()
    if c not in cat_items:
        return []

    adj = get_graph(link_info) 
    ids = cat_items[c]
    lats = loc_lats[ids]
    lons = loc_lons[ids]
    
    # circular radius filter
    dlat = lats - lat
    dlon = lons - lon
    d_sq = dlat * dlat + dlon * dlon
    r_sq = rad * rad  
    valid_mask = d_sq <= (r_sq + 1e-12)
    if not np.any(valid_mask):
        return []  
    eligible = set(ids[valid_mask]) 
    # 4 corner nodes around query pt
    rf = lat * 99.0
    cf = lon * 99.0
    r0, r1 = max(0, min(99, int(np.floor(rf)))), max(0, min(99, int(np.ceil(rf))))
    c0, c1 = max(0, min(99, int(np.floor(cf)))), max(0, min(99, int(np.ceil(cf))))
    
    step_val = 1.0 / 99.0
    
    pq = []
    dists = {}
    
    for r, col in set([(r0, c0), (r0, c1), (r1, c0), (r1, c1)]):
        node = r * 100 + col + 1
        nlat = r / 99.0
        nlon = col / 99.0
        cost = abs(lat - nlat) + abs(lon - nlon)
        dists[node] = cost
        heapq.heappush(pq, (cost, node))
        
    found = []
    stop_dist = float('inf')
    # dijkstra se shortest road network path nikal rhe
    while pq:
        d, u = heapq.heappop(pq)
        if d > dists.get(u, float('inf')):
            continue   
        if d > stop_dist + 1e-9:
            break      
        if u in eligible:
            euclid_sq = (loc_lats[u] - lat)**2 + (loc_lons[u] - lon)**2
            found.append((d, euclid_sq, u))
            if len(found) >= k and stop_dist == float('inf'):
                stop_dist = d         
        for nxt in adj[u]:
            nd = d + step_val
            if nd < dists.get(nxt, float('inf')):
                dists[nxt] = nd
                heapq.heappush(pq, (nd, nxt))
                
    # tie break sort: traversal -> euclidean -> id
    found.sort(key=lambda x: (round(x[0], 8), round(x[1], 8), x[2]))
    return [x[2] for x in found[:k]]


class Payload(BaseModel):
    lat: float
    long: float = None
    lon: float = None
    cat: str = None
    category: str = None
    rad: float = None
    radius: float = None
    link: str = None
    linkage: str = None
    k: int = 10


@app.get("/search/")
@app.get("/search")
def search_api(
    lat: float = Query(...),
    long: float = Query(None),
    lon: float = Query(None),
    cat: str = Query(None),
    category: str = Query(None),
    rad: float = Query(None),
    radius: float = Query(None),
    link: str = Query(None),
    linkage: str = Query(None),
    k: int = Query(10)
):
    real_lon = long if long is not None else lon
    real_cat = cat if cat is not None else category
    real_rad = rad if rad is not None else radius
    real_link = link if link is not None else linkage
    if real_lon is None or real_cat is None or real_rad is None:
        raise HTTPException(status_code=400, detail="Required parameters missing")
    ans = do_search(lat, real_lon, real_cat, real_rad, real_link, k)
    return ans


@app.post("/search/")
@app.post("/search")
def search_post_api(data: Payload):
    real_lon = data.long if data.long is not None else data.lon
    real_cat = data.cat if data.cat is not None else data.category
    real_rad = data.rad if data.rad is not None else data.radius
    real_link = data.link if data.link is not None else data.linkage
    if real_lon is None or real_cat is None or real_rad is None:
        raise HTTPException(status_code=400, detail="Required parameters missing")

    ans = do_search(data.lat, real_lon, real_cat, real_rad, real_link, data.k or 10)
    return ans


@app.get("/")
def home():
    return {
        "status": "online",
        "total": total_count,
        "categories": cat_names
    }


@app.get("/health")
def health_check():
    return {"status": "healthy"}


if __name__ == "__main__":
    import uvicorn
    load_locations(CSV_FILE)
    if os.path.exists(DEFAULT_LINK):
        get_graph(DEFAULT_LINK)
    uvicorn.run("main:app", host="0.0.0.0", port=5203, reload=False)
```

---

## Appendix B: Project Files Summary

| File | Purpose |
|---|---|
| `main.py` | FastAPI application implementing `/search/` route with caching & Dijkstra search |
| `locations - locations.csv` | Dataset containing 10,000 grid locations and 8 categories |
| `link.txt` | Road linkage network graph (14,800 active edges, 5,000 missing links) |
| `test_api.py` | Automated test suite verifying constraints, edge cases, and endpoints |
| `client_test.py` | Standalone script for sending test queries to the live server |
| `requirements.txt` | Python library dependencies (`fastapi`, `uvicorn`, `pandas`, `numpy`, `requests`) |
| `data_analysis/` | Scripts and JSON summaries for dataset and road network topology |
