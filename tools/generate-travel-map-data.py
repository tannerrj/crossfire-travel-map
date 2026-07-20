#!/usr/bin/env python3
"""Generate travel-map-data.js from a crossfire-maps checkout.

Parses the 900 bigworld map files (world/world_100_100 .. world_129_129,
each 50x50 squares) and extracts, on the 1500x1500 world-square grid:

  * the continent coastline and major island outlines, traced from the
    land/water boundary and simplified (inland lakes are dropped -- the
    map shows the outer perimeter only);
  * the road network, split into paved roads (cobblestones, flagstone),
    minor ways (dirt roads, footpaths), and sea routes;
  * city positions, derived from the region designations of the map files
    (same method as the navigator's landmark extractor), restricted to
    settlements.

The result is written as a JavaScript data file consumed by
travel-map.html. Uses only the Python standard library.

Usage:
    tools/generate-travel-map-data.py /path/to/crossfire-maps [out.js]
"""

import sys
import time
from pathlib import Path

TMIN, TMAX, TILE = 100, 129, 50
SIZE = (TMAX - TMIN + 1) * TILE          # 1500 squares per side

WATER = {"sea", "sea1", "deep_sea", "shallow_sea"}
PAVED = {"cobblestones", "cobblestones2", "flagstone"}
MINOR_PREFIX = ("dirtroad", "footpath")
SEA_ROUTE = {"sea_route"}

# Settlement regions shown as cities: region code -> display name.
SETTLEMENTS = {
    "scorn": "Scorn",
    "navar": "Navar",
    "brest": "Brest",
    "santodominion": "Santo Dominion",
    "darcap": "Darcap",
    "portjoseph": "Port Joseph",
    "wolfsburg": "Wolfsburg",
    "azumauindo": "Azumauindo",
    "stoneville": "Stoneville",
    "marksel": "Marksel",
    "euthville": "Euthville",
    "narcopin": "Narcopin",
    "lakecountry": "Lake Country",
    "whalingoutpost": "Whaling Outpost",
}

MIN_ISLAND_AREA = 30      # squares; smaller islets are dropped
SIMPLIFY_EPS = 1.6        # Douglas-Peucker tolerance, in squares


def parse_tile(path, base_x, base_y, water, roads, region_tiles):
    """Scan one 50x50 world map file for water, road, and region data."""
    depth = 0
    in_msg = False
    name = None
    ax = ay = 0
    tile_region = None
    for raw in open(path, encoding="utf-8", errors="replace"):
        line = raw.strip()
        if in_msg:
            if line == "endmsg":
                in_msg = False
            continue
        if line == "msg":
            in_msg = True
        elif line.startswith("arch "):
            depth += 1
            if depth == 1:
                name = line[5:]
                ax = ay = 0
        elif line == "end":
            if depth == 1 and name != "map":
                gx, gy = base_x + ax, base_y + ay
                if name in WATER:
                    water[gy * SIZE + gx] = 1
                elif name in PAVED:
                    roads["paved"].add((gx, gy))
                elif name.startswith(MINOR_PREFIX):
                    roads["minor"].add((gx, gy))
                elif name in SEA_ROUTE:
                    roads["sea"].add((gx, gy))
            if depth > 0:
                depth -= 1
        elif depth == 1:
            if line.startswith("x "):
                ax = int(line[2:])
            elif line.startswith("y "):
                ay = int(line[2:])
            elif (name == "map" and tile_region is None
                  and line.startswith("region ")):
                r = line[7:]
                if r != "world":
                    tile_region = r
                    region_tiles.setdefault(r, []).append(
                        (base_x // TILE + TMIN, base_y // TILE + TMIN))


# ---------------------------------------------------------------------------
# Coastline tracing


def trace_coastline(water):
    """Return simplified outer land boundaries (continent + islands).

    Builds directed unit edges along every land/water boundary with land on
    the left, chains them into closed loops, keeps counter-clockwise loops
    (outer boundaries; clockwise loops are lakes), and simplifies them.
    """
    def is_land(x, y):
        return 0 <= x < SIZE and 0 <= y < SIZE and not water[y * SIZE + x]

    # Directed edges vertex->vertex, oriented with land on the left.
    nxt = {}
    for y in range(SIZE):
        row = y * SIZE
        for x in range(SIZE):
            if water[row + x]:
                continue
            if not is_land(x, y - 1):
                nxt.setdefault((x, y), []).append((x + 1, y))        # north side, eastward
            if not is_land(x, y + 1):
                nxt.setdefault((x + 1, y + 1), []).append((x, y + 1))  # south side, westward
            if not is_land(x - 1, y):
                nxt.setdefault((x, y + 1), []).append((x, y))        # west side, northward
            if not is_land(x + 1, y):
                nxt.setdefault((x + 1, y), []).append((x + 1, y + 1))  # east side, southward
    loops = []
    while nxt:
        start = next(iter(nxt))
        loop = [start]
        v = start
        prev = None
        while True:
            outs = nxt.get(v)
            if not outs:
                break
            if len(outs) == 1:
                w = outs.pop()
                del nxt[v]
            else:
                # Crossing point: prefer the left-most turn to keep loops tight.
                dx, dy = v[0] - prev[0], v[1] - prev[1]
                left = (v[0] + dy, v[1] - dx)
                w = left if left in outs else outs[0]
                outs.remove(w)
                if not outs:
                    del nxt[v]
            if w == start:
                break
            loop.append(w)
            prev, v = v, w
        if len(loop) >= 8:
            loops.append(loop)
    return loops


def signed_area(pts):
    a = 0
    for i in range(len(pts)):
        x1, y1 = pts[i]
        x2, y2 = pts[(i + 1) % len(pts)]
        a += x1 * y2 - x2 * y1
    return a / 2.0


def simplify(pts, eps):
    """Iterative Douglas-Peucker on a closed ring (treated as open path)."""
    if len(pts) < 3:
        return pts
    keep = [False] * len(pts)
    keep[0] = keep[-1] = True
    stack = [(0, len(pts) - 1)]
    while stack:
        i, j = stack.pop()
        ax, ay = pts[i]
        bx, by = pts[j]
        dx, dy = bx - ax, by - ay
        norm = (dx * dx + dy * dy) ** 0.5 or 1e-9
        worst, wd = -1, eps
        for k in range(i + 1, j):
            px, py = pts[k]
            d = abs(dx * (ay - py) - dy * (ax - px)) / norm
            if d >= wd:
                worst, wd = k, d
        if worst >= 0:
            keep[worst] = True
            stack.append((i, worst))
            stack.append((worst, j))
    return [p for p, k in zip(pts, keep) if k]


# ---------------------------------------------------------------------------
# Road chaining


DIRS = ((1, 0), (0, 1), (1, 1), (1, -1))


def road_paths(cells):
    """Compress a cell set into maximal straight segments plus lone dots."""
    segs = []
    linked = set()
    for dx, dy in DIRS:
        for (x, y) in cells:
            if (x - dx, y - dy) in cells:
                continue                     # not the start of a run
            ex, ey = x, y
            while (ex + dx, ey + dy) in cells:
                ex, ey = ex + dx, ey + dy
            if (ex, ey) != (x, y):
                segs.append((x, y, ex, ey))
                px, py = x, y
                while True:
                    linked.add((px, py))
                    if (px, py) == (ex, ey):
                        break
                    px, py = px + dx, py + dy
    dots = sorted(cells - linked)
    return segs, dots


def seg_path(segs):
    return " ".join("M%g %gL%g %g" % (x1 + .5, y1 + .5, x2 + .5, y2 + .5)
                    for x1, y1, x2, y2 in segs)


# ---------------------------------------------------------------------------


def main(argv):
    if len(argv) < 2 or len(argv) > 3:
        sys.exit("usage: %s /path/to/crossfire-maps [out.js]" % argv[0])
    maps = Path(argv[1])
    out = Path(argv[2]) if len(argv) > 2 else \
        Path(__file__).resolve().parent.parent / "travel-map-data.js"
    if not (maps / "world").is_dir():
        sys.exit("error: %s/world not found" % maps)

    water = bytearray(SIZE * SIZE)
    roads = {"paved": set(), "minor": set(), "sea": set()}
    region_tiles = {}

    t0 = time.time()
    for ty in range(TMIN, TMAX + 1):
        for tx in range(TMIN, TMAX + 1):
            parse_tile(maps / "world" / ("world_%d_%d" % (tx, ty)),
                       (tx - TMIN) * TILE, (ty - TMIN) * TILE,
                       water, roads, region_tiles)
        print("parsed row %d" % ty, file=sys.stderr)

    loops = trace_coastline(water)
    outer = []
    for loop in loops:
        area = signed_area(loop)
        if area > MIN_ISLAND_AREA:           # CCW in y-down coords = outer
            outer.append((area, simplify(loop, SIMPLIFY_EPS)))
    outer.sort(reverse=True)
    coast = ["M" + " ".join("%g %g" % p for p in ring) + "Z"
             for _, ring in outer]

    # Streets mark the settlement itself, so prefer the region tile with the
    # most paved squares; fall back to the tile nearest the region centroid
    # for street-less regions. (Matters for scattered regions like the
    # Whaling Outpost, whose centroid tile is empty ocean coast.)
    paved_per_tile = {}
    for (x, y) in roads["paved"]:
        t = (x // TILE + TMIN, y // TILE + TMIN)
        paved_per_tile[t] = paved_per_tile.get(t, 0) + 1

    cities = []
    for code, name in sorted(SETTLEMENTS.items(), key=lambda kv: kv[1]):
        tiles = region_tiles.get(code)
        if not tiles:
            print("warning: no tiles found for region %s" % code,
                  file=sys.stderr)
            continue
        cx = sum(t[0] for t in tiles) / len(tiles)
        cy = sum(t[1] for t in tiles) / len(tiles)
        best = max(tiles, key=lambda t: (paved_per_tile.get(t, 0),
                                         -((t[0] - cx) ** 2 + (t[1] - cy) ** 2)))
        cities.append({"name": name,
                       "x": (best[0] - TMIN) * TILE + TILE // 2,
                       "y": (best[1] - TMIN) * TILE + TILE // 2,
                       "tx": best[0], "ty": best[1]})

    with open(out, "w") as f:
        f.write("// Generated by tools/generate-travel-map-data.py"
                " -- do not edit by hand.\n")
        f.write("const TRAVEL_MAP = {\n")
        f.write("  size: %d,\n" % SIZE)
        f.write("  coast: [\n")
        for p in coast:
            f.write('    "%s",\n' % p)
        f.write("  ],\n  roads: {\n")
        for key in ("paved", "minor", "sea"):
            segs, dots = road_paths(roads[key])
            f.write('    %s: { path: "%s",\n' % (key, seg_path(segs)))
            f.write("      dots: %s },\n"
                    % [[x, y] for x, y in dots])
        f.write("  },\n  cities: [\n")
        for c in cities:
            f.write("    { name: %r, x: %d, y: %d, tx: %d, ty: %d },\n"
                    % (c["name"], c["x"], c["y"], c["tx"], c["ty"]))
        f.write("  ]\n};\n")

    print("wrote %s in %.1fs: %d coastline rings, "
          "%d/%d/%d road cells (paved/minor/sea), %d cities"
          % (out, time.time() - t0, len(coast),
             len(roads["paved"]), len(roads["minor"]), len(roads["sea"]),
             len(cities)), file=sys.stderr)


if __name__ == "__main__":
    main(sys.argv)
