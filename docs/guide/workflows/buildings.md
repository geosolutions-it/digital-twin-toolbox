# Buildings <Badge type="warning" text="experimental" />

::: warning Experimental
This workflow is new and has been tried on few datasets. Its options and output may change.
:::

Reconstructs buildings with their roofs from footprints and a classified lidar point cloud, and converts them to 3D Tiles. The reconstruction is done by [Roofer](https://github.com/3DBAG/roofer).

## Input

- The footprints: a Shapefile of polygons, zipped with its sidecar files including the `.prj`. Each footprint becomes one building and keeps its attributes.
- A LAS or LAZ point cloud with ground and building classes, in the same horizontal CRS as the footprints. Set a single file or a folder: from a folder, only the files that overlap the footprints are used.

In **Assets**, click **Process** on the footprints and pick **Buildings (roofs from a point cloud)** as the workflow. This workflow runs on single files only, not in batches.

## Options

| Option | Description |
| --- | --- |
| Point cloud | Required. Bucket key of a LAS or LAZ file, or of a folder ending with `/`. |
| Level of detail | **LoD 2.2** roof shapes, **LoD 1.3** flat roofs with steps, **LoD 1.2** one flat roof per building. |
| Orthophoto for the roofs | Bucket key of an orthophoto. Textures the roofs and adds a `roof_color` attribute. |
| Texture resolution (m) | Size of a texture pixel on the ground. Empty uses the orthophoto's. |
| Terrain (DTM) | Bucket key of a terrain model. Lowers the building bases onto the ground on slopes. It must use the same height reference as the point cloud. |
| Building class, Ground class | Classes of the point cloud for buildings and ground, `6` and `2` by default. |
| Height conversion, Geoid EPSG | See [Heights](../heights). The heights come from the point cloud. |
| Max tile size (KB) | Upper limit for the size of each tile. |

## Output

3D Tiles of the buildings, with the attributes of their footprints.

The reconstructed buildings are also saved as CityJSON (`buildings.city.jsonl`), available from **Other outputs** on the job.

## Tips

- Buildings that Roofer can't reconstruct at the chosen level of detail are left out, e.g. footprints without enough building points.
- LoD 2.2 takes the longest. Try LoD 1.2 first on a large area.
