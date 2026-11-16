# Point instance

Places a 3D model on each point of a layer, such as trees, street lights or benches, and converts them to 3D Tiles. Each model is stored once and repeated at every point, so thousands of instances stay light.

## Input

- A Shapefile of points, zipped with its sidecar files (`.shp`, `.shx`, `.dbf`, `.prj`). MultiPoint features are skipped.
- One or more models in binary glTF (`.glb`), uploaded to the bucket, e.g. in a `models/` folder. Textures and buffers must be embedded in the `.glb`.

**Process** on a point layer opens this workflow directly. In a batch, pick **Point instance**.

## Options

| Option | Description |
| --- | --- |
| Models prefix | Bucket folder of the models, e.g. `models/`. The model field then lists the `.glb` files found there. |
| Model | Model file name, or an attribute holding it, to place different models per point. |
| Scale | Size multiplier of the model. |
| Rotation (deg) | Rotation of the model around the vertical axis. |
| Elevation (m) | Elevation of the model base. Empty uses the point height, 0 for 2D points. |
| Height conversion, Geoid EPSG | See [Heights](../heights). |
| Max tile size (KB) | Upper limit for the size of each tile. |
| Max geometric error | Controls from which distance the instances start to appear. Lower values show them only when closer. |

Model, scale, rotation and elevation accept a number, an attribute or a formula, with the same syntax as the [Polygon heights](./polygon#heights-and-formulas). For example `height / 10` scales each tree from its height attribute.

## Output

3D Tiles with one instanced model per point. Each instance keeps the attributes of its point.

## Tips

- Points whose model can't be found in the bucket are skipped. The job fails only if no point has a valid model.
- Keep the models light: their size is repeated in every tile that uses them.
