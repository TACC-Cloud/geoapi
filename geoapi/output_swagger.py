from geoapi.app import api, app
from flask import json
import argparse

def write_openapi_definition(filename):
    with app.test_request_context():
        with open(filename, 'w') as f:
           f.write(json.dumps(api.__schema__))

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Output swagger file")
    parser.add_argument("swagger_file", help="Output file ")
    args = parser.parse_args()
    write_openapi_definition(filename=args.swagger_file)
