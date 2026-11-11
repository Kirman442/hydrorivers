"""Country boundaries, capitals and flags from Natural Earth / flagcdn.

The first version geocoded every country and capital through OSM and a
third-party JSON list of capitals. Natural Earth gives boundaries, ISO codes,
continents and capitals in two files that are downloaded once and cached.
"""

from __future__ import annotations

import io
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path

import geopandas as gpd

NE_BASE = "https://raw.githubusercontent.com/nvkelso/natural-earth-vector/master/geojson/"
NE_COUNTRIES = "ne_10m_admin_0_countries.geojson"
NE_PLACES = "ne_10m_populated_places_simple.geojson"
NAME_COLUMNS = ["ADMIN", "NAME", "NAME_LONG", "NAME_EN", "NAME_DE", "NAME_RU",
                "ISO_A2_EH", "ADM0_A3"]


@dataclass
class Country:
    name: str
    continent: str
    iso_a2: str | None
    geometry: object
    capital: str | None
    capital_lonlat: tuple[float, float] | None


def _cached(cache_dir: Path, filename: str) -> Path:
    cache_dir.mkdir(parents=True, exist_ok=True)
    path = cache_dir / filename
    if not path.exists():
        print(f"Downloading {filename} (only once) ...")
        urllib.request.urlretrieve(NE_BASE + filename, path)
    return path


def find_country(name: str, cache_dir: Path) -> Country:
    """Look a country up by name (English, German or Russian) or ISO code."""
    countries = gpd.read_file(_cached(cache_dir, NE_COUNTRIES),
                              columns=NAME_COLUMNS + ["CONTINENT"])
    key = name.strip().casefold()
    match = countries[NAME_COLUMNS].apply(
        lambda col: col.astype(str).str.casefold() == key).any(axis=1)
    hit = countries[match]
    if hit.empty:
        close = countries.loc[countries["NAME"].str.casefold()
                              .str.contains(key[:4], regex=False), "NAME"]
        hint = f" Did you mean: {', '.join(close.head(5))}?" if len(close) else ""
        raise SystemExit(f"Country '{name}' not found in Natural Earth.{hint}")
    row = hit.iloc[0]

    places = gpd.read_file(_cached(cache_dir, NE_PLACES),
                           columns=["name", "featurecla", "adm0_a3", "longitude", "latitude"])
    caps = places[(places["adm0_a3"] == row["ADM0_A3"])
                  & places["featurecla"].str.startswith("Admin-0 capital")]
    caps = caps.sort_values("featurecla")  # 'Admin-0 capital' before '... alt'
    capital, lonlat = None, None
    if len(caps):
        cap = caps.iloc[0]
        capital, lonlat = cap["name"], (float(cap["longitude"]), float(cap["latitude"]))

    iso = row["ISO_A2_EH"] if row["ISO_A2_EH"] not in ("-99", None) else None
    return Country(name=row["NAME"], continent=row["CONTINENT"], iso_a2=iso,
                   geometry=row.geometry, capital=capital, capital_lonlat=lonlat)


def download_flag(iso_a2: str, cache_dir: Path, width: int = 160):
    """Flag image from flagcdn.com as a PIL image, or None when offline."""
    from PIL import Image

    cache_dir.mkdir(parents=True, exist_ok=True)
    path = cache_dir / f"flag_{iso_a2.lower()}_w{width}.png"
    if not path.exists():
        url = f"https://flagcdn.com/w{width}/{iso_a2.lower()}.png"
        try:
            with urllib.request.urlopen(url, timeout=20) as resp:
                path.write_bytes(resp.read())
        except (urllib.error.URLError, TimeoutError) as err:
            print(f"Flag for {iso_a2} not available ({err}); continuing without it.")
            return None
    return Image.open(io.BytesIO(path.read_bytes())).convert("RGBA")


def deg_to_dms(deg: float, axis: str) -> str:
    """12.345 -> '12°21′N'."""
    d, m = divmod(round(abs(deg) * 60), 60)
    if axis == "lat":
        hemi = "N" if deg >= 0 else "S"
    else:
        hemi = "E" if deg >= 0 else "W"
    return f"{d}°{m}′{hemi}"
