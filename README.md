# GeoAPI

[![PyPI version](https://badge.fury.io/py/geoapi-client.svg)](https://badge.fury.io/py/geoapi-client)

## Overview and Architecture

GeoAPI is a restful API to create geospatial features in a PostGIS database. Users create a map "project" then
can add features to it. The development docker-compose file has 3 containers: 
* a PostGIS database exposing 5432, 
* the api which exposes port 8000 behind gunicorn
* an nginx server to serve static files and proxy to the api, running on port 8080. 

See https://github.com/TACC-Cloud/hazmapper which is an associated viewer application.

## Setup

#### Configure .env file

Environment variables are used to define the tenant's service accounts which are needed to access metadata and some user
information. An .env file for developers can be found on [UT Stache](https://stache.utexas.edu/entry/892c730561534ed3b3d306dbf933455d).

#### Python side

The API is built with flask and flask-restplus. It is running in its own container
under gunicorn on port 8000

`make build`
`make start`

###### Initialize the database

`docker exec -it geoapi python initdb.py`

###### Obtain a JWT

Refer to the confluence page or ask a colleague for assistance in obtaining a JWT.

###### Make some requests

You need to add the following header for authentication:

`X-JWT-Assertion-designsafe` to equal the JWT obtained above

###### Create a new map project

send a POST request to `localhost:8000/projects` with a body like this: 

```json
{
  "name": "Awesome Project",
  "description": "Cool project"
}

```

send a GET request to `localhost:8000/projects` and you should get that back.

### Client viewer

See https://github.com/TACC-Cloud/hazmapper for details.

### Creating migrations when updating database models

These are useful steps to follow when there are changes to the database model.

First, apply migrations:

```
docker exec -it geoapi alembic upgrade head
```

Then, create migrations:

```
docker exec -it geoapi /bin/bash
alembic revision --autogenerate
# Then:
# - remove drop table commands for postgis
# - add/commit migrations
```

## Testing

Run route/service tests on the `api` container
```
docker-compose -f devops/docker-compose.test.yml -p geoapi_test run api pytest
```

Run worker-related tasks on the `workers` container
```
docker-compose -f devops/docker-compose.test.yml -p geoapi_test run workers pytest -m "worker"
```

Note that images need to be rebuilt before running tests if they have been updated (e.g. packages):
```
make build
```

or run directly in your running containers:
```
docker exec -it geoapi_postgres psql -d postgres  -U dev
CREATE DATABASE TEST;
 \connect test;
CREATE EXTENSION postgis;

# then run tests in api
docker exec -it geoapi bash
APP_ENV=testing pytest

# then run tests in worker
docker exec -it geoapiworkers bash
APP_ENV=testing pytest -m "worker"
```

## Kubernetes (Production/Staging)

Information on Kubernetes configuration for production and staging environments can be found in the [kube/README.md](kube/README.md) including information
on kube commands and Jenkins deployment workflows.


## Python client

The python package can be found at [PyPi](https://pypi.org/project/geoapi-client/)

### Python client generation

Python client is generated from the swagger definition of GeoAPI.  The following steps can be used to get swagger definition:
```
docker exec -it geoapi python output_swagger.py swagger.json
docker cp geoapi:/app/geoapi/swagger.json .
```

Using the swagger definition, the following steps create python client and upload the python client to PyPi
```
git clone --depth 1 https://github.com/swagger-api/swagger-codegen.git client/swagger-codegen
cp client/*.mustache client/swagger-codegen/modules/swagger-codegen/src/main/resources/python/.
# Convert
docker run --rm -v ${PWD}:/local -w=/local swaggerapi/swagger-codegen-cli  generate -i swagger.json -l python -o client/geoapi_client -c client/config.json -t client/swagger-codegen/modules/swagger-codegen/src/main/resources/python/
cd client/geoapi_client
python3 setup.py sdist bdist_wheel
twine check dist/*
python3 -m twine upload dist/*
```
