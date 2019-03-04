import { Component, OnInit } from '@angular/core';
import { ProjectsService} from "../../services/projects.service";
import {Project} from "../../models/models";

@Component({
  selector: 'app-projects',
  templateUrl: './projects.component.html',
  styleUrls: ['./projects.component.styl']
})
export class ProjectsComponent implements OnInit {

  projects: Project[];

  constructor(private service: ProjectsService) { }

  ngOnInit() {
    this.service.getProjects().subscribe( (projects)=>{
      this.projects = projects;
    })
  }

}
