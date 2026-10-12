# Drawing wall outlines and stable ground (about 15 minutes per pit)

*Plain-language header: if PitGeom is not ready, you draw the walls yourself on a free map website. No software to install.*

1. Open https://geojson.io in your browser. Search the pit by name in the search box (top left of the map). Switch to satellite view with the layer button (bottom left).
2. Click the **polygon** tool (pentagon icon on the right). Click around one wall section, from crest to toe, and click the first point again to close it. Split the pit into walls the way you would for a ground-control plan, usually 4 to 8 sections by facing direction.
3. In the panel on the right, click the new shape's row and add three properties:
   - `wall_id`: a short name, for example `NE` or `W2`
   - `aspect_deg`: the compass direction the face looks toward, 0 to 359 (a wall on the east side of the pit faces west, about 270)
   - `slope_deg`: overall slope angle in degrees, your best estimate
   **Required names for the pilot:** at the Continental Pit, the wall that failed on 1 Nov 2022 must be called `D_East`. At Bald Mountain, the Saga Pit north wall must be called `Saga_N`. Draw the failed wall as you understand its pre-failure extent; the event list refers to these names.
4. Repeat for every wall. Then **Save > GeoJSON**. Rename the file `continental_walls.geojson` (or `baldmountain_walls.geojson`) and send it to me.
5. New map (**New** at top left). Draw one or more polygons around ground you are confident does **not** move: natural ground beyond the rim, away from waste dumps, leach pads, tailings and haul-road fills. Aim for at least 1 km2 in total. Save as `continental_stable.geojson` (or `baldmountain_stable.geojson`).

What it should look like: the walls file shows a ring of shapes around the pit with a label each; the stable file shows a few shapes outside the mine footprint.
