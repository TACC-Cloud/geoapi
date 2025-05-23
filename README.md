# GeoAPI

## Overview and Architecture

GeoAPI is a restful API to create geospatial features in a PostGIS database. Users create a map "project" then
can add features to it. The development docker-compose file has 3 containers:
* a PostGIS database exposing 5432,
* the api which exposes port 8000 behind gunicorn
* a nginx server to serve static files and proxy to the api, running on port 8080.

See https://github.com/TACC-Cloud/hazmapper which is an associated viewer application.

## Setup

#### Configure .env file

Environment variables are used to define the tenant's service accounts which are needed to access metadata and some user
information. An .env file for developers can be found on [UT Stache](https://stache.utexas.edu/entry/892c730561534ed3b3d306dbf933455d).

#### Python side

The API is built with flask and flask-restplus. It is running in its own container
under gunicorn on port 8000

`make build-dev`
`make start`

###### Initialize the database (for local development and unit testing)

`docker exec -it geoapi python initdb.py`

### Example requests

You need a Tapis token for the appropriate tenant.

```bash
export JWT=your_access_token_string
```

To create a new "map" project, send a POST request:

```
curl -X POST -H "Content-Type: application/json" -H "X-Tapis-Token: $JWT" http://localhost:8000/projects/ -d '{"name": "Test Project", "description": "This is a test project."}'
```

To view all projects, including the newly created one, send a GET request:

```
curl -v -H "Content-Type: application/json" -H "X-Tapis-Token: $JWT" http://localhost:8000/projects/
```


### Client viewer

See https://github.com/TACC-Cloud/hazmapper for details.

### Creating migrations when updating database models

These are useful steps to follow when there are changes to the database model.

First, apply migrations:

```
docker exec -it geoapi alembic upgrade head
```

**Note:** The above step is also automatically performed when running `initdb.py`

Then, create migrations:

```
docker exec -it geoapi /bin/bash
# determine a description for the migration like 'add_user_email_column'
alembic revision --autogenerate -m "add_user_email_column"
# Then:
# - check to make sure no postgis table commands (we try to ommit them in env.py)
# - add/commit migrations
```

Then, you will need to manually apply the new migration after creating it:
```
docker exec -it geoapi alembic upgrade head
```

## Testing

Run directly in your running containers:
```
# then run tests in api
docker exec -it geoapi bash
APP_ENV=testing pytest

# then run tests in worker
docker exec -it geoapiworkers bash
APP_ENV=testing pytest -m "worker"
```
## Production/Staging

Information on  configuration for production and staging environments can be found in the [devops/README.md](devops/README.md) including information
on Jenkins deployment workflows.


## Python client

The python package can be found at [PyPi](https://pypi.org/project/geoapi-client/).  More details can be found in [Python Client](./PYTHON_CLIENT.md)
