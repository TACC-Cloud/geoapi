import { Injectable } from '@angular/core';
import {HttpClient} from "@angular/common/http";
import {Observable} from "rxjs";

@Injectable({
  providedIn: 'root'
})
export class ProjectsService {
  constructor(private http: HttpClient) { }

  // TODO: Add types on the observable
  getProjects (): Observable<any> {
    return this.http.get(`/api/projects/`);
  }
}
