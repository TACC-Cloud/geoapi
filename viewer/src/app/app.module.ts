import { BrowserModule } from '@angular/platform-browser';
import { NgModule } from '@angular/core';
import { BrowserAnimationsModule } from '@angular/platform-browser/animations';
import { HttpClientModule, HTTP_INTERCEPTORS } from '@angular/common/http';
import { AppRoutingModule } from './app-routing.module';
import { AppComponent } from "./app.component";
import { MapComponent} from "./components/map/map.component";
import { JwtInterceptor } from "./app.interceptors";
import { NotFoundComponent } from './components/notfound/notfound.component';
import { ProjectsComponent } from './components/projects/projects.component';
import { GalleryComponent } from './components/gallery/gallery.component';
import { MaterialModule } from './material.module';
import { PropstableComponent } from './components/propstable/propstable.component';

@NgModule({
  declarations: [
    AppComponent, MapComponent, NotFoundComponent, ProjectsComponent, GalleryComponent, PropstableComponent
  ],
  imports: [
    BrowserModule,
    AppRoutingModule,
    HttpClientModule,
    BrowserAnimationsModule,
    MaterialModule,
  ],
  providers: [
    { provide: HTTP_INTERCEPTORS, useClass: JwtInterceptor, multi: true },
  ],
  bootstrap: [AppComponent],
  entryComponents: [GalleryComponent]
})
export class AppModule { }

