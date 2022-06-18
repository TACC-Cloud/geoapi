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

#### Python side

The API is built with flask and flask-restplus. It is running in its own container
under gunicorn on port 8000

`docker-compose up`

###### Run locally with service accounts

For some access to metadata and user information, a service account is required:
`TENANT="{\"DESIGNSAFE\": {\"service_account_token\": \"ABCDEFG12344\"}}" docker-compose up`

###### Initialize the database

`docker exec -it geoapi python initdb.py`

###### Create a JWT

Copy this string to here: https://jwt.io/ 

```
eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.eyJpc3MiOiJ3c28yLm9yZy9wcm9kdWN0cy9hbSIsImV4cCI6MjM4NDQ4MTcxMzg0MiwiaHR0cDovL3dzbzIub3JnL2NsYWltcy9zdWJzY3JpYmVyIjoiWU9VUl9VU0VSTkFNRSIsImh0dHA6Ly93c28yLm9yZy9jbGFpbXMvYXBwbGljYXRpb25pZCI6IjQ0IiwiaHR0cDovL3dzbzIub3JnL2NsYWltcy9hcHBsaWNhdGlvbm5hbWUiOiJEZWZhdWx0QXBwbGljYXRpb24iLCJodHRwOi8vd3NvMi5vcmcvY2xhaW1zL2FwcGxpY2F0aW9udGllciI6IlVubGltaXRlZCIsImh0dHA6Ly93c28yLm9yZy9jbGFpbXMvYXBpY29udGV4dCI6Ii9hcHBzIiwiaHR0cDovL3dzbzIub3JnL2NsYWltcy92ZXJzaW9uIjoiMi4wIiwiaHR0cDovL3dzbzIub3JnL2NsYWltcy90aWVyIjoiVW5saW1pdGVkIiwiaHR0cDovL3dzbzIub3JnL2NsYWltcy9rZXl0eXBlIjoiUFJPRFVDVElPTiIsImh0dHA6Ly93c28yLm9yZy9jbGFpbXMvdXNlcnR5cGUiOiJBUFBMSUNBVElPTl9VU0VSIiwiaHR0cDovL3dzbzIub3JnL2NsYWltcy9lbmR1c2VyIjoiWU9VUl9VU0VSTkFNRSIsImh0dHA6Ly93c28yLm9yZy9jbGFpbXMvZW5kdXNlclRlbmFudElkIjoiMTAiLCJodHRwOi8vd3NvMi5vcmcvY2xhaW1zL2VtYWlsYWRkcmVzcyI6InRlc3R1c2VyM0B0ZXN0LmNvbSIsImh0dHA6Ly93c28yLm9yZy9jbGFpbXMvZnVsbG5hbWUiOiJEZXYgVXNlciIsImh0dHA6Ly93c28yLm9yZy9jbGFpbXMvZ2l2ZW5uYW1lIjoiRGV2IiwiaHR0cDovL3dzbzIub3JnL2NsYWltcy9sYXN0bmFtZSI6IlVzZXIiLCJodHRwOi8vd3NvMi5vcmcvY2xhaW1zL3ByaW1hcnlDaGFsbGVuZ2VRdWVzdGlvbiI6Ik4vQSIsImh0dHA6Ly93c28yLm9yZy9jbGFpbXMvcm9sZSI6IkludGVybmFsL2V2ZXJ5b25lIiwiaHR0cDovL3dzbzIub3JnL2NsYWltcy90aXRsZSI6Ik4vQSJ9.0dIfuYvmXJwES1m1NJKKAPclynbGnaxzX3ygSz-3dqA
```

Edit the `YOUR_USERNAME`s in there for your TACC username and copy the modified string

###### Make some requests

You need to add the following header for authentication:

`X-JWT-Assertion` to equal the JWT created above

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

### Migrations


Applying migrations

```
docker exec -it geoapi alembic upgrade head
```

Creating migrations

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
docker-compose -f docker-compose.test.yml -p geoapi_test run api pytest
```

Run worker-related tasks on the `workers` container
```
docker-compose -f docker-compose.test.yml -p geoapi_test run workers pytest -m "worker"
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
