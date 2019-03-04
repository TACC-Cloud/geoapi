import { Component, Inject } from '@angular/core';
import { MatDialogRef, MAT_DIALOG_DATA } from '@angular/material';
import {Feature} from "geojson";


@Component({
  selector: 'app-gallery',
  templateUrl: './gallery.component.html',
  styleUrls: ['./gallery.component.styl']
})
export class GalleryComponent {

  constructor(
    public dialogRef: MatDialogRef<GalleryComponent>,
    @Inject(MAT_DIALOG_DATA) public data: Feature) {}

  onClose(): void {
    this.dialogRef.close();
  }

}
