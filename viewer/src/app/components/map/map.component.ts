import { Component, OnInit } from '@angular/core';
import * as L  from 'leaflet';
import { GeoDataService} from "../../services/geo-data.service";
import { createMarker} from "../../utils/leafletUtils";
import { clustersKmeans } from "@turf/turf";

import { ActivatedRoute } from "@angular/router";

@Component({
  selector: 'app-map',
  templateUrl: './map.component.html',
  styleUrls: ['./map.component.styl']
})
export class MapComponent implements OnInit {
  map: L.Map;
  features: {};
  projectId: number;

  constructor(private GeoDataService: GeoDataService,
              private route: ActivatedRoute) {
    this.GeoDataService = GeoDataService;
  }

  ngOnInit() {

    const style: string = this.route.snapshot.queryParamMap.get('style');
    this.projectId = +this.route.snapshot.paramMap.get("projectId");


    this.map = new L.Map('map', {
     center: [40, -80],
     zoom: 15
    });

    let baseSatellite = L.tileLayer('https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}');
    let baseOSM = L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
      maxZoom: 19,
      attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
    });
    baseOSM.addTo(this.map);
    this.loadFeatures();

  }

  loadFeatures () {
    let geojsonOptions = {
      pointToLayer: createMarker
    }
    this.GeoDataService.getAllFeatures(this.projectId).subscribe(collection=> {
      let fg = new L.FeatureGroup();
      collection.features.forEach( d=>{
        L.geoJSON(d, geojsonOptions).addTo(fg);
      })
      fg.addTo(this.map);
      this.map.fitBounds(fg.getBounds());

      let points = collection.features.filter( d=> {return d.geometry.type == 'Point'});
      console.log(points);
      let clusters = clustersKmeans(points)
      console.log(clusters)
    })

  }
}
