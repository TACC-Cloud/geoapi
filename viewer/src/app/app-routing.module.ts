import { NgModule } from '@angular/core';
import { Routes, RouterModule } from '@angular/router';
import { MapComponent } from "./components/map/map.component";
import { NotFoundComponent} from "./components/notfound/notfound.component";
import { ProjectsComponent } from "./components/projects/projects.component";

const routes: Routes = [
  {path: 'projects/:projectId', component: MapComponent},
  {path: 'projects', component: ProjectsComponent},
  {path: '404', component: NotFoundComponent },
  {path: '**', redirectTo: '/404'}
];

@NgModule({
  imports: [RouterModule.forRoot(routes)],
  exports: [RouterModule]
})
export class AppRoutingModule { }
