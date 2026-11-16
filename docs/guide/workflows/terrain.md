# Terrain <Badge type="warning" text="experimental" />

::: warning Experimental
This workflow is new and has been tried on few datasets. Its options and output may change.
:::

Converts an elevation model to a terrain for the globe, in the quantized-mesh format used by CesiumJS. The other tilesets can then sit on the real ground instead of the flat ellipsoid.

## Input

- A GeoTIFF elevation model (`.tif`, `.tiff`), heights in metres in the first band.
- The file must declare its CRS.
- Pixels without data are set to height 0.

## Options

| Option | Description |
| --- | --- |
| Max zoom | Deepest level of detail. Empty picks the level that matches the pixel size of the input, up to 18. |
| Height conversion, Geoid EPSG | See [Heights](../heights). |
| Vertex normals (lighting) | Adds normals so the viewer can shade the slopes. |

## Output

A quantized-mesh terrain: a `layer.json` file and one `.terrain` file per tile.

To use it as the ground of the globe, open **Map** and select it under **Terrain**. The default is **Ellipsoid (flat)**.

## Tips

- Use a terrain model (DTM, bare ground), not a surface model (DSM). With a DSM, buildings and trees become bumps in the ground under the other tilesets.
- Use the same [height conversion](../heights) for the terrain and the other datasets of the area, so everything sits at the same height.
- A lower **Max zoom** builds much faster and gives a lighter terrain. Each extra level has about four times as many tiles.
