import {Injectable, NgModule} from '@angular/core';
import {Routes, RouterModule, CanActivate, ActivatedRouteSnapshot, RouterStateSnapshot} from '@angular/router';
import { MapComponent } from "./components/map/map.component";
import { NotFoundComponent} from "./components/notfound/notfound.component";
import { ProjectsComponent } from "./components/projects/projects.component";
import {AuthenticationService} from "./services/authentication.service";
import {Observable} from "rxjs";


@Injectable()
class Activate implements CanActivate {
  constructor(private authSvc: AuthenticationService) {}

  canActivate(route: ActivatedRouteSnapshot, state: RouterStateSnapshot): Observable<boolean>  {
    return this.authSvc.authenticate()
  }
}


const routes: Routes = [
  {path: 'projects/:projectId', component: MapComponent,  canActivate: [Activate]},
  {path: 'projects', component: ProjectsComponent, canActivate: [Activate]},
  {path: '404', component: NotFoundComponent },
  {path: '**', redirectTo: 'projects'}
];

@NgModule({
  imports: [RouterModule.forRoot(routes)],
  exports: [RouterModule],
  providers: [Activate]
})
export class AppRoutingModule { }


