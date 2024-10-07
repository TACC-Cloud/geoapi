# Deployment

## Images building + Jenkins

The deployment of images and updating of the services and applications is performed by a Jenkins
workflow found [here](https://jenkins01.tacc.utexas.edu/view/Hazmapper+Geoapi/.)

The images used in deployment are built automatically and 
pushed to Docker Hub.

See:
* https://hub.docker.com/r/taccaci/hazmapper
* https://hub.docker.com/r/taccaci/geoapi
* https://hub.docker.com/r/taccaci/geoapi-workers)

Deployment configuration including the tag of which image is deployed is maintained at https://github.com/TACC-Cloud/wma-geospatial-deployments

## Access and Troubleshooting
The configurations of each of the following are in their associated directories. 

### VM for nginx:  

    hazmapper.tacc.utexas.edu 
    
    see hazmapper repo [ngnix.conf] (https://github.com/TACC-Cloud/hazmapper/blob/master/nginx.conf)

### VMs for backend services 
    dev.geoapi-services.tac.utexas.edu
    staging.geoapi-services.tac.utexas.edu
    prod.geoapi-services.tac.utexas.edu

### VMs for Workers
    129.114.35.63 - used by Hazmapper prod as its worker and is a machine provided to us by Mike Packard 
    staging.geoapi-workers.tacc.utexas.edu
    prod.geoapi-workers.tacc.utexas.edu

### VM for Database
    geoapi-database.tacc.utexas.edu

### VM hosting mounted NFS assets
    geoapi-nfs.tacc.utexas.edu 
