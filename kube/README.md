# Kubernetes + Deployment

## Images building + Jenkins

The deployment of images and updating of the Kubernetes services and applications is performed by a Jenkins
workflow found [here](https://jenkins01.tacc.utexas.edu/view/Hazmapper+Geoapi/.)

The images used in deployment are built automatically for the master branch using TravisCI and 
pushed to Docker Hub (see https://hub.docker.com/r/taccaci/geoapi and https://hub.docker.com/r/taccaci/geoapi-workers).

### Kube config

[`geoapi.deployment.yaml`](geoapi.deployment.yaml) describes the configuration of the cluster. The file is adjusted using `envsubstr` to provide
custom values for the image tags, node port and nfs service for the production or staging environments.

The [`nfsshare.service.yaml`](nfsshare.service.yaml) and the [`nfsshare_pvc.yaml`](nfsshare.pvc.yaml) in the repo are used for configuring the nfs share. Note that the
configuration (i.e. `persistentVolumeClaim`) is the same for production and staging except that the clusterIP differs:

* clusterIP: 10.104.129.89  (prod)
* clusterIP: 10.102.247.244 (dev)

This service/pod **are only set up once manually** for production deployment and then once for staging deployment.
They do not need to be updated for any changes to source code.

## Access and Troubleshooting

`cic02` is used to access the cluster for the production (context=`wma-geospatial`) and staging (context=`geoapi-dev`)
environments.

```
ssh cic02
CONTEXT=`geoapi-dev`
kubectl get --context=$CONTEXT all
kubectl describe --context=$CONTEXT deployment.apps/geoapi
kubectl logs --tail 100 --context=$CONTEXT deployment.apps/geoapi
kubectl logs --tail 100 --context=$CONTEXT deployment.apps/geoapi-workers
```
