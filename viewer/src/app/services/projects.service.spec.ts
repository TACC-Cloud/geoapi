import { TestBed } from '@angular/core/testing';

import { ProjectsService } from './projects.service';
import {HttpClientTestingModule} from "@angular/common/http/testing";

describe('ProjectsService', () => {
  beforeEach(() => TestBed.configureTestingModule({
    imports: [HttpClientTestingModule]
  }));

  it('should be created', () => {
    const service: ProjectsService = TestBed.get(ProjectsService);
    expect(service).toBeTruthy();
  });
});
