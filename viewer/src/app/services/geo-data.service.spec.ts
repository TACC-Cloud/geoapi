import { TestBed } from '@angular/core/testing';

import { GeoDataService } from './geo-data.service';

describe('GeoDataService', () => {
  beforeEach(() => TestBed.configureTestingModule({}));

  it('should be created', () => {
    const service: GeoDataService = TestBed.get(GeoDataService);
    expect(service).toBeTruthy();
  });
});
