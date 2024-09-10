## Python client

[![PyPI version](https://badge.fury.io/py/geoapi-client.svg)](https://badge.fury.io/py/geoapi-client)

The python package can be found at [PyPi](https://pypi.org/project/geoapi-client/). 

**Note:** This Python client is no longer actively maintained or updated. 

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
