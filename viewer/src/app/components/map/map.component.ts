import { Component, OnInit } from '@angular/core';
import { ActivatedRoute } from "@angular/router";
import { MatDialog } from "@angular/material";
import * as L  from 'leaflet';
import 'types.leaflet.heat';
import 'leaflet.markercluster';

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
  projectId: number;
  mapType: string = "normal";
  cluster: string;

  constructor(private GeoDataService: GeoDataService,
              private route: ActivatedRoute,
              public dialog: MatDialog) {
    this.featureClickHandler.bind(this);

  }

  ngOnInit() {
    const mapType: string = this.route.snapshot.queryParamMap.get('mapType');
    this.projectId = +this.route.snapshot.paramMap.get("projectId");
    this.cluster = this.route.snapshot.queryParamMap.get('mapType');

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
      let markers = L.markerClusterGroup({
        iconCreateFunction: (cluster)=>{
          return L.divIcon({html:`<div><b>${cluster.getChildCount()}</b></div>`, className:'marker-cluster'})
        }
      });
      collection.features.forEach( d=>{
        let feat = L.geoJSON(d, geojsonOptions);
        feat.on('click', (ev)=>{ this.featureClickHandler(ev)} );

        if (d.geometry.type == "Point") {
          markers.addLayer(feat);
        } else {
          fg.addLayer(feat);
        }
      });
      fg.addLayer(markers);
      this.map.addLayer(fg);
      try {
        this.map.fitBounds(fg.getBounds());
      } catch (e) {
        console.log(e);
      }

    });

  }

  /**
   *
   * @param ev
   */
  featureClickHandler(ev: any): void {
    this.dialog.open(GalleryComponent, {
      data: <Feature>ev.layer.feature,
      maxWidth: '50%',
    })

  }
}
