import { async, ComponentFixture, TestBed } from '@angular/core/testing';

import { PropstableComponent } from './propstable.component';

describe('PropstableComponent', () => {
  let component: PropstableComponent;
  let fixture: ComponentFixture<PropstableComponent>;

  beforeEach(async(() => {
    TestBed.configureTestingModule({
      declarations: [ PropstableComponent ]
    })
    .compileComponents();
  }));

  beforeEach(() => {
    fixture = TestBed.createComponent(PropstableComponent);
    component = fixture.componentInstance;
    fixture.detectChanges();
  });

  it('should create', () => {
    expect(component).toBeTruthy();
  });
});
