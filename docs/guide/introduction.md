# Introduction

The Digital Twin Toolbox turns common urban datasets into [3D Tiles](https://www.ogc.org/standard/3dtiles/).

You put your files in a storage bucket, pick a workflow, and background workers build the tilesets. The results can be previewed on a map in the application or downloaded.

::: warning Project status
The toolbox is at release candidate stage and is not production ready yet.
:::

## Workflows

Each workflow converts one kind of data. Its page lists the accepted inputs and the options.

- [Point cloud](./workflows/point-cloud): lidar and photogrammetry point clouds
- [Polygon](./workflows/polygon): footprints extruded to volumes, e.g. buildings
- [Point instance](./workflows/point-instance): a 3D model placed on each point, e.g. trees
- [Terrain](./workflows/terrain) (experimental): elevation models to a terrain for the globe
- [CityGML](./workflows/citygml) (experimental): city models
- [Mesh](./workflows/mesh) (experimental): textured meshes, e.g. photogrammetry models
- [Buildings](./workflows/buildings) (experimental): buildings with roofs, reconstructed from footprints and lidar

Workflows that read heights share the same height options, see [Heights](./heights).

## How it works

```
 Browser ──> Frontend ──> Backend API ──> Redis queue ──> Workers
                               │                            │
                               └──── Postgres          S3 storage
                                    (jobs, status)   (inputs, 3D Tiles)
```

1. **Files** live in an S3-compatible bucket. Locally the stack ships its own storage, so nothing external is needed.
2. A **job** runs one workflow on one file. A **batch** runs it on every supported file under a folder and can combine the results into a single tileset.
3. **Workers** pick the jobs up from the queue. Each worker handles a family of workflows (vector, point cloud, mesh), so they scale independently.
4. The **outputs** are written back to the bucket and listed in the Pipelines page, where they can be opened on the map or downloaded.
