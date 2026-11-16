# CityGML <Badge type="warning" text="experimental" />

::: warning Experimental
This workflow is new and has been tried on few datasets. Its options and output may change.
:::

Converts a CityGML or CityJSON city model, such as LoD1 or LoD2 buildings, to 3D Tiles. The geometry is used as it is in the file, no extrusion is needed.

## Input

- A CityGML file (`.gml`), a CityJSON file (`.city.json`, `.city.jsonl`), or a zip with one or more of them. All the files of a zip end up in the same tileset.
- The CRS is read from the file. When the file has none, set **Horizontal EPSG**.
- Every city object is converted: buildings, bridges, vegetation, furniture and so on. Terrain (`ReliefFeature`) and groups are skipped.

## Options

| Option | Description |
| --- | --- |
| Level of detail | Highest LoD to use, by default the highest available. Each object is converted at its best LoD up to this one. |
| Height conversion, Geoid EPSG | See [Heights](../heights). A vertical CRS declared in the file is used for the input. |
| Horizontal EPSG | CRS to use when the file declares none. |
| Orthophoto for the roofs | Bucket key of an orthophoto. Textures the roofs and adds a `roof_color` attribute. |
| Texture resolution (m) | Size of a texture pixel on the ground. Empty uses the orthophoto's. |
| Max tile size (KB) | Upper limit for the size of each tile. |

## Output

3D Tiles of the city objects, with textured roofs when an orthophoto is set. Each object keeps its attributes, plus `gml_id` and `citygml_type` (e.g. `Building`), so viewers can show them on click.

## Tips

- Pick a lower **Level of detail** for a lighter tileset over a large area, e.g. LoD1 blocks instead of LoD2 roofs.
