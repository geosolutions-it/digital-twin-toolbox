# Mesh <Badge type="warning" text="experimental" />

::: warning Experimental
This workflow is new and has been tried on few datasets. Its options and output may change.
:::

Converts a textured OBJ mesh, such as a photogrammetry model or a detailed building, to 3D Tiles with levels of detail.

## Input

- A zip with the `.obj`, its `.mtl` and the texture images. When the zip holds several `.obj` files, the one closest to the root is used.
- A single `.obj` file also works, but without its textures.
- Coordinates in metres, around a local origin. The mesh has no CRS: you place it with the options below.

## Options

| Option | Description |
| --- | --- |
| Latitude, Longitude | Required. Where the mesh origin (0, 0, 0) is placed. Click the preview map to pick them. |
| Altitude (m, ellipsoidal) | Height of the mesh origin above the ellipsoid. |
| Forward axis (north) | Axis of the file that points north. |
| Up axis | Axis of the file that points up. Many tools export Y up. |
| Depth | Number of detail levels below the root, from 0 to 8. Each level splits a tile in four. |
| Faces per tile | Triangles kept in each tile after simplification. |
| Texture size (px) | Size of the texture of each tile. |
| Max geometric error | Controls from which distance the mesh appears. Empty derives it from the mesh size. |
| Decimate the last level | Simplifies the most detailed level too. Off keeps the original triangles there. |

## Output

Textured 3D Tiles, with simplified levels of detail for far views.

## Tips

- If the mesh shows up lying on its side, swap **Up axis** between Y and Z. If it's rotated, change **Forward axis**.
- The altitude is ellipsoidal: add the local geoid height to a height above sea level, otherwise the mesh floats or sinks. See [Heights](../heights).
- More depth or a larger texture size gives sharper close views, but each step takes longer and produces a heavier tileset.
- A batch includes meshes only when **Mesh** is picked, and the same placement applies to every mesh. Use it for meshes that share the same origin.
