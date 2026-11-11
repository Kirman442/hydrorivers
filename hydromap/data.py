"""Loading and filtering HydroRIVERS data."""

from __future__ import annotations

import json
from pathlib import Path

import geopandas as gpd
import pandas as pd
import pyarrow.parquet as pq
import shapely
from shapely.geometry import box

# Attributes the maps use. Everything else stays on disk.
RIVER_COLUMNS = ["HYRIV_ID", "MAIN_RIV", "UPLAND_SKM", "DIS_AV_CMS",
                 "ORD_STRA", "ORD_CLAS", "ORD_FLOW"]


def dataset_bounds(path: Path) -> tuple[float, float, float, float] | None:
    """Bounding box of a GeoParquet file, read from its metadata only."""
    if path.suffix.lower() != ".parquet":
        return None
    meta = pq.read_metadata(path).metadata or {}
    geo = meta.get(b"geo")
    if not geo:
        return None
    info = json.loads(geo)
    bbox = info["columns"][info["primary_column"]].get("bbox")
    return tuple(bbox) if bbox else None


def read_rivers(path: str | Path, bbox=None, columns=RIVER_COLUMNS) -> gpd.GeoDataFrame:
    """Read river segments, only inside ``bbox`` (minx, miny, maxx, maxy) if given.

    GeoParquet written by ``convert_to_parquet.py`` carries a bbox column and is
    sorted spatially, so a country is read without touching the rest of the
    continent. Shapefile/GeoPackage/FileGDB are read with a bbox filter through
    pyogrio. Feather has no spatial filter: it is read whole and cut afterwards.
    """
    path = Path(path)
    suffix = path.suffix.lower()
    bbox_filter = False
    if suffix == ".parquet":
        available = set(pq.read_schema(path).names)
        cols = [c for c in columns if c in available] + ["geometry"]
        try:
            gdf = gpd.read_parquet(path, columns=cols, bbox=bbox)
        except (ValueError, TypeError):  # older file without a bbox column
            gdf = gpd.read_parquet(path, columns=cols)
            bbox_filter = True
    elif suffix == ".feather":
        gdf = gpd.read_feather(path)
        gdf = gdf[[c for c in columns if c in gdf.columns] + ["geometry"]]
        bbox_filter = True
    else:
        gdf = gpd.read_file(path, bbox=bbox, columns=list(columns),
                            engine="pyogrio", use_arrow=True)
    if bbox is not None and bbox_filter:
        minx, miny, maxx, maxy = bbox
        gdf = gdf.cx[minx:maxx, miny:maxy]
    if gdf.crs is None:
        gdf = gdf.set_crs("EPSG:4326")
    return gdf.reset_index(drop=True)


def clip_to_area(gdf: gpd.GeoDataFrame, area) -> gpd.GeoDataFrame:
    """Keep the parts of segments that lie inside ``area`` (a shapely geometry).

    Rivers that cross the border are cut at the border instead of dropped, which
    is what ``sjoin(predicate='within')`` did in the first version.
    """
    # Segments fully inside are kept as they are; only those that touch the
    # border are cut. That is much cheaper than gpd.clip on every segment.
    inside = gdf.sindex.query(area, predicate="contains_properly")
    border = gdf.sindex.query(area.boundary, predicate="intersects")
    cut = gdf.iloc[border].copy()
    cut["geometry"] = shapely.intersection(cut.geometry.values, area)
    clipped = pd.concat([gdf.iloc[inside], cut])
    clipped = clipped[~clipped.geometry.is_empty]
    clipped = clipped[clipped.geom_type.isin(["LineString", "MultiLineString"])]
    return clipped.explode(index_parts=False).reset_index(drop=True)


def apply_filters(gdf: pd.DataFrame, min_upland=None, max_ord_flow=None,
                  max_ord_stra=None, max_ord_clas=None, where=None):
    """Drop small streams. All thresholds are optional; see the HydroRIVERS docs."""
    mask = pd.Series(True, index=gdf.index)
    if min_upland is not None:
        mask &= gdf["UPLAND_SKM"] > min_upland
    if max_ord_flow is not None:
        mask &= gdf["ORD_FLOW"] <= max_ord_flow
    if max_ord_stra is not None:
        mask &= gdf["ORD_STRA"] <= max_ord_stra
    if max_ord_clas is not None:
        mask &= gdf["ORD_CLAS"] <= max_ord_clas
    out = gdf[mask]
    if where:
        out = out.query(where)
    return out


def limit_to_data(area, data_bounds=None):
    """Cut ``area`` to the data extent and return it with its bounds.

    Countries such as France include overseas territories; without this the bbox
    would span half the globe and the whole file would be read.
    """
    if data_bounds is not None:
        area = area.intersection(box(*data_bounds))
    return area, area.bounds
