import { Component, OnInit } from '@angular/core';
import { ActivatedRoute } from "@angular/router";
import { MatDialog } from "@angular/material";
import { randomPoint } from "@turf/turf";
import * as L  from 'leaflet';
import 'types.leaflet.heat';

import { GeoDataService} from "../../services/geo-data.service";
import { createMarker } from "../../utils/leafletUtils";
import { GalleryComponent } from "../gallery/gallery.component";
import {Feature} from "geojson";


@Component({
  selector: 'app-map',
  templateUrl: './map.component.html',
  styleUrls: ['./map.component.styl']
})
export class MapComponent implements OnInit {
  map: L.Map;
  features: {};
  projectId: number;
  mapType: string = "normal";

  constructor(private GeoDataService: GeoDataService,
              private route: ActivatedRoute,
              public dialog: MatDialog) {
    this.featureClickHandler.bind(this);

  }

  ngOnInit() {
    const mapType: string = this.route.snapshot.queryParamMap.get('mapType');
    this.projectId = +this.route.snapshot.paramMap.get("projectId");
    console.log(mapType);

    this.map = new L.Map('map', {
     center: [40, -80],
     zoom: 9
    });

    let baseOSM = L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
      maxZoom: 19,
      attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
    });
    baseOSM.addTo(this.map);
    this.loadFeatures();

  }


  /**
   * Load Features for a project.
   */
  loadFeatures () {
    let geojsonOptions = {
      pointToLayer: createMarker
    };
    this.GeoDataService.getAllFeatures(this.projectId).subscribe(collection=> {
      let fg = new L.FeatureGroup();
      collection.features.forEach( d=>{
        let feat = L.geoJSON(d, geojsonOptions);
        feat.on('click', (ev)=>{ this.featureClickHandler(ev)} );
        feat.addTo(fg);
      });
      fg.addTo(this.map);
      this.map.fitBounds(fg.getBounds());

      // let points = collection.features.filter( d=> {return d.geometry.type == 'Point'});
      // let points = randomPoint(100000);
      // let heater = L.heatLayer(points.features.map(p => {return p.geometry.coordinates}), {radius: 10});
      // heater.addTo(this.map);
      // let newfc = {type: "FeatureCollection", features: points};

    });

  }

  /**
   *
   * @param ev
   */
  featureClickHandler(ev: any): void {
    console.log(ev);
    console.log(this.dialog)
    this.dialog.open(GalleryComponent, {
      data: <Feature>ev.layer.feature,
      maxWidth: '50%',
    })

  }
}
