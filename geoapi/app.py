
from flask import Flask
from geoapi.routes import api
from geoapi.settings import settings as app_settings
from geoapi.db import db_session


app = Flask(__name__)
api.init_app(app)
app.config.from_object(app_settings)


@app.teardown_appcontext
def shutdown_session(exception=None):
    db_session.remove()