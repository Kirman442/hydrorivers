"""Stylised river maps of a country or a whole continent from HydroRIVERS.

Examples
--------
    # whole file (e.g. South America), only rivers with ORD_FLOW <= 6
    python hydro_map.py data/HydroRIVERS_v10_sa.parquet --label "South America" --max-ord-flow 6

    # one or several countries, with capital, coordinates and flag
    python hydro_map.py data/HydroRIVERS_v10_sa.parquet --country Venezuela Uruguay --flag

Run ``python hydro_map.py -h`` for all options.
"""

from __future__ import annotations

import argparse
import time
from pathlib import Path

from hydromap import data, places, render

CACHE_DIR = Path("data/cache")


def parse_args(argv=None):
    p = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    p.add_argument("rivers", type=Path,
                   help="HydroRIVERS file: .parquet (fastest, see convert_to_parquet.py), "
                        ".shp, .gpkg, .gdb or .feather")
    p.add_argument("--country", nargs="+", metavar="NAME",
                   help="country name(s) in English, German or Russian, or ISO code")
    p.add_argument("--label", help="caption for a map without --country, e.g. 'South America'")
    p.add_argument("--out-dir", type=Path, default=Path("maps"))

    f = p.add_argument_group("filters (see HydroRIVERS technical documentation)")
    f.add_argument("--min-upland", type=float, help="keep UPLAND_SKM > value (km²)")
    f.add_argument("--max-ord-flow", type=int, help="keep ORD_FLOW <= value")
    f.add_argument("--max-ord-stra", type=int, help="keep ORD_STRA <= value")
    f.add_argument("--max-ord-clas", type=int, help="keep ORD_CLAS <= value")
    f.add_argument("--where", help="extra pandas query, e.g. \"DIS_AV_CMS > 1\"")

    s = p.add_argument_group("style")
    s.add_argument("--color-by", default="main_riv",
                   help="main_riv (one colour per river system) or a column such as "
                        "ORD_FLOW, ORD_STRA, DIS_AV_CMS")
    s.add_argument("--cmap", default="Set2", help="matplotlib or colorcet colormap name")
    s.add_argument("--min-width", type=float, default=0.05)
    s.add_argument("--max-width", type=float, default=1.5)
    s.add_argument("--max-area", type=float, default=10_000,
                   help="UPLAND_SKM at which the line reaches --max-width")
    s.add_argument("--crs", help="project before drawing, e.g. EPSG:3035 for Europe")
    s.add_argument("--background", default="black")
    s.add_argument("--transparent", action="store_true")
    s.add_argument("--dpi", type=int, default=300, help="600 gives a 9000 px print file")
    s.add_argument("--size", type=float, default=15, help="figure size in inches")
    s.add_argument("--flag", action="store_true", help="put the flag on the capital")
    s.add_argument("--no-frame", action="store_true")
    s.add_argument("--text-pos", choices=["left", "right"], default="left")
    return p.parse_args(argv)


def make_map(args, country_name: str | None):
    t0 = time.perf_counter()
    bounds = data.dataset_bounds(args.rivers)
    country = None
    if country_name:
        country = places.find_country(country_name, CACHE_DIR)
        area, bbox = data.limit_to_data(country.geometry, bounds)
        if area.is_empty:
            print(f"{country.name}: not covered by {args.rivers.name}, skipped.")
            return
        rivers = data.read_rivers(args.rivers, bbox=bbox)
        rivers = data.clip_to_area(rivers, area)
    else:
        rivers = data.read_rivers(args.rivers)
    rivers = data.apply_filters(rivers, args.min_upland, args.max_ord_flow,
                                args.max_ord_stra, args.max_ord_clas, args.where)
    if rivers.empty:
        print("No river segments left after filtering.")
        return
    print(f"{len(rivers):,} segments loaded in {time.perf_counter() - t0:.1f} s")

    flag = flag_xy = None
    if country and country.capital_lonlat:
        flag_xy = country.capital_lonlat
        if args.flag and country.iso_a2:
            flag = places.download_flag(country.iso_a2, CACHE_DIR)
    if args.crs:
        rivers = rivers.to_crs(args.crs)
        if flag_xy:
            import geopandas as gpd
            from shapely.geometry import Point
            pt = gpd.GeoSeries([Point(flag_xy)], crs="EPSG:4326").to_crs(args.crs).iloc[0]
            flag_xy = (pt.x, pt.y)

    widths = render.line_widths(rivers["UPLAND_SKM"], args.min_width, args.max_width,
                                args.max_area)
    colors = render.line_colors(rivers, args.color_by, args.cmap)

    args.out_dir.mkdir(parents=True, exist_ok=True)
    name = country.name if country else (args.label or args.rivers.stem)
    out = args.out_dir / f"{name.replace(' ', '_')}.png"
    render.plot_rivers(rivers, out, widths, colors, figsize=args.size, dpi=args.dpi,
                       background=args.background, transparent=args.transparent,
                       flag=flag, flag_xy=flag_xy)

    if country:
        caption = f"{country.continent}\nCountry: {country.name}"
        if country.capital:
            lon, lat = country.capital_lonlat
            caption += (f"\nCapital: {country.capital}\n\n"
                        f"{places.deg_to_dms(lat, 'lat')} / {places.deg_to_dms(lon, 'lon')}")
    else:
        caption = args.label
    render.finish_image(out, caption, args.text_pos, frame=not args.no_frame)
    print(f"Saved {out} ({time.perf_counter() - t0:.1f} s)")


def main(argv=None):
    args = parse_args(argv)
    for country in args.country or [None]:
        make_map(args, country)


if __name__ == "__main__":
    main()
