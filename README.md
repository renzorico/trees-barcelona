# Barcelona Plantings

Animated 3D map of Barcelona's street trees by planting date, 2007 to 2026. Trees drop in as they were planted. Only the 22% of trees with a recorded date are animated; the rest show as faint street context. Made for #30DayMapChallenge.

Add `?film` to the URL for a controls-free camera move meant for screen recording.

## Data

- Trees: Open Data BCN, "Arbrat viari" (street trees), Ajuntament de Barcelona, CC BY 4.0. 145,397 trees, 32,130 with a planting date.
- Elevation: Mapzen Terrain Tiles (Terrarium format, AWS Open Data). Relief is exaggerated on the page.
- Landmarks and beaches: © OpenStreetMap contributors, ODbL, via the Overpass API.

Inspiration: a Cluj-Napoca tree-growth map, and Craig Taylor's 2019 New York tree animation.

## Setup

1. Download the "Arbrat viari" CSV from Open Data BCN and save it as `data/arbrat_viari.csv`.
2. Build the data files:
   ```bash
   python3 -m venv .venv && source .venv/bin/activate && pip install -r requirements.txt
   python prep.py
   ```
   This downloads the elevation tiles and OSM data once into `data/` (gitignored), then writes `trees.json`, `terrain.bin` and `context.json`. Those three are committed, so the page runs without re-running this.

## Run

```bash
python3 -m http.server 8765
```

Open http://localhost:8765/index.html. The page needs internet: MapLibre GL and deck.gl load from jsDelivr, fonts from Google Fonts.

## Environment variables

None. See `.env.example`.

## Publish

GitHub Pages, branch `main`, folder `/`. Before sharing, set `og:image` and `twitter:image` in `index.html` to the full `https://` URL of `og.png`.

## Layout

| File | Purpose |
|---|---|
| `index.html` | The whole page (MapLibre + deck.gl, no build step) |
| `prep.py` | Builds all data files |
| `trees.json` | Cleaned tree data |
| `terrain.bin` | Elevation grid, 16-bit metres, rows south to north |
| `context.json` | Contours, shoreline, beaches, landmark footprints |
| `og.png` | Share image |
| `audits/` | UX audit report |
| `PRODUCT.md` | Product notes |
