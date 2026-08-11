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

## Security Scanning
Using [Trivy](https://github.com/aquasecurity/trivy) to scan Python dependencies for known vulnerabilities.

### Install (macOS)
```bash
brew install trivy
trivy --version
```

### Scan the dependency lockfile
```bash
# Scan the devops poetry.lock (run from this directory)
trivy fs .
```

### Remediating findings
Findings list a **Fixed Version**. Bump the affected packages and re-scan.

The cleanest way to update the lockfile is a throwaway container from our own
image (it already has poetry and the matching Python version), mounting this
`devops/` directory as the working dir so edits write straight back to the host:

```bash
# from the geoapi/ repo root
docker run --rm -it -u root \
  -v "$PWD/devops:/devops" \
  -w /devops \
  taccwma/geoapi:local bash
```

Then inside the container:

```bash
poetry update
```

Poetry edits `/devops/pyproject.toml` and `/devops/poetry.lock` in place; the
mount writes them back to the host.

### Scanning image

Build the production images and then scan

```
make build
trivy image --ignore-unfixed --severity MEDIUM,HIGH,CRITICAL taccwma/geoapi:latest
trivy image --ignore-unfixed --severity MEDIUM,HIGH,CRITICAL taccwma/geoapi-workers:latest
```
