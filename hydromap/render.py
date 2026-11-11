"""Styling and drawing of the river network, frame and caption."""

from __future__ import annotations

import math
from pathlib import Path

import matplotlib

matplotlib.use("Agg")  # no window needed; works on servers and in batch runs

import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
import shapely  # noqa: E402
from matplotlib import colormaps, font_manager  # noqa: E402
from matplotlib.collections import LineCollection  # noqa: E402
from matplotlib.offsetbox import AnnotationBbox, OffsetImage  # noqa: E402
from PIL import Image, ImageDraw, ImageFont  # noqa: E402


# ---------------------------------------------------------------- styling ---

def line_widths(upland_skm, min_width=0.05, max_width=1.5, max_area=10_000):
    """Line width grows linearly with upstream area and is capped at max_width.

    Same formula as the first version, but on the whole column at once instead
    of a Python call per segment.
    """
    upland = np.asarray(upland_skm, dtype="float64")
    return np.clip(min_width + (max_width - min_width) * upland / max_area,
                   min_width, max_width)


def line_colors(gdf, color_by="main_riv", cmap_name="Set2"):
    """RGBA colour per segment.

    ``main_riv``: every river system gets its own colour, as before.
    Any other value is a numeric column (e.g. ORD_FLOW, DIS_AV_CMS) shown with a
    continuous colormap; discharge is log-scaled.
    """
    cmap = colormaps[cmap_name]
    if color_by == "main_riv":
        codes, uniques = pd.factorize(gdf["MAIN_RIV"])
        return cmap(codes / max(len(uniques), 1))
    values = gdf[color_by].to_numpy(dtype="float64")
    if color_by == "DIS_AV_CMS":
        values = np.log10(values + 1e-3)
    if color_by.startswith("ORD_"):
        values = -values  # order 1 = biggest river -> top of the colormap
    lo, hi = np.nanmin(values), np.nanmax(values)
    return cmap((values - lo) / (hi - lo) if hi > lo else np.zeros_like(values))


# ---------------------------------------------------------------- drawing ---

def _segments(geoms):
    """LineStrings -> list of (n, 2) coordinate arrays for LineCollection."""
    coords, (offsets,) = shapely.to_ragged_array(geoms)[1:]
    return np.split(coords[:, :2], offsets[1:-1])


def plot_rivers(gdf, out_path: Path, widths, colors, figsize=15, dpi=300,
                background="black", transparent=False, flag=None, flag_xy=None):
    """Draw all segments as one LineCollection and save a PNG.

    One collection is much faster than GeoDataFrame.plot() with per-row colours
    and widths, which matters at a million segments.
    """
    fig, ax = plt.subplots(figsize=(figsize, figsize), facecolor=background)
    ax.add_collection(LineCollection(_segments(gdf.geometry.values),
                                     colors=colors, linewidths=widths,
                                     capstyle="round", joinstyle="round"))
    minx, miny, maxx, maxy = gdf.total_bounds
    ax.set_xlim(minx, maxx)
    ax.set_ylim(miny, maxy)
    if gdf.crs is None or gdf.crs.is_geographic:
        # Same correction geopandas applies: keep shapes right at this latitude.
        ax.set_aspect(1 / math.cos(math.radians((miny + maxy) / 2)))
    else:
        ax.set_aspect("equal")
    ax.set_axis_off()
    ax.patch.set_facecolor("none")

    if flag is not None and flag_xy is not None:
        box = AnnotationBbox(OffsetImage(flag, zoom=0.1), flag_xy,
                             frameon=True, bboxprops=dict(boxstyle="round,pad=0.1",
                             edgecolor="blue", facecolor="white", linewidth=0.5))
        ax.add_artist(box)

    fig.savefig(out_path, dpi=dpi, bbox_inches="tight",
                facecolor="none" if transparent else background, transparent=transparent)
    plt.close(fig)


# ------------------------------------------------------- frame & caption ---

def draw_frame(image, outer=50, line=4, gap=4,
               colors=("#9B9B9B", "#006975", "#7FD1AE", "#006975")):
    """Grey passe-partout plus three thin lines inside it (drawn in place)."""
    draw = ImageDraw.Draw(image)
    w, h = image.size
    draw.rectangle([(0, 0), (w - 1, h - 1)], outline=colors[0], width=outer)
    inset = outer
    for color, width in zip(colors[1:], (line, gap, line)):
        draw.rectangle([(inset, inset), (w - inset, h - inset)], outline=color, width=width)
        inset += width
    return image


def _font(size):
    """A bold sans font that exists everywhere matplotlib is installed."""
    path = font_manager.findfont(font_manager.FontProperties(family="DejaVu Sans"))
    return ImageFont.truetype(path, size=size)


def add_caption(image, text, position="left"):
    """Semi-transparent caption near the bottom; size scales with the image."""
    w, h = image.size
    size = max(12, round(min(w, h) * 0.0156))  # = 140 px on a 9000 px map, as before
    layer = Image.new("RGBA", image.size, (255, 255, 255, 0))
    xy = (w * (0.8 if position == "right" else 0.15), h * 0.9)
    ImageDraw.Draw(layer).multiline_text(
        xy, text, font=_font(size), fill="#ffffff90", anchor="ms", align="center",
        spacing=8, stroke_width=3, stroke_fill="#ABBFC899")
    return Image.alpha_composite(image, layer)


def finish_image(png_path: Path, caption: str | None, position="left", frame=True):
    """Add frame and caption to the saved map and overwrite it."""
    image = Image.open(png_path).convert("RGBA")
    if frame:
        image = draw_frame(image)
    if caption:
        image = add_caption(image, caption, position)
    image.save(png_path, optimize=True)
