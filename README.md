# Crossfire Travel Map

A schematic "parchment atlas" of the [Crossfire](https://crossfire.real-time.com/)
world: city locations, the outer coastline of the continent, and the roads, paths,
and sea lanes that connect the destinations. A companion to the
[crossfire-world-map-navigator](https://github.com/tannerrj/crossfire-world-map-navigator)
tile navigator — clicking any city opens that location in the navigator.

![The travel map: parchment-style continent with city markers, roads, and
sea lanes](docs/travel-map.png)

Nothing on the map is hand-drawn. Everything is extracted from the
[Crossfire map sources](https://sourceforge.net/p/crossfire/crossfire-maps/):

- **Coastline** — traced from the land/water boundary of the 1500 × 1500-square
  bigworld (water arches: `sea`, `deep_sea`, `shallow_sea`), simplified, with inland
  lakes dropped and minor islets filtered out.
- **Roads** — the actual road arches on the world maps: paved roads (`cobblestones`,
  `flagstone`), dirt roads and footpaths (`dirtroad_*`, `footpath_*`), and shipping
  lanes (`sea_route`), each drawn in its own style and individually toggleable.
- **Cities** — settlement positions from the `region` designations of the world map
  files, the same method the navigator uses for its landmark list.

## Files

- `travel-map.html` — the page: static hand-written markup, styling, and rendering
  code. Builds the SVG from the data file at load time.
- `travel-map-data.js` — generated data (coastline paths, road polylines, city
  list). Do not edit by hand.
- `tools/generate-travel-map-data.py` — the generator. Python 3 standard library
  only. Rerun it whenever the world maps change:

```sh
tools/generate-travel-map-data.py /path/to/crossfire-maps
```

## Viewing locally

```sh
python3 -m http.server 8895
# open http://localhost:8895/travel-map.html
```

(A server is needed because the page loads `travel-map-data.js`; everything else is
self-contained.)

## License

Licensed under the GNU General Public License, version 2 (see [LICENSE](LICENSE)),
matching the Crossfire project whose map data this work is derived from.
