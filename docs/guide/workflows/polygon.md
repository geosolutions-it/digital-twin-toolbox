# Polygon

Extrudes polygons, such as building footprints, into 3D volumes and converts them to 3D Tiles. The heights can come from a fixed value, an attribute or a formula.

## Input

- A Shapefile zipped with its sidecar files (`.shp`, `.shx`, `.dbf`, `.prj`).
- Polygon and MultiPolygon features. Other geometries are skipped.
- The layer must declare its CRS, i.e. the zip must contain the `.prj` file.
- 2D and 3D footprints are both supported. A 2D footprint sits at height 0.

## Options

| Option | Description |
| --- | --- |
| Building height (m) | Height of the top of each volume. |
| Base height (m) | Height of the bottom of each volume. Empty uses the footprint height. |
| Height conversion, Geoid EPSG | See [Heights](../heights). |
| Remove bottom surface | Leaves the bottom of the volumes open, which is lighter and invisible from above. |
| Max tile size (KB) | Upper limit for the size of each tile. |

With both heights empty, the footprints are converted flat, without volume.

## Heights and formulas

Both heights are **elevations**, not heights above the footprint. With 3D footprints, add the footprint height to get a volume that starts on the ground:

```
$minZ + height
```

The height fields accept a number, an attribute of the layer or a formula:

| Element | Example |
| --- | --- |
| number | `12.5` |
| attribute | `height`, or `[roof height]` when the name has spaces |
| arithmetic | `+ - * /` and parentheses, e.g. `floors * 3` |
| footprint height | `$minZ` lowest point, `$maxZ` highest point |

The field lists the layer attributes and checks the formula while typing. A feature where the formula can't be evaluated, e.g. an empty attribute, is converted flat.

## Output

3D Tiles of the volumes. Each volume keeps the attributes of its feature, so viewers can show them on click.

## Tips

- Lines and points in the same layer are skipped. Use [Point instance](./point-instance) to place models on points.
- Lower **Max tile size** if the tiles load slowly on weak connections, raise it for fewer requests.
