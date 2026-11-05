# Barcelona Plantings

Animated 3D map of Barcelona's street trees by planting date, 2007 to 2026. Trees drop in as they were planted. Only the 22% of trees with a recorded date are animated; the rest show as faint street context. Made for #30DayMapChallenge.

Add `?film` to the URL for a controls-free camera move meant for screen recording.

## Data

Open Data BCN, "Arbrat viari" (street trees), Ajuntament de Barcelona, CC BY 4.0. 145,397 trees, 32,130 with a planting date.

Inspiration: a Cluj-Napoca tree-growth map, and Craig Taylor's 2019 New York tree animation.

## Setup

1. Download the "Arbrat viari" CSV from Open Data BCN and save it as `data/arbrat_viari.csv`.
2. Create the data file (needs Python 3 with pandas):
   ```bash
   python3 -m venv .venv && source .venv/bin/activate && pip install pandas
   python prep.py
   ```
   This writes `trees.json`, which is committed so the page runs without the CSV.

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
| `prep.py` | CSV to `trees.json` |
| `trees.json` | Cleaned tree data |
| `og.png` | Share image |
| `audits/` | UX audit report |
| `PRODUCT.md` | Product notes |
