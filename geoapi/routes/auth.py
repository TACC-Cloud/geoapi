from flask import request
from flask_restplus import Resource, Namespace

from geoapi.settings import settings

api = Namespace('auth')

@api.route('/')
class AuthenticationResource(Resource):

    @api.doc(description="Get the current user's JWT")
    def get(self):

        # For development purposes, this will be a JWT for a user with username=test
        if settings.DEBUG:
            jwt = "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.eyJpc3MiOiJ3c28yLm9yZy9wcm9kdWN0cy9hbSIsImV4cCI6MjM4NDQ4MTcxMzg0MiwiaHR0cDovL3dzbzIub3JnL2NsYWltcy9zdWJzY3JpYmVyIjoiam1laXJpbmciLCJodHRwOi8vd3NvMi5vcmcvY2xhaW1zL2FwcGxpY2F0aW9uaWQiOiI0NCIsImh0dHA6Ly93c28yLm9yZy9jbGFpbXMvYXBwbGljYXRpb25uYW1lIjoiRGVmYXVsdEFwcGxpY2F0aW9uIiwiaHR0cDovL3dzbzIub3JnL2NsYWltcy9hcHBsaWNhdGlvbnRpZXIiOiJVbmxpbWl0ZWQiLCJodHRwOi8vd3NvMi5vcmcvY2xhaW1zL2FwaWNvbnRleHQiOiIvZ2VvYXBpIiwiaHR0cDovL3dzbzIub3JnL2NsYWltcy92ZXJzaW9uIjoiMi4wIiwiaHR0cDovL3dzbzIub3JnL2NsYWltcy90aWVyIjoiVW5saW1pdGVkIiwiaHR0cDovL3dzbzIub3JnL2NsYWltcy9rZXl0eXBlIjoiUFJPRFVDVElPTiIsImh0dHA6Ly93c28yLm9yZy9jbGFpbXMvdXNlcnR5cGUiOiJBUFBMSUNBVElPTl9VU0VSIiwiaHR0cDovL3dzbzIub3JnL2NsYWltcy9lbmR1c2VyIjoiam1laXJpbmciLCJodHRwOi8vd3NvMi5vcmcvY2xhaW1zL2VuZHVzZXJUZW5hbnRJZCI6IjEwIiwiaHR0cDovL3dzbzIub3JnL2NsYWltcy9lbWFpbGFkZHJlc3MiOiJ0ZXN0dXNlcjNAdGVzdC5jb20iLCJodHRwOi8vd3NvMi5vcmcvY2xhaW1zL2Z1bGxuYW1lIjoiRGV2IFVzZXIiLCJodHRwOi8vd3NvMi5vcmcvY2xhaW1zL2dpdmVubmFtZSI6IkRldiIsImh0dHA6Ly93c28yLm9yZy9jbGFpbXMvbGFzdG5hbWUiOiJVc2VyIiwiaHR0cDovL3dzbzIub3JnL2NsYWltcy9wcmltYXJ5Q2hhbGxlbmdlUXVlc3Rpb24iOiJOL0EiLCJodHRwOi8vd3NvMi5vcmcvY2xhaW1zL3JvbGUiOiJJbnRlcm5hbC9ldmVyeW9uZSIsImh0dHA6Ly93c28yLm9yZy9jbGFpbXMvdGl0bGUiOiJOL0EifQ.HYx3yTWZi1aVZzlyzzYPsX027NxBDsyMTRGkh1jpe2Y"
        else:
            user = request.current_user
            jwt = user.jwt
        return {"jwt": jwt}


