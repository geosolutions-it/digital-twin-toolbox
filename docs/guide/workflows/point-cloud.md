# Point cloud

Converts a LAS or LAZ point cloud to 3D Tiles. It can thin the points, colorize them from an orthophoto, classify the ground and convert the heights.

## Input

- LAS or LAZ, any version.
- The file must declare its CRS, otherwise the job fails.
- Colour, classification and intensity are kept when present.

## Options

| Option | Description |
| --- | --- |
| Sample radius (m) | Keeps at most one point within this distance. Empty picks a radius from the point spacing, which only removes near-duplicate points. |
| Colorization raster | Bucket key of an orthophoto, e.g. `rasters/orthophoto.tif`. Each point takes the colour of the pixel below it. |
| Height conversion, Geoid EPSG | See [Heights](../heights). A vertical CRS declared in the file is used for the input. |
| Classify ground points | Marks noise and ground points, replacing any existing classification. |

## Output

Point cloud 3D Tiles, with the colour, classification and intensity attributes when present.

## Tips

- The colorization raster should use the same CRS as the point cloud and cover it entirely; points outside the raster stay black.
- Set a sample radius larger than the point spacing to make big clouds lighter, e.g. `0.5` for a dense urban survey.
- Ground classification is the slowest step. Skip it when the survey is already classified.
