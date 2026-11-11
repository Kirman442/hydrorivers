"""Convert a HydroRIVERS download (shapefile, FileGDB, GeoPackage, Feather) to GeoParquet.

The result is the fastest input for hydro_map.py:
  * compact column types (orders fit in one byte),
  * zstd compression,
  * rows sorted along a Hilbert curve and a bbox column per row, so reading
    one country only touches the row groups that cover it.

    python convert_to_parquet.py HydroRIVERS_v10_eu_shp/HydroRIVERS_v10_eu.shp data/HydroRIVERS_v10_eu.parquet
"""

from __future__ import annotations

import argparse
import time
from pathlib import Path

import geopandas as gpd

DTYPES = {
    "HYRIV_ID": "int32", "NEXT_DOWN": "int32", "MAIN_RIV": "int32",
    "LENGTH_KM": "float32", "DIST_DN_KM": "float32", "DIST_UP_KM": "float32",
    "CATCH_SKM": "float32", "UPLAND_SKM": "float32", "DIS_AV_CMS": "float32",
    "ENDORHEIC": "uint8", "ORD_STRA": "uint8", "ORD_CLAS": "uint8", "ORD_FLOW": "uint8",
    "HYBAS_L12": "int64",
}


def convert(src: Path, dst: Path, row_group_size: int = 50_000):
    t0 = time.perf_counter()
    if src.suffix.lower() == ".feather":
        gdf = gpd.read_feather(src)
    elif src.suffix.lower() == ".parquet":
        gdf = gpd.read_parquet(src)
    else:
        gdf = gpd.read_file(src, engine="pyogrio", use_arrow=True)
    print(f"read {len(gdf):,} segments in {time.perf_counter() - t0:.1f} s")

    gdf = gdf.drop(columns=[c for c in ("fid", "index_right") if c in gdf.columns])
    gdf = gdf.astype({c: t for c, t in DTYPES.items() if c in gdf.columns})
    if gdf.crs is None:
        gdf = gdf.set_crs("EPSG:4326")
    gdf = gdf.iloc[gdf.geometry.hilbert_distance().argsort()].reset_index(drop=True)

    dst.parent.mkdir(parents=True, exist_ok=True)
    gdf.to_parquet(dst, compression="zstd", write_covering_bbox=True,
                   row_group_size=row_group_size, schema_version="1.1.0")
    print(f"wrote {dst} ({dst.stat().st_size / 2**20:.0f} MB) "
          f"in {time.perf_counter() - t0:.1f} s")


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    p.add_argument("src", type=Path)
    p.add_argument("dst", type=Path)
    p.add_argument("--row-group-size", type=int, default=50_000)
    a = p.parse_args()
    convert(a.src, a.dst, a.row_group_size)
