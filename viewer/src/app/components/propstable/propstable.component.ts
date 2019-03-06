import {Component, Input, OnInit} from '@angular/core';

@Component({
  selector: 'app-propstable',
  templateUrl: './propstable.component.html',
  styleUrls: ['./propstable.component.styl']
})
export class PropstableComponent implements OnInit {

  private RESERVED_FIELDS: string[] = ["assets", "styles"];
  @Input() props: object;
  properties: Array<any>;

  constructor() { }

  ngOnInit() {
    this.properties = Object.entries(this.props)
      .map(d=>{return {key: d[0], value:d[1]}})
      .filter(d=>{
        return !this.RESERVED_FIELDS.includes(d.key);
      });
    console.log(this.properties);
  }

}
