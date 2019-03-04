import { Injectable } from '@angular/core';

@Injectable({
  providedIn: 'root'
})
export class AuthenticationService {
  jwt: string;

  constructor() { }

  public setUserJWT(userJWT: string): void {
    this.jwt = userJWT;
  }


  public getJWT(): string {
    return this.jwt;
  }
}
