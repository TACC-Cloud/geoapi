import { Injectable } from '@angular/core';
import {HttpClient} from "@angular/common/http";
import {Observable} from "rxjs";
import { FeatureCollection } from "geojson";

@Injectable({
  providedIn: 'root'
})
export class GeoDataService {
  constructor(private http: HttpClient) { }

  // TODO: Add types on the observable
  getAllFeatures (projectId : number): Observable<any> {
    return this.http.get(`/api/projects/${projectId}/features/`);
  }
}
