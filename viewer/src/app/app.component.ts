import {Component, OnInit} from '@angular/core';
import { Map } from 'leaflet';
import {GeoDataServiceService} from "./geo-data-service.service";


@Component({
  selector: 'app-root',
  templateUrl: './app.component.html',
  styleUrls: ['./app.component.styl'],
})
export class AppComponent implements OnInit {
  title = 'viewer';
  map: Map;

  constructor(private GeoDataService: GeoDataService) {
    this.GeoDataService = GeoDataService;
  }

  ngOnInit() {
    this.map = new Map('map');
  }
}
