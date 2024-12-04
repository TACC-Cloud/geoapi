""" Signals for the geoapi app """

from blinker import Namespace

geoapi_signals = Namespace()

create_notification = geoapi_signals.signal("create-notification")
