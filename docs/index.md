---
layout: home
hero:
  name: Digital Twin Toolbox
  text: 3D Tiles from urban data
  tagline: Turn point clouds, footprints, terrain, meshes and city models into streamable 3D Tiles, on your own machine.
  actions:
    - theme: brand
      text: Get started
      link: /guide/getting-started
    - theme: alt
      text: Workflows
      link: /guide/introduction#workflows
    - theme: alt
      text: GitHub
      link: https://github.com/geosolutions-it/digital-twin-toolbox
features:
  - title: Point cloud
    details: LAS and LAZ thinned, colorized from an orthophoto and ground classified.
    link: /guide/workflows/point-cloud
  - title: Polygon
    details: Footprints extruded to volumes, with heights from attributes or formulas.
    link: /guide/workflows/polygon
  - title: Point instance
    details: A 3D model on every point, e.g. trees and street furniture.
    link: /guide/workflows/point-instance
  - title: Terrain
    details: Elevation models to a quantized-mesh ground for the globe. Experimental.
    link: /guide/workflows/terrain
  - title: CityGML
    details: CityGML and CityJSON city models, with their attributes. Experimental.
    link: /guide/workflows/citygml
  - title: Mesh
    details: Textured OBJ models placed on the globe, with levels of detail. Experimental.
    link: /guide/workflows/mesh
  - title: Buildings
    details: Roofs reconstructed from footprints and a classified lidar point cloud. Experimental.
    link: /guide/workflows/buildings
---

<div class="vp-doc" style="max-width: 1152px; margin: 64px auto 0; padding: 0 24px">

::: warning Project status
The toolbox is at release candidate stage and is not production ready yet.
:::

## Credits

We would like to thanks the **City of Florence** and **Politechnic University of Turin** for providing funding to bootstrap this work. The evolution of this project is right now an effort funded by GeoSolutions.

If you are interested in participating or funding this work please, drop an email to info@geosolutionsgroup.com or engage with us through GitHub discussions and issues.

</div>
