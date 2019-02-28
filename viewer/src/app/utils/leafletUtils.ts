import {CircleMarker, circleMarker, icon, LatLng, Marker, marker} from "leaflet";
import {Feature} from "geojson";


export function createCircleMarker (feature: Feature, latlng: LatLng): CircleMarker {
  let options = {
    radius: 8,
    fillColor: "lightgreen",
    color: "black",
    weight: 1,
    opacity: 1,
    fillOpacity: 0.8
  };
  return circleMarker( latlng, options );
}

export function createImageMarker (feature: Feature, latlng: LatLng): Marker {
  let divHtml = `<div> <img src=""></div>`;
  console.log(feature.properties);
  let asset = feature.properties.assets[0]
  let ico = icon({iconUrl: asset.path, iconSize: [25,25]});
  return marker(latlng, {icon: ico});
}


export function createMarker(feature: Feature, latlng: LatLng) {

  if (feature.properties
      && feature.properties.assets
      && feature.properties.assets.length == 1) {
    return createImageMarker(feature, latlng)
  } else {
    return createCircleMarker(feature, latlng)
  }

}
