import { Injectable } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import {Observable, of} from "rxjs";
import {map} from "rxjs/operators";

@Injectable({
  providedIn: 'root'
})
export class AuthenticationService {
  jwt: string ='';

  constructor(private http: HttpClient) { }


  public authenticate(): Observable<boolean> {

    if (this.jwt) {
      return of(true);
    }
    return this.http.get("/api/auth/").pipe(
      map(data=>{
        console.log(data);
        this.jwt = data["jwt"];
        return true;
        })
    );
  }

  public getJWT(): string {
    return this.jwt;
  }

}
