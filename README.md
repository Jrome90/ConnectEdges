# Connect Edges
This Blender 2.90 Addon is my attempt at implementing similar functionality to Max's Connect Edges tool.

## Features:
* Select and deselect edges while the operator is running (Enable in addon preferences).
  * Selecting and deselecting breaks "adjust last operator" and "repeat last operator" for the operator session it was used.
  * It will be slow with high poly meshes (Has to iterate through all edges to find the selected edges)
* Change number of segments using (CTRL+MouseWheel).
* Adjust the pinch value using (CTRL+Mouse).
* Right clicking anywhere in the 3d view opens a popup to tweak the number of segments and the pinch value.
  * Left click anywhere to close
* Switch between the following using (E):
  * None
  * Even Spacing between the new segments (Calculated using the shortest selected edge).
  * Even spacing between the last vertex and the nearest segment (Calculated using the same method as above).
  
## New Features:
 Version: 0.2.0
 * Left click on a single edge to ring select and connect.
 * Shift Left click to add another edge selection.
 * Left click + CTRL+ALT+SHIFT to add another ring selection.
## Missing Features
* Slide

## Install:
* Download the zip file from github.
* Open Blender.
* Edit -> Preferences -> Click Install button and choose the zip file you downloaded.
* Click the Add-ons button on the left and then activate the addon by ticking the checkbox.

## To use:
 * select the edges you want to connect and then press ALT+C
 * Hit the Enter Key to accept or the ESC Key to cancel.

### Uses Jayanam's "Blender UI Widgets" library which can be found here: https://github.com/jayanam/bl_ui_widgets
