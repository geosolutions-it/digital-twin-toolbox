# <img src="./static/img/logo.svg" height="32" /> Digital Twin Toolbox

Introduction
============
This repository collects different tools/libraries and workflows inside a docker environment to generate 3D Tiles from common data sources such as Shapefiles and LAS files. 
The short term goal is to evaluate the various open source tools that are available to generate 3D Tiles from various data sources typically used when modeling an urban environment when creating a 3D Model like building and Lidar data. The long term goal is to transform this experiment into an engine that can be used to create 3D Tiles for urban environments.

This project is still a work in progress and this application **is not** production ready. Extensive documentation about this project can be found in the [wiki](https://github.com/geosolutions-it/digital-twin-toolbox/wiki) page (see the Table of Contents).

At the moment we have draft pipelines for:
- converting shapefile data (polygons, lines, points) into 3DTiles
- converting lidar data to point 3DTiles dataset
- processing lidar to fix/manage CRS, resample and color it
- converting lidar data to a 3D Mesh file (experimental at this stage)
- converting 3D Mesh to 3DTiles dataset (experimental at this stage)

![](https://github.com/geosolutions-it/digital-twin-toolbox/wiki/images/vector-point-tiling.png)

License
============
This work is licensed using [GPL v3.0 license](https://github.com/geosolutions-it/digital-twin-toolbox/blob/main/LICENSE.txt).

Credits
============
We would like to thanks the **City of Florence** and **Politechnic University of Turin** for providing funding to bootstrap this work. The evolution of this project is right now an effort funded by GeoSolutions.
If you are interested in participating or funding this work please, drop an email to info@geosolutionsgroup.com or engage with us through GitHub discussions and issues.

