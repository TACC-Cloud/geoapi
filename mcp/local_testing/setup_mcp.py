import json
from getpass import getpass
from pathlib import Path

from tapipy.tapis import Tapis

BASE_URL = "https://designsafe.tapis.io"
MCP_URL = "http://localhost:8001/mcp"
OUTPUT_PATH = Path(".mcp.json")

username = input("Tapis username: ")
password = getpass("Tapis password: ")

t = Tapis(base_url=BASE_URL, username=username, password=password)
t.get_tokens()
jwt = t.access_token.access_token

config = {
    "mcpServers": {
        "geoapi": {
            "type": "http",
            "url": MCP_URL,
            "headers": {"X-Tapis-Token": jwt},
        }
    }
}

OUTPUT_PATH.write_text(json.dumps(config, indent=2))
print(f"\nWrote {OUTPUT_PATH.resolve()}")
