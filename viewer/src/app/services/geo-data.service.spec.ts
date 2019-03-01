import { TestBed } from '@angular/core/testing';

import { GeoDataService } from './geo-data.service';
import {HttpClientTestingModule} from "@angular/common/http/testing";

describe('GeoDataService', () => {
  beforeEach(() => TestBed.configureTestingModule({imports:[
    HttpClientTestingModule
    ]}));

  it('should be created', () => {
    const service: GeoDataService = TestBed.get(GeoDataService);
    expect(service).toBeTruthy();
  });
});
