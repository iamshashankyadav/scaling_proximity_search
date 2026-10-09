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
                lon1, lat1, lon2,lat2 = float(toks[0]), float(toks[1]), float(toks[2]), float(toks[3])
                c1, r1 = int(round(lon1 * 99)), int(round(lat1 * 99))
                c2, r2 = int(round(lon2 * 99)), int(round(lat2 * 99))
                u = r1*100 + c1 + 1
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
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=False)
