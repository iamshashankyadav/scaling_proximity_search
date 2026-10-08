import os
from typing import List, Optional, Union
import numpy as np
import pandas as pd
from fastapi import FastAPI, Query, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

app = FastAPI(
    title="Scaling Proximity Search API",
    description="High-performance Grid Traversal & Circular Radius Proximity Search API for 10,000+ Locations",
    version="1.0.0"
)

# Enable CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global in-memory data structures
DATA_PATH = os.environ.get("CSV_PATH", "locations - locations.csv")
category_index = {}
categories_list = []
total_records = 0

def load_dataset(csv_path: str):
    global category_index, categories_list, total_records
    
    if not os.path.exists(csv_path):
        # Fallback search in current dir or parent
        alt_paths = ["locations - locations.csv", "locations.csv", "../locations - locations.csv"]
        for p in alt_paths:
            if os.path.exists(p):
                csv_path = p
                break

    if not os.path.exists(csv_path):
        raise FileNotFoundError(f"Could not find dataset at {csv_path}")

    df = pd.read_csv(csv_path)
    total_records = len(df)
    
    # Standardize column names if needed
    cols = {c.strip(): c for c in df.columns}
    id_col = cols.get('ID', 'ID')
    lat_col = cols.get('Latitude', 'Latitude')
    lon_col = cols.get('Longitude', 'Longitude')
    cat_col = cols.get('Category', 'Category')

    # Normalize categories to lower-case trimmed string for robust matching
    df['normalized_cat'] = df[cat_col].astype(str).str.strip().str.lower()
    
    category_index.clear()
    for cat, group in df.groupby('normalized_cat'):
        category_index[cat] = {
            'ids': group[id_col].to_numpy(dtype=np.int32),
            'lats': group[lat_col].to_numpy(dtype=np.float64),
            'longs': group[lon_col].to_numpy(dtype=np.float64),
        }
    
    categories_list = sorted(list(category_index.keys()))
    print(f"Loaded {total_records} locations across {len(category_index)} categories: {categories_list}")

@app.on_event("startup")
def startup_event():
    load_dataset(DATA_PATH)

def execute_proximity_search(
    lat: float,
    long: float,
    cat: str,
    rad: float,
    k: int = 10
) -> List[int]:
    """
    Executes circular radius filtering and Manhattan grid traversal ranking.
    - Radius: Circular Euclidean distance sqrt((lat - qlat)^2 + (long - qlon)^2) <= rad
    - Ranking: Grid traversal distance |lat - qlat| + |long - qlon| (Manhattan L1)
    - Tie-breaking: Euclidean distance L2, then ID ascending
    """
    norm_cat = str(cat).strip().lower()
    if norm_cat not in category_index:
        return []

    data = category_index[norm_cat]
    dlat = data['lats'] - lat
    dlon = data['longs'] - long
    
    # Circular Euclidean radius filter
    r2 = rad * rad
    dist_sq = dlat * dlat + dlon * dlon
    mask = dist_sq <= r2
    
    if not np.any(mask):
        return []
    
    survivor_ids = data['ids'][mask]
    survivor_l1 = np.abs(dlat[mask]) + np.abs(dlon[mask])
    survivor_l2_sq = dist_sq[mask]
    
    # Multi-key deterministic sort: L1 distance -> L2 distance -> ID
    order = np.lexsort((survivor_ids, survivor_l2_sq, survivor_l1))[:k]
    return survivor_ids[order].tolist()

class SearchPayload(BaseModel):
    lat: float = Field(..., description="Latitude of query point")
    long: Optional[float] = Field(None, description="Longitude of query point")
    lon: Optional[float] = Field(None, description="Alternative Longitude field name")
    cat: Optional[str] = Field(None, description="Category to search for")
    category: Optional[str] = Field(None, description="Alternative Category field name")
    rad: Optional[float] = Field(None, description="Search radius (circular Euclidean)")
    radius: Optional[float] = Field(None, description="Alternative Radius field name")
    k: Optional[int] = Field(10, description="Number of results to return (default 10)")

@app.get("/search/", response_model=List[int])
@app.get("/search", response_model=List[int])
def search_get(
    lat: float = Query(..., description="Current Latitude"),
    long: Optional[float] = Query(None, description="Current Longitude"),
    lon: Optional[float] = Query(None, description="Current Longitude (alias)"),
    cat: Optional[str] = Query(None, description="Category"),
    category: Optional[str] = Query(None, description="Category (alias)"),
    rad: Optional[float] = Query(None, description="Search Radius (circular distance)"),
    radius: Optional[float] = Query(None, description="Search Radius (alias)"),
    k: int = Query(10, description="Top K recommendations (default 10)")
):
    actual_long = long if long is not None else lon
    actual_cat = cat if cat is not None else category
    actual_rad = rad if rad is not None else radius

    if actual_long is None:
        raise HTTPException(status_code=400, detail="Missing required field: 'long' (or 'lon')")
    if actual_cat is None:
        raise HTTPException(status_code=400, detail="Missing required field: 'cat' (or 'category')")
    if actual_rad is None:
        raise HTTPException(status_code=400, detail="Missing required field: 'rad' (or 'radius')")

    results = execute_proximity_search(
        lat=lat,
        long=actual_long,
        cat=actual_cat,
        rad=actual_rad,
        k=k
    )
    return results

@app.post("/search/", response_model=List[int])
@app.post("/search", response_model=List[int])
def search_post(payload: SearchPayload):
    actual_long = payload.long if payload.long is not None else payload.lon
    actual_cat = payload.cat if payload.cat is not None else payload.category
    actual_rad = payload.rad if payload.rad is not None else payload.radius

    if actual_long is None:
        raise HTTPException(status_code=400, detail="Missing required field: 'long' (or 'lon')")
    if actual_cat is None:
        raise HTTPException(status_code=400, detail="Missing required field: 'cat' (or 'category')")
    if actual_rad is None:
        raise HTTPException(status_code=400, detail="Missing required field: 'rad' (or 'radius')")

    results = execute_proximity_search(
        lat=payload.lat,
        long=actual_long,
        cat=actual_cat,
        rad=actual_rad,
        k=payload.k or 10
    )
    return results

@app.get("/")
def root():
    return {
        "status": "online",
        "api_name": "Scaling Proximity Search API",
        "dataset_size": total_records,
        "categories": categories_list,
        "endpoint": "/search/?lat={lat}&long={long}&cat={cat}&rad={rad}",
        "docs": "/docs"
    }

@app.get("/health")
def health():
    return {"status": "healthy", "total_records": total_records}

if __name__ == "__main__":
    import uvicorn
    # Load dataset directly if running standalone
    load_dataset(DATA_PATH)
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=False)
