import { TestBed } from '@angular/core/testing';

import { GeoDataServiceService } from './geo-data-service.service';

describe('GeoDataServiceService', () => {
  beforeEach(() => TestBed.configureTestingModule({}));

  it('should be created', () => {
    const service: GeoDataServiceService = TestBed.get(GeoDataServiceService);
    expect(service).toBeTruthy();
  });
});
