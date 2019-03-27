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
            jwt = "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.eyJpc3MiOiJ3c28yLm9yZy9wcm9kdWN0cy9hbSIsImV4cCI6MjM4NDQ4MTcxMzg0MiwiaHR0cDovL3dzbzIub3JnL2NsYWltcy9zdWJzY3JpYmVyIjoidGVzdCIsImh0dHA6Ly93c28yLm9yZy9jbGFpbXMvYXBwbGljYXRpb25pZCI6IjQ0IiwiaHR0cDovL3dzbzIub3JnL2NsYWltcy9hcHBsaWNhdGlvbm5hbWUiOiJEZWZhdWx0QXBwbGljYXRpb24iLCJodHRwOi8vd3NvMi5vcmcvY2xhaW1zL2FwcGxpY2F0aW9udGllciI6IlVubGltaXRlZCIsImh0dHA6Ly93c28yLm9yZy9jbGFpbXMvYXBpY29udGV4dCI6Ii9nZW9hcGkiLCJodHRwOi8vd3NvMi5vcmcvY2xhaW1zL3ZlcnNpb24iOiIyLjAiLCJodHRwOi8vd3NvMi5vcmcvY2xhaW1zL3RpZXIiOiJVbmxpbWl0ZWQiLCJodHRwOi8vd3NvMi5vcmcvY2xhaW1zL2tleXR5cGUiOiJQUk9EVUNUSU9OIiwiaHR0cDovL3dzbzIub3JnL2NsYWltcy91c2VydHlwZSI6IkFQUExJQ0FUSU9OX1VTRVIiLCJodHRwOi8vd3NvMi5vcmcvY2xhaW1zL2VuZHVzZXIiOiJ0ZXN0IiwiaHR0cDovL3dzbzIub3JnL2NsYWltcy9lbmR1c2VyVGVuYW50SWQiOiIxMCIsImh0dHA6Ly93c28yLm9yZy9jbGFpbXMvZW1haWxhZGRyZXNzIjoidGVzdHVzZXIzQHRlc3QuY29tIiwiaHR0cDovL3dzbzIub3JnL2NsYWltcy9mdWxsbmFtZSI6IkRldiBVc2VyIiwiaHR0cDovL3dzbzIub3JnL2NsYWltcy9naXZlbm5hbWUiOiJEZXYiLCJodHRwOi8vd3NvMi5vcmcvY2xhaW1zL2xhc3RuYW1lIjoiVXNlciIsImh0dHA6Ly93c28yLm9yZy9jbGFpbXMvcHJpbWFyeUNoYWxsZW5nZVF1ZXN0aW9uIjoiTi9BIiwiaHR0cDovL3dzbzIub3JnL2NsYWltcy9yb2xlIjoiSW50ZXJuYWwvZXZlcnlvbmUiLCJodHRwOi8vd3NvMi5vcmcvY2xhaW1zL3RpdGxlIjoiTi9BIn0.B-GRkyQv_l2NPm4lJ-4U0Lu0tcMJmDo6vpTvl_u8MEw";
        else:
            user = request.current_user
            jwt = user.jwt
        return {"jwt": jwt}


