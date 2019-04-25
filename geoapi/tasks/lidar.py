from geoapi.celery_app import app
from agavepy.agave import Agave


@app.task()
def import_from_agave():
    client = Agave(api_server="https://agave.designsafe-ci.org", token="3df38c7b3f58461ef8fa3c238a344291")
    files = client.files.list(systemId="designsafe.storage.default")
    print(files)


if __name__== "__main__":
    import_from_agave()