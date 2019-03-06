import { Injectable } from '@angular/core';
import { HttpRequest, HttpHandler, HttpEvent, HttpInterceptor } from '@angular/common/http';
import { Observable } from 'rxjs';
import { AuthenticationService} from "./services/authentication.service";

@Injectable()
export class JwtInterceptor implements HttpInterceptor {
  constructor(private authSvc: AuthenticationService) {}

  intercept(request: HttpRequest<any>, next: HttpHandler): Observable<HttpEvent<any>> {
    // add authorization header with jwt token if available
    let authToken = this.authSvc.getJWT();
    request = request.clone({
        setHeaders: {
            'X-JWT-Assertion': authToken
        }
    });

    return next.handle(request);
  }
}

// TODO: Add 403 interceptor
