"""Build the web map's data: trees.json, terrain.bin and context.json.

Downloads are cached in data/ (gitignored), so re-runs do not hit the servers again.
"""

import json
import math
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

import numpy as np
import pandas as pd
from contourpy import contour_generator
from PIL import Image

ROOT = Path(__file__).parent
DATA_DIR = ROOT / "data"
SOURCE_CSV = DATA_DIR / "arbrat_viari.csv"
TILE_DIR = DATA_DIR / "tiles"
OSM_DIR = DATA_DIR / "osm"
TREES_JSON = ROOT / "trees.json"
TERRAIN_BIN = ROOT / "terrain.bin"
CONTEXT_JSON = ROOT / "context.json"

USER_AGENT = "barcelona-plantings-data-prep"
REQUEST_PAUSE_S = 2.0
RETRY_ATTEMPTS = 5
RETRY_PAUSE_S = 20
RETRY_STATUS = {429, 502, 503, 504}

EPOCH = pd.Timestamp("2007-01-01")
UNDATED = -1
COORD_DECIMALS = 5
# Rough Barcelona bounds, to drop bad coordinates.
LAT_RANGE = (41.30, 41.47)
LON_RANGE = (2.05, 2.24)

TILE_URL = "https://s3.amazonaws.com/elevation-tiles-prod/terrarium/{z}/{x}/{y}.png"
TILE_ZOOM = 13
TILE_SIZE = 256
TERRAIN_LON = (2.02, 2.27)
TERRAIN_LAT = (41.29, 41.49)
GRID_STEP_M = 50
METERS_PER_DEGREE = 111_320
CONTOUR_STEP_M = 50
INDEX_CONTOUR_M = 200
SHORE_LEVEL_M = 0.5
MIN_LINE_POINTS = 8
CONTOUR_SMOOTH_PASSES = 2

OVERPASS_URL = "https://overpass-api.de/api/interpreter"

# Each place is matched by name near a known point, so neighbouring buildings stay out.
# fallback is used when OSM has no usable footprint or height.
LANDMARKS = [
    {
        "id": "sagrada",
        "label": "Sagrada Família",
        "lat": 41.4036,
        "lon": 2.1744,
        "radius": 110,
        "name": "Sagrada|Temple Expiatori",
        "height": 172,
        "parts": True,
        "primary": True,
    },
    {
        "id": "glories",
        "label": "Torre Glòries",
        "lat": 41.4034,
        "lon": 2.1895,
        "radius": 80,
        "name": "Gl[oò]ries|Agbar",
        "height": 144,
        "primary": True,
    },
    {
        "id": "arts",
        "label": "Hotel Arts",
        "lat": 41.3868,
        "lon": 2.1962,
        "radius": 90,
        "name": "Hotel Arts|Arts Barcelona",
        "height": 154,
    },
    {
        "id": "mapfre",
        "label": "Torre Mapfre",
        "lat": 41.3881,
        "lon": 2.1975,
        "radius": 90,
        "name": "Mapfre",
        "height": 154,
    },
    {
        "id": "w",
        "label": "Hotel W",
        "lat": 41.3685,
        "lon": 2.1900,
        "radius": 110,
        "name": "W Barcelona|Hotel W|Vela",
        "height": 99,
    },
    {
        "id": "tibidabo",
        "label": "Tibidabo",
        "lat": 41.4221,
        "lon": 2.1186,
        "radius": 90,
        "name": "Sagrat Cor|Sagrado Coraz",
        "height": 40,
        "primary": True,
    },
    {
        "id": "collserola",
        "label": "Torre de Collserola",
        "lat": 41.4173,
        "lon": 2.1142,
        "radius": 60,
        "name": "Collserola",
        "height": 288,
        "fallback_radius": 10,
    },
    {
        "id": "montjuic",
        "label": "Castell de Montjuïc",
        "lat": 41.3636,
        "lon": 2.1661,
        "radius": 170,
        "name": "Castell de Montju",
        "height": 18,
        "primary": True,
    },
    {
        "id": "mnac",
        "label": "MNAC",
        "lat": 41.3686,
        "lon": 2.1533,
        "radius": 130,
        "name": "Palau Nacional|Museu Nacional",
        "height": 45,
    },
    {
        "id": "campnou",
        "label": "Camp Nou",
        "lat": 41.3809,
        "lon": 2.1228,
        "radius": 190,
        "name": "Camp Nou",
        "height": 48,
        "primary": True,
    },
    {
        "id": "colom",
        "label": "Monument a Colom",
        "lat": 41.3758,
        "lon": 2.1778,
        "radius": 40,
        "name": "Colom|Colón",
        "height": 60,
        "fallback_radius": 6,
    },
]
# Places with no building of their own: a label on the ground only.
GROUND_LABELS = [
    {
        "id": "barceloneta",
        "label": "Barceloneta",
        "lat": 41.3785,
        "lon": 2.1925,
        "primary": True,
    },
]
FALLBACK_CIRCLE_POINTS = 12
FLOOR_HEIGHT_M = 3.2


def fetch(url: str, cache_path: Path, data: bytes | None = None) -> bytes:
    """Return a cached download, fetching it once if it is missing."""
    if cache_path.exists():
        return cache_path.read_bytes()
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    request = urllib.request.Request(url, data=data, headers={"User-Agent": USER_AGENT})
    for attempt in range(RETRY_ATTEMPTS):
        try:
            with urllib.request.urlopen(request, timeout=120) as response:
                body = response.read()
            break
        except urllib.error.HTTPError as error:
            if error.code not in RETRY_STATUS or attempt == RETRY_ATTEMPTS - 1:
                raise
            time.sleep(RETRY_PAUSE_S * (attempt + 1))
    cache_path.write_bytes(body)
    time.sleep(REQUEST_PAUSE_S if data else 0.05)
    return body


def tile_x(lon: float) -> float:
    return (lon + 180) / 360 * 2**TILE_ZOOM


def tile_y(lat: float) -> float:
    radians = math.radians(lat)
    return (1 - math.asinh(math.tan(radians)) / math.pi) / 2 * 2**TILE_ZOOM


def load_elevation_mosaic() -> tuple[np.ndarray, int, int]:
    """Stitch Terrarium tiles into one array; returns it with its first tile indices."""
    x_first, x_last = int(tile_x(TERRAIN_LON[0])), int(tile_x(TERRAIN_LON[1]))
    y_first, y_last = int(tile_y(TERRAIN_LAT[1])), int(tile_y(TERRAIN_LAT[0]))
    columns = x_last - x_first + 1
    rows = y_last - y_first + 1
    mosaic = np.zeros((rows * TILE_SIZE, columns * TILE_SIZE), dtype=np.float32)
    for y in range(y_first, y_last + 1):
        for x in range(x_first, x_last + 1):
            path = TILE_DIR / f"{TILE_ZOOM}_{x}_{y}.png"
            fetch(TILE_URL.format(z=TILE_ZOOM, x=x, y=y), path)
            rgb = np.asarray(Image.open(path).convert("RGB"), dtype=np.float32)
            elevation = rgb[..., 0] * 256 + rgb[..., 1] + rgb[..., 2] / 256 - 32768
            top, left = (y - y_first) * TILE_SIZE, (x - x_first) * TILE_SIZE
            mosaic[top : top + TILE_SIZE, left : left + TILE_SIZE] = elevation
    return mosaic, x_first, y_first


def build_grid() -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Resample the mosaic to a regular lon/lat grid; rows run south to north."""
    mosaic, x_first, y_first = load_elevation_mosaic()
    mid_lat = math.radians(sum(TERRAIN_LAT) / 2)
    columns = (
        round(
            (TERRAIN_LON[1] - TERRAIN_LON[0])
            * METERS_PER_DEGREE
            * math.cos(mid_lat)
            / GRID_STEP_M
        )
        + 1
    )
    rows = (
        round((TERRAIN_LAT[1] - TERRAIN_LAT[0]) * METERS_PER_DEGREE / GRID_STEP_M) + 1
    )
    lons = np.linspace(*TERRAIN_LON, columns)
    lats = np.linspace(*TERRAIN_LAT, rows)
    pixel_x = np.array([(tile_x(lon) - x_first) * TILE_SIZE for lon in lons])
    pixel_y = np.array([(tile_y(lat) - y_first) * TILE_SIZE for lat in lats])
    grid = bilinear(mosaic, *np.meshgrid(pixel_x, pixel_y))
    return lons, lats, grid


def bilinear(values: np.ndarray, x: np.ndarray, y: np.ndarray) -> np.ndarray:
    x0 = np.clip(np.floor(x).astype(int), 0, values.shape[1] - 2)
    y0 = np.clip(np.floor(y).astype(int), 0, values.shape[0] - 2)
    dx, dy = x - x0, y - y0
    top = values[y0, x0] * (1 - dx) + values[y0, x0 + 1] * dx
    bottom = values[y0 + 1, x0] * (1 - dx) + values[y0 + 1, x0 + 1] * dx
    return top * (1 - dy) + bottom * dy


def sample_elevation(
    lons: np.ndarray,
    lats: np.ndarray,
    grid: np.ndarray,
    lon: np.ndarray,
    lat: np.ndarray,
) -> np.ndarray:
    x = (lon - lons[0]) / (lons[1] - lons[0])
    y = (lat - lats[0]) / (lats[1] - lats[0])
    return np.maximum(bilinear(grid, x, y), 0)


def smooth(grid: np.ndarray) -> np.ndarray:
    """Box blur, so contours read as lines rather than as single-pixel noise."""
    result = grid.copy()
    for _ in range(CONTOUR_SMOOTH_PASSES):
        padded = np.pad(result, 1, mode="edge")
        result = (
            sum(
                np.roll(np.roll(padded, dy, 0), dx, 1)
                for dy in (-1, 0, 1)
                for dx in (-1, 0, 1)
            )[1:-1, 1:-1]
            / 9
        )
    return result


def contour_lines(
    lons: np.ndarray, lats: np.ndarray, grid: np.ndarray, level: float
) -> list[list[list[float]]]:
    generator = contour_generator(x=lons, y=lats, z=grid)
    return [
        np.round(line, COORD_DECIMALS).tolist()
        for line in generator.lines(level)
        if len(line) >= MIN_LINE_POINTS
    ]


def overpass(query: str, cache_name: str) -> list[dict]:
    body = urllib.parse.urlencode({"data": query}).encode()
    raw = fetch(OVERPASS_URL, OSM_DIR / f"{cache_name}.json", body)
    return json.loads(raw)["elements"]


def stitch_rings(segments: list[list[list[float]]]) -> list[list[list[float]]]:
    """Join a relation's outer ways, which OSM often splits, into closed rings."""
    remaining = [segment for segment in segments if segment]
    rings = []
    while remaining:
        ring = remaining.pop(0)
        extended = True
        while ring[0] != ring[-1] and extended:
            extended = False
            for index, segment in enumerate(remaining):
                if segment[0] == ring[-1]:
                    ring = ring + segment[1:]
                elif segment[-1] == ring[-1]:
                    ring = ring + segment[::-1][1:]
                else:
                    continue
                remaining.pop(index)
                extended = True
                break
        if len(ring) >= 4 and ring[0] == ring[-1]:
            rings.append(ring)
    return rings


def outer_rings(element: dict) -> list[list[list[float]]]:
    """Closed lon/lat rings of a way or of a relation's outer members."""
    if element["type"] == "way":
        geometries = [element.get("geometry", [])]
    else:
        geometries = [m.get("geometry", []) for m in element.get("members", []) if m.get("role") == "outer"]
    segments = [[[round(p["lon"], 6), round(p["lat"], 6)] for p in geometry] for geometry in geometries]
    return stitch_rings(segments)


def parse_meters(value: str | None) -> float | None:
    if not value:
        return None
    try:
        return float(value.replace("m", "").strip())
    except ValueError:
        return None


def element_heights(tags: dict, default_height: float) -> tuple[float, float]:
    """Return (base, top) in metres above the ground."""
    height = parse_meters(tags.get("height"))
    levels = parse_meters(tags.get("building:levels"))
    if height is None and levels is not None:
        height = levels * FLOOR_HEIGHT_M
    if height is None:
        height = default_height
    base = parse_meters(tags.get("min_height"))
    if base is None:
        min_level = parse_meters(tags.get("building:min_level"))
        base = min_level * FLOOR_HEIGHT_M if min_level is not None else 0.0
    return base, max(height, base + 1)


def circle_ring(lon: float, lat: float, radius_m: float) -> list[list[float]]:
    lat_step = radius_m / METERS_PER_DEGREE
    lon_step = lat_step / math.cos(math.radians(lat))
    ring = [
        [round(lon + lon_step * math.cos(a), 6), round(lat + lat_step * math.sin(a), 6)]
        for a in (
            2 * math.pi * i / FALLBACK_CIRCLE_POINTS
            for i in range(FALLBACK_CIRCLE_POINTS)
        )
    ]
    return ring + [ring[0]]


def fetch_landmark(place: dict) -> list[dict]:
    around = f"(around:{place['radius']},{place['lat']},{place['lon']})"
    name_filter = f'["name"~"{place["name"]}",i]'
    selectors = [
        f'way["building"]{name_filter}{around};',
        f'relation["building"]{name_filter}{around};',
        f'way["man_made"]{name_filter}{around};',
        f'way["historic"]{name_filter}{around};',
        f'relation["historic"]{name_filter}{around};',
        f'way["leisure"="stadium"]{name_filter}{around};',
    ]
    if place.get("parts"):
        selectors.append(f'way["building:part"]{around};')
        selectors.append(f'relation["building:part"]{around};')
    query = f"[out:json][timeout:60];({''.join(selectors)});out geom;"
    elements = overpass(query, place["id"])
    parts = [e for e in elements if "building:part" in e.get("tags", {})]
    # Parts replace the outline they describe; otherwise the outline hides them.
    chosen = parts if parts else elements
    pieces = []
    for element in chosen:
        base, top = element_heights(element.get("tags", {}), place["height"])
        for ring in outer_rings(element):
            pieces.append({"ring": ring, "base": base, "top": top})
    if not pieces and place.get("fallback_radius"):
        pieces.append(
            {
                "ring": circle_ring(
                    place["lon"], place["lat"], place["fallback_radius"]
                ),
                "base": 0.0,
                "top": place["height"],
            }
        )
    print(
        f"  {place['id']}: {len(elements)} OSM elements, {len(pieces)} pieces, tallest {max((p['top'] for p in pieces), default=0):.0f} m"
    )
    return pieces


def fetch_beaches() -> list[list[list[float]]]:
    bbox = f"{TERRAIN_LAT[0]},{TERRAIN_LON[0]},{TERRAIN_LAT[1]},{TERRAIN_LON[1]}"
    query = f'[out:json][timeout:60];(way["natural"="beach"]({bbox});relation["natural"="beach"]({bbox}););out geom;'
    return [
        ring for element in overpass(query, "beaches") for ring in outer_rings(element)
    ]


def build_landmarks(lons: np.ndarray, lats: np.ndarray, grid: np.ndarray) -> list[dict]:
    landmarks = []
    for place in LANDMARKS:
        pieces = fetch_landmark(place)
        ground = float(
            sample_elevation(
                lons, lats, grid, np.array(place["lon"]), np.array(place["lat"])
            )
        )
        landmarks.append(
            {
                "id": place["id"],
                "label": place["label"],
                "primary": bool(place.get("primary")),
                "lon": place["lon"],
                "lat": place["lat"],
                "ground": round(ground, 1),
                "pieces": pieces,
            }
        )
    for place in GROUND_LABELS:
        ground = float(
            sample_elevation(
                lons, lats, grid, np.array(place["lon"]), np.array(place["lat"])
            )
        )
        landmarks.append(
            {
                "id": place["id"],
                "label": place["label"],
                "primary": place["primary"],
                "lon": place["lon"],
                "lat": place["lat"],
                "ground": round(ground, 1),
                "pieces": [],
            }
        )
    return landmarks


def write_context(lons: np.ndarray, lats: np.ndarray, grid: np.ndarray) -> None:
    clamped = np.clip(np.round(grid), -32768, 32767).astype("<i2")
    TERRAIN_BIN.write_bytes(clamped.tobytes())

    land = np.maximum(smooth(grid), 0)
    top = int(land.max())
    contours = [
        {
            "level": level,
            "index": level % INDEX_CONTOUR_M == 0,
            "lines": contour_lines(lons, lats, land, level),
        }
        for level in range(CONTOUR_STEP_M, top, CONTOUR_STEP_M)
    ]
    payload = {
        "terrain": {
            "lon": TERRAIN_LON,
            "lat": TERRAIN_LAT,
            "columns": len(lons),
            "rows": len(lats),
            "shoreLevel": SHORE_LEVEL_M,
        },
        "contours": contours,
        "shore": contour_lines(lons, lats, smooth(grid), SHORE_LEVEL_M),
        "beaches": fetch_beaches(),
        "landmarks": build_landmarks(lons, lats, grid),
    }
    CONTEXT_JSON.write_text(
        json.dumps(payload, separators=(",", ":"), ensure_ascii=False)
    )
    print(
        f"terrain.bin {TERRAIN_BIN.stat().st_size / 1e6:.2f} MB, peak {top} m; context.json {CONTEXT_JSON.stat().st_size / 1e6:.2f} MB"
    )


def write_trees(lons: np.ndarray, lats: np.ndarray, grid: np.ndarray) -> None:
    trees = pd.read_csv(SOURCE_CSV, dtype=str)
    trees["lat"] = pd.to_numeric(trees["latitud"], errors="coerce")
    trees["lon"] = pd.to_numeric(trees["longitud"], errors="coerce")
    trees = trees.dropna(subset=["lat", "lon"])
    trees = trees[trees["lat"].between(*LAT_RANGE) & trees["lon"].between(*LON_RANGE)]

    planted = pd.to_datetime(trees["data_plantacio"], errors="coerce")
    days = (planted - EPOCH).dt.days
    trees["t"] = days.where(days >= 0, UNDATED).fillna(UNDATED).astype(int)
    trees = trees.sort_values("t")

    barri_names = sorted(trees["nom_barri"].dropna().unique())
    barri_index = {name: i for i, name in enumerate(barri_names)}
    trees["b"] = trees["nom_barri"].map(barri_index).fillna(UNDATED).astype(int)
    trees["e"] = np.round(
        sample_elevation(
            lons, lats, grid, trees["lon"].to_numpy(), trees["lat"].to_numpy()
        )
    ).astype(int)

    payload = {
        "epoch": EPOCH.strftime("%Y-%m-%d"),
        "barris": barri_names,
        "b": trees["b"].tolist(),
        "lon": trees["lon"].round(COORD_DECIMALS).tolist(),
        "lat": trees["lat"].round(COORD_DECIMALS).tolist(),
        "t": trees["t"].tolist(),
        "e": trees["e"].tolist(),
    }
    TREES_JSON.write_text(json.dumps(payload, separators=(",", ":")))
    dated = int((trees["t"] != UNDATED).sum())
    print(
        f"{len(trees)} trees, {dated} dated, highest {trees['e'].max()} m -> {TREES_JSON} ({TREES_JSON.stat().st_size / 1e6:.1f} MB)"
    )


def main() -> None:
    lons, lats, grid = build_grid()
    write_context(lons, lats, grid)
    write_trees(lons, lats, grid)


if __name__ == "__main__":
    main()
