# Deployment

## Images building + Jenkins

The deployment of images and updating of the services and applications is performed by a Jenkins
workflow found [here](https://jenkins01.tacc.utexas.edu/view/Hazmapper+Geoapi/.)

The images used in deployment are built automatically for the master branch using TravisCI and 
pushed to Docker Hub (see https://hub.docker.com/r/taccaci/hazmapper).

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
