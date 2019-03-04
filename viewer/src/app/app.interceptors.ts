import { Injectable } from '@angular/core';
import { HttpRequest, HttpHandler, HttpEvent, HttpInterceptor } from '@angular/common/http';
import { Observable } from 'rxjs';
import { AuthenticationService} from "./services/authentication.service";

// import { AuthenticationService } from '@/_services';

@Injectable()
export class JwtInterceptor implements HttpInterceptor {
    constructor(authSvc: AuthenticationService) {}

    intercept(request: HttpRequest<any>, next: HttpHandler): Observable<HttpEvent<any>> {
        console.log(request.headers);
        // add authorization header with jwt token if available
        // let authToken = "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.eyJpc3MiOiJ3c28yLm9yZy9wcm9kdWN0cy9hbSIsImV4cCI6MjM4NDQ4MTcxMzg0MiwiaHR0cDovL3dzbzIub3JnL2NsYWltcy9zdWJzY3JpYmVyIjoiam1laXJpbmciLCJodHRwOi8vd3NvMi5vcmcvY2xhaW1zL2FwcGxpY2F0aW9uaWQiOiI0NCIsImh0dHA6Ly93c28yLm9yZy9jbGFpbXMvYXBwbGljYXRpb25uYW1lIjoiRGVmYXVsdEFwcGxpY2F0aW9uIiwiaHR0cDovL3dzbzIub3JnL2NsYWltcy9hcHBsaWNhdGlvbnRpZXIiOiJVbmxpbWl0ZWQiLCJodHRwOi8vd3NvMi5vcmcvY2xhaW1zL2FwaWNvbnRleHQiOiIvYXBwcyIsImh0dHA6Ly93c28yLm9yZy9jbGFpbXMvdmVyc2lvbiI6IjIuMCIsImh0dHA6Ly93c28yLm9yZy9jbGFpbXMvdGllciI6IlVubGltaXRlZCIsImh0dHA6Ly93c28yLm9yZy9jbGFpbXMva2V5dHlwZSI6IlBST0RVQ1RJT04iLCJodHRwOi8vd3NvMi5vcmcvY2xhaW1zL3VzZXJ0eXBlIjoiQVBQTElDQVRJT05fVVNFUiIsImh0dHA6Ly93c28yLm9yZy9jbGFpbXMvZW5kdXNlciI6ImptZWlyaW5nIiwiaHR0cDovL3dzbzIub3JnL2NsYWltcy9lbmR1c2VyVGVuYW50SWQiOiIxMCIsImh0dHA6Ly93c28yLm9yZy9jbGFpbXMvZW1haWxhZGRyZXNzIjoidGVzdHVzZXIzQHRlc3QuY29tIiwiaHR0cDovL3dzbzIub3JnL2NsYWltcy9mdWxsbmFtZSI6IkRldiBVc2VyIiwiaHR0cDovL3dzbzIub3JnL2NsYWltcy9naXZlbm5hbWUiOiJEZXYiLCJodHRwOi8vd3NvMi5vcmcvY2xhaW1zL2xhc3RuYW1lIjoiVXNlciIsImh0dHA6Ly93c28yLm9yZy9jbGFpbXMvcHJpbWFyeUNoYWxsZW5nZVF1ZXN0aW9uIjoiTi9BIiwiaHR0cDovL3dzbzIub3JnL2NsYWltcy9yb2xlIjoiSW50ZXJuYWwvZXZlcnlvbmUiLCJodHRwOi8vd3NvMi5vcmcvY2xhaW1zL3RpdGxlIjoiTi9BIn0.Hm9wcptlxJDqGNijo6Qg223h8drbsTz3veVv968Emdw";
        let authToken = AuthenticationService.getJWT();
        request = request.clone({
            setHeaders: {
                'X-JWT-Assertion': authToken
            }
        });

        return next.handle(request);
    }
}

// TODO: Add 403 interceptor
