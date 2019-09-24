# GeoAPI and Viewer

[![Build Status](https://travis-ci.org/TACC-Cloud/geoapi.svg?branch=master)](https://travis-ci.org/TACC-Cloud/geoapi)

## Overview and Architecture

GeoAPI is a restful API to create geospatial features in a PostGIS database. Users create a map "project" then
can add features to it. The development docker-compose file has 3 containers: 
* a PostGIS database exposing 5432, 
* the api which exposes port 8000 behind gunicorn
* an nginx server to serve static files and proxy to the api, running on port 8080. 


## Setup

#### Python side

The API is built with flask and flask-restplus. It is running in its own container
under gunicorn on port 8000

`docker-compose up`

- Initialize the database

`docker exec -it geoapi python initdb.py`

- Create a JWT

Copy this string to here: https://jwt.io/ 

```
eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.eyJpc3MiOiJ3c28yLm9yZy9wcm9kdWN0cy9hbSIsImV4cCI6MjM4NDQ4MTcxMzg0MiwiaHR0cDovL3dzbzIub3JnL2NsYWltcy9zdWJzY3JpYmVyIjoiWU9VUl9VU0VSTkFNRSIsImh0dHA6Ly93c28yLm9yZy9jbGFpbXMvYXBwbGljYXRpb25pZCI6IjQ0IiwiaHR0cDovL3dzbzIub3JnL2NsYWltcy9hcHBsaWNhdGlvbm5hbWUiOiJEZWZhdWx0QXBwbGljYXRpb24iLCJodHRwOi8vd3NvMi5vcmcvY2xhaW1zL2FwcGxpY2F0aW9udGllciI6IlVubGltaXRlZCIsImh0dHA6Ly93c28yLm9yZy9jbGFpbXMvYXBpY29udGV4dCI6Ii9hcHBzIiwiaHR0cDovL3dzbzIub3JnL2NsYWltcy92ZXJzaW9uIjoiMi4wIiwiaHR0cDovL3dzbzIub3JnL2NsYWltcy90aWVyIjoiVW5saW1pdGVkIiwiaHR0cDovL3dzbzIub3JnL2NsYWltcy9rZXl0eXBlIjoiUFJPRFVDVElPTiIsImh0dHA6Ly93c28yLm9yZy9jbGFpbXMvdXNlcnR5cGUiOiJBUFBMSUNBVElPTl9VU0VSIiwiaHR0cDovL3dzbzIub3JnL2NsYWltcy9lbmR1c2VyIjoiWU9VUl9VU0VSTkFNRSIsImh0dHA6Ly93c28yLm9yZy9jbGFpbXMvZW5kdXNlclRlbmFudElkIjoiMTAiLCJodHRwOi8vd3NvMi5vcmcvY2xhaW1zL2VtYWlsYWRkcmVzcyI6InRlc3R1c2VyM0B0ZXN0LmNvbSIsImh0dHA6Ly93c28yLm9yZy9jbGFpbXMvZnVsbG5hbWUiOiJEZXYgVXNlciIsImh0dHA6Ly93c28yLm9yZy9jbGFpbXMvZ2l2ZW5uYW1lIjoiRGV2IiwiaHR0cDovL3dzbzIub3JnL2NsYWltcy9sYXN0bmFtZSI6IlVzZXIiLCJodHRwOi8vd3NvMi5vcmcvY2xhaW1zL3ByaW1hcnlDaGFsbGVuZ2VRdWVzdGlvbiI6Ik4vQSIsImh0dHA6Ly93c28yLm9yZy9jbGFpbXMvcm9sZSI6IkludGVybmFsL2V2ZXJ5b25lIiwiaHR0cDovL3dzbzIub3JnL2NsYWltcy90aXRsZSI6Ik4vQSJ9.0dIfuYvmXJwES1m1NJKKAPclynbGnaxzX3ygSz-3dqA
```

Edit the `YOUR_USERNAME`s in there for your TACC username and copy the modified string

- Make some requests

You need to add the following header for authentication:

`X-JWT-Assertion` to equal the JWT created above

- Create a new map project

send a POST request to `localhost:8000/projects` with a body like this: 

```json
{
  "name": "Awesome Project",
  "description": "Cool project"
}

```

- send a GET request to `localhost:8000/projects` and you should get that back.


#### Client side

The viewer is build with Angular 7 at the moment. In the `viewer` folder:

`npm install`
`ng build --watch`

Go to localhost:8080/projects/1 and you should see a map
