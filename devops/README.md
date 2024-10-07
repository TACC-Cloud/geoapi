# Deployment

## Images building + Jenkins

The deployment of images, updating of services and applications, and backup procedures are performed by multiple Jenkins
workflows found [here](https://jenkins01.tacc.utexas.edu/view/Hazmapper+Geoapi/.)

The images used in deployment are built automatically and 
pushed to Docker Hub.

See:
* https://hub.docker.com/r/taccaci/hazmapper
* https://hub.docker.com/r/taccaci/geoapi
* https://hub.docker.com/r/taccaci/geoapi-workers)

Deployment configuration including the tag of which image is deployed is maintained at https://github.com/TACC-Cloud/wma-geospatial-deployments

## Configuration

The configurations for each of the following are in their associated directories:
* [geoapi-services](geoapi-services/) - Main backend services
* [geoapi-workers](geoapi-workers/) - Workers
* [database](database/) - geoapi-database
* [hazmapper](hazmapper/) - hazmapper.tacc.utexas.edu
* nfs-geoapi - TODO: See https://tacc-main.atlassian.net/browse/WG-226

Specific hosts for these services are listed at https://tacc-main.atlassian.net/wiki/spaces/UP/pages/6654513/WMA+Projects+and+Portals+Directory.


