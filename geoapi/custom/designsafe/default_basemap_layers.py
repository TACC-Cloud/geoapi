default_layers = [
  {
    "name": "Roads",
    "type": "tms",
    "url": "https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png",
    "attribution": "© OpenStreetMap contributors",
    "uiOptions": {
      "opacity": 1,
      "isActive": True,
      "showDescription": False,
      "showInput": False,
      "zIndex": 0
    },
    "tileOptions": {
      "minZoom": 0,
      "maxZoom": 24,
      "maxNativeZoom": 19,
    },
  },
  {
    "name": "Satellite",
    "type": "tms",
    "url": "https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}",
    "attribution":
      "Tiles © Esri — Source: Esri, i-cubed, USDA, USGS, AEX, \
    GeoEye, Getmapping, Aerogrid, IGN, IGP, UPR-EGP, and the GIS User Community",
    "uiOptions": {
      "opacity": 1,
      "isActive": True,
      "showDescription": False,
      "showInput": False,
      "zIndex": -1
    },
    "tileOptions": {
      "minZoom": 0,
      "maxZoom": 24,
      "maxNativeZoom": 19,
    },
  },
]