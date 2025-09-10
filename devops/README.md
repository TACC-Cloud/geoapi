# Deployment

## Images building + Jenkins

The deployment of images, updating of services and applications, and backup procedures are performed by multiple Jenkins
workflows found [here](https://jenkins01.tacc.utexas.edu/view/Hazmapper+Geoapi/.)

The images used in deployment are built automatically and 
pushed to Docker Hub.

See:
* https://hub.docker.com/r/taccwma/hazmapper
* https://hub.docker.com/r/taccwma/geoapi
* https://hub.docker.com/r/taccwma/geoapi-workers)

Deployment configuration including the tag of which image is deployed is maintained at https://github.com/TACC-Cloud/wma-geospatial-deployments

## Configuration

The configurations for each of the following are in their associated directories:
* geoapi-services - Main backend services (deployed by Camino, see [here](https://github.com/TACC/Core-Portal-Deployments/tree/main/geoapi-workers/camino))
* geoapi-workers - Workers (deployed by Camino, see [here](https://github.com/TACC/Core-Portal-Deployments/tree/main/geoapi-services/camino))
* [database](database/) - geoapi-database
* [hazmapper](hazmapper/) - hazmapper.tacc.utexas.edu
* nfs-geoapi - TODO: See https://tacc-main.atlassian.net/browse/WG-226

Specific hosts for these services are listed at https://tacc-main.atlassian.net/wiki/spaces/UP/pages/6654513/WMA+Projects+and+Portals+Directory.


