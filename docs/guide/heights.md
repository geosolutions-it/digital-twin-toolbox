# Heights

A tileset sits where its heights say, so the heights must use the same reference as the viewer's ground:

- **Ellipsoidal** heights are measured from the ellipsoid. CesiumJS and its terrains use them.
- **Orthometric** heights are measured from the geoid, roughly sea level. Most surveys and many web terrains use them.

The two differ by the local geoid height, from a few metres to tens of metres. A tileset with the wrong reference floats above the ground or sinks into it by that amount.

## Options

Every workflow that reads heights from its input has the same two options.

| Option | Description |
| --- | --- |
| Height conversion | **None** keeps the heights of the input. **Geoid → ellipsoidal** converts orthometric heights for CesiumJS. **Ellipsoidal → geoid** converts ellipsoidal heights to orthometric. |
| Geoid EPSG | The geoid of the conversion, EGM2008 (`3855`) when empty: the geoid of the input for **Geoid → ellipsoidal**, of the output for **Ellipsoidal → geoid**. |

When the input declares its vertical CRS, that CRS is used for the input instead of **Geoid EPSG**.

## Which one to pick

| Input heights | Viewer ground | Height conversion |
| --- | --- | --- |
| orthometric, e.g. a survey above sea level | CesiumJS | Geoid → ellipsoidal |
| ellipsoidal, e.g. GNSS or many lidar deliveries | CesiumJS | None |
| ellipsoidal | an orthometric terrain | Ellipsoidal → geoid |
| same reference as the ground | any | None |

A conversion always runs when selected. If the heights are already ellipsoidal but the file does not say so, pick **None**, otherwise the geoid height is added twice.

Use the same choice for every dataset of an area, so they sit at the same height.

## Geoid grids

The conversion uses a geoid grid that the worker downloads on first use, so the workers need internet access.

When a grid can't be found, the job fails with a message about the missing PROJ geoid grid. It never writes unconverted heights silently.
