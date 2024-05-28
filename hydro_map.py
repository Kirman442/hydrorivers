# -*- coding: utf-8 -*-
"""
Created on Wed May 22 18:45:27 2024

@author: Kirill
"""

import json
import urllib.request
import os
import osmnx as ox
import matplotlib.pyplot as plt
import geopandas as gpd
import time

from matplotlib import colormaps
from shapely.geometry import Point
from matplotlib.offsetbox import OffsetImage, AnnotationBbox
from PIL import Image, ImageDraw, ImageFont
import pandas as pd

data_folder = 'data'
if not os.path.exists(data_folder):
    os.makedirs(data_folder)

output_file = 'foo.png'
output_file_path = os.path.join(data_folder, output_file)
continent = 'Europa'
picture_file_path = os.path.join(
    data_folder, f'{continent}.png'.replace(' ', '_'))

country = "France"
text_pos = 'left'
pd.options.display.max_columns = None

start_time = time.time()
print("start --- %s seconds ---" % (time.time() - start_time))

shapefile_path = r'm:\projekte\Hydrosherds\HydroRIVERS_v10_eu_shp\HydroRIVERS_v10_eu_shp\HydroRIVERS_v10_eu.shp'

# Extract the file name with extension
file_name = os.path.splitext(os.path.basename(shapefile_path))[0] + '.feather'
country_file_name = country.replace(' ', '_') + '.feather'

print("get_capital_info --- %s seconds ---" % (time.time() - start_time))


def check_file_exists(directory, filename):
    file_path = os.path.join(directory, filename)
    return os.path.isfile(file_path)


def ensure_fid_column(gdf):

    if 'fid' not in gdf.columns:
        gdf.insert(0, 'fid', range(1, len(gdf) + 1))
    else:
        if gdf['fid'].dtype == 'float64':
            gdf['fid'] = gdf['fid'].astype(int)
    return gdf


def normalize_width(upland_skm, min_width=.05, max_width=1.5, max_area=10000):
    # Any river segment with an elevation area >= max_area should have the maximum width
    normalized_width = min_width + \
        (max_width - min_width) * (upland_skm / max_area)
    return min(normalized_width, max_width)


def draw_frame(image, outer_white_width=50, black_width=4, inner_white_width=4):
    """
    Draw a frame around the image with the inscription.
    """
    # Create a drawing object
    draw = ImageDraw.Draw(image)

    # Get image dimensions
    width, height = image.size

    # Calculate frame coordinates
    top_left = (0, 0)
    bottom_right = (width - 1, height - 1)

    # Calculate inner rectangle coordinates
    inner_left = outer_white_width
    inner_top = outer_white_width
    inner_right = width - outer_white_width
    inner_bottom = height - outer_white_width

    # Draw outer white frame
    draw.rectangle([top_left, bottom_right],
                   outline="#9B9B9B", width=outer_white_width)

    # Draw black frame
    draw.rectangle([(inner_left, inner_top), (inner_right,
                    inner_bottom)], outline="#006975", width=black_width)

    # Draw inner white frame
    inner_left += black_width
    inner_top += black_width
    inner_right -= black_width
    inner_bottom -= black_width
    draw.rectangle([(inner_left, inner_top), (inner_right, inner_bottom)],
                   outline="#7FD1AE", width=inner_white_width)

    # Draw second black frame
    inner_left += inner_white_width
    inner_top += inner_white_width
    inner_right -= inner_white_width
    inner_bottom -= inner_white_width
    draw.rectangle([(inner_left, inner_top), (inner_right,
                    inner_bottom)], outline="#006975", width=black_width)

    return image


def composite_images(base_image, image_with_inscription_path, save_path):
    """
    Combine all images to get the final image.
    """
    try:
        # Check if image_with_inscription is a PIL Image object
        if not isinstance(image_with_inscription_path, Image.Image):
            raise ValueError(
                "image_with_inscription is not a PIL Image object")

        # Composite images
        final_image = Image.alpha_composite(
            base_image, image_with_inscription_path.convert("RGBA"))

        # Save the result
        final_image.save(save_path)
        print("Image saved successfully:", save_path)

    except FileNotFoundError as e:
        print("Error: File not found:", e.filename)

    except Exception as e:
        print("An error occurred:", e)


def deg_to_dms(deg, pretty_print=None):
    """
    Convert degrees to dms.
    """
    m, s = divmod(abs(deg)*3600, 60)
    d, m = divmod(m, 60)
    if deg < 0:
        d = -d
    d, m = int(d), int(m)

    if pretty_print:
        if pretty_print == 'latitude':
            hemi = 'N' if d >= 0 else 'S'
        elif pretty_print == 'longitude':
            hemi = 'E' if d >= 0 else 'W'
        else:
            hemi = '?'
        return '{d:d}°{m:d}′{hemi:1s}'.format(
            d=abs(d), m=m, hemi=hemi)
    return d, m, s


if not check_file_exists(data_folder, file_name):
    gdf = gpd.read_file(shapefile_path)
    print("read shp file europe --- %s seconds ---" %
          (time.time() - start_time))
    gdf = ensure_fid_column(gdf)
    print("ensure_fid_column gdf europe --- %s seconds ---" %
          (time.time() - start_time))
    gdf.to_feather(os.path.join(data_folder, file_name))
    print("to_feather gdf europe --- %s seconds ---" %
          (time.time() - start_time))
else:
    gdf = gpd.read_feather(os.path.join(data_folder, file_name))
print("check_continent_file_exists --- %s seconds ---" %
      (time.time() - start_time))
print(gdf.iloc[0])
print(gdf.iloc[0:20])

# print('Make map from country boundarys?: 1 - Yes, 0 - No')
# country_map = None
# while country_map not in {0, 1}:
#     country_map = int(input("Please type the matching number: "))

# country_flag = None
# if country_map == 1:
#     # country_flag = None
#     print('Add country flag as capital marker to the map?: 1 - Yes, 0 - No')
#     while country_flag not in {0, 1}:
#         country_flag = int(input("Please type the matching number: "))


# if country_map == 1:
#     picture_file_path = os.path.join(
#         data_folder, f'{country}.png'.replace(' ', '_'))
#     url = "https://mrgallo.github.io/python-fundamental-exercises/_downloads/d1feb1a136dc985fbab706d3092281ab/country-by-capital-city.json"

#     with urllib.request.urlopen(url) as response:
#         data = response.read().decode('utf-8')
#         country_capitals = json.loads(data)

#     def get_capital(country_name):
#         for country in country_capitals:
#             if country["country"] == country_name:
#                 return country["city"]
#         return "Country not found"

#     capital = get_capital(country)
#     print(f"The capital of {country} is {capital}")

#     country_capital = ox.geocode_to_gdf(capital)
#     first_row = country_capital.iloc[0]

#     lat = first_row['lat']
#     lon = first_row['lon']
#     print("Latitude:", lat)
#     print("Longitude:", lon)
#     point = Point(lon, lat)

#     # Convert lat/lon to dms coordinates
#     lat = deg_to_dms(lat, pretty_print='latitude')
#     lon = deg_to_dms(lon, pretty_print='longitude')
#     coords = f"{lat} / {lon}"

#     if not check_file_exists(data_folder, country_file_name):
#         gdf_boundary = ox.geocode_to_gdf(country)
#         gdf_boundary = ensure_fid_column(gdf_boundary)
#         gdf_boundary.to_feather(os.path.join(
#             data_folder, country_file_name))
#     else:
#         gdf_boundary = gpd.read_feather(os.path.join(
#             data_folder, country_file_name))
#     print("check_country_file_exists --- %s seconds ---" %
#           (time.time() - start_time))

#     gdf = gpd.sjoin(gdf, gdf_boundary, how='inner', predicate='within')
#     # gdf.to_file("test.gdf", driver="GPKG")
# # print("Start read_file--- %s seconds ---" %
# #       (time.time() - start_time))
# # gdf = gpd.read_file("test.gdf")
# # print("End read_file--- %s seconds ---" %
# #       (time.time() - start_time))
# def add_inscription(image, city_name, text_position, country_map=None):  # coordinates
#     """
#     Add inscriptions to the image.
#     """
#     # Make image with the same size as original to compose them later together
#     text_image = Image.new("RGBA", image.size, (255, 255, 255, 0))
#     draw_text = ImageDraw.Draw(text_image)
#     picWidth, picHeight = image.size
#     if picWidth > picHeight:
#         fontsize = int(picHeight * 140 / picWidth)
#     else:
#         fontsize = int(picWidth * 140 / picHeight)
#     font = ImageFont.truetype("arial.ttf", size=fontsize)

#     if text_position == 'right':
#         city_name_coord = (picWidth*.8, picHeight * .9)

#     else:
#         city_name_coord = (picWidth * .15, picHeight * .9)

#     # Draw country info
#     if country_map == 1:
#         draw_text.text(city_name_coord, f"{continent}\nCountry: {country}\nCapital: {capital}\n\n{coords}", font=font, fill='#ffffff90',
#                        anchor="ms",  spacing=8, stroke_width=3, stroke_fill='#ABBFC899')
#     else:
#         draw_text.text(city_name_coord, f"{continent}", font=font, fill='#ffffff90',
#                        anchor="ms",  spacing=8, stroke_width=3, stroke_fill='#ABBFC899')
#     final_image = Image.alpha_composite(
#         image.convert("RGBA"), text_image.convert("RGBA"))

#     # return text with gradient and base image
#     return final_image.convert('RGBA')


# # Filter the GeoDataFrame based on a condition
# # If there are too many rivers, you can play with the parameters
# # Replace with your desired value based on these columns. See HydroRIVERS Technical Documentation
# """
# UPLAND_SKM, ORD_STRA, ORD_CLAS, ORD_FLOW
# """


# # condition = (gdf['UPLAND_SKM'] > 10) & (gdf['ORD_FLOW'] <= 5)
# # gdf = gdf[condition]


# # Apply the normalization function to the UPLAND_SKM field
# gdf['line_width'] = gdf['UPLAND_SKM'].apply(normalize_width)


# # Assign a color to each unique MAIN_RIV
# unique_rivers = gdf['MAIN_RIV'].unique()
# cmap = colormaps['Set2']  # You can choose a different colormap
# colors = {river: cmap(i / len(unique_rivers))
#           for i, river in enumerate(unique_rivers)}

# print("Assign a color to each unique MAIN_RIV--- %s seconds ---" %
#       (time.time() - start_time))

# # Create a new column 'color' and set the colors based on MAIN_RIV
# gdf['color'] = gdf['MAIN_RIV'].map(colors)

# # Plot the rivers with different colors and line widths
# fig, ax = plt.subplots(figsize=(15, 15), facecolor='none')
# print("Create subplots --- %s seconds ---" % (time.time() - start_time))
# gdf.plot(ax=ax, color=gdf['color'], linewidth=gdf['line_width'], alpha=1)
# # Draw the country's boundary line
# # gdf_boundary.boundary.plot(ax=ax, color='grey', linewidth=.5)
# print("Create plot --- %s seconds ---" % (time.time() - start_time))

# if country_flag == 1:
#     # get country code to download the flag image of the country
#     url = "https://flagcdn.com/en/codes.json"

#     with urllib.request.urlopen(url) as response:
#         data = response.read().decode('utf-8')
#         country_codes = json.loads(data)

#     def get_counry_code(country_name):
#         for keys, values in country_codes.items():
#             if values == country_name:
#                 return keys
#         return "Country not found"
#     country_code = get_counry_code(country)

#     # Inserting the country code into the flag url and uploading the flag image
#     flag_url = f"https://flagcdn.com/w160/{country_code}.jpg"
#     with urllib.request.urlopen(flag_url) as url:
#         flag_image = Image.open(url)

#     # Show Capital on the map as flag image
#     # Adding an image to a chart
#     imagebox = OffsetImage(flag_image, zoom=0.1)
#     imagebox.image.axes = ax
#     # Creating a dictionary with parameters for the frame
#     bbox_props = dict(boxstyle="round,pad=0.1",
#                       edgecolor="blue", facecolor="white", linewidth=0.5)
#     ab = AnnotationBbox(imagebox, (point.x, point.y),
#                         frameon=True, bboxprops=bbox_props)
#     ax.add_artist(ab)

# # Show Capital on the map as point
# # gdf_point = gpd.GeoDataFrame([{'geometry': point}], crs="EPSG:4326")
# # gdf_point.plot(ax=ax, markersize = 100, alpha=.5)

# # Set background color behind the lines to transparent
# ax.patch.set_facecolor('none')


# plt.savefig(output_file_path, dpi=600, bbox_inches='tight', transparent=True)

# rivers_image = Image.open(output_file_path).convert("RGBA")
# output_image = draw_frame(rivers_image)  # picture
# image_with_inscription = add_inscription(
#     output_image, continent, text_pos, country_map)
# print("add all inscription--- %s seconds ---" % (time.time() - start_time))


# composite_images(rivers_image, image_with_inscription, picture_file_path)
# print("composite_images--- %s seconds ---" % (time.time() - start_time))

# # Delete permanent image file
# os.remove(os.path.join(data_folder, output_file))

# plt.show()

print("All done --- %s seconds ---" % (time.time() - start_time))
