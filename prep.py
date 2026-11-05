"""Clean Barcelona street-tree CSV into a compact JSON for the web map."""

import json
from pathlib import Path

import pandas as pd

DATA_DIR = Path(__file__).parent / "data"
SOURCE_CSV = DATA_DIR / "arbrat_viari.csv"
OUTPUT_JSON = Path(__file__).parent / "trees.json"

EPOCH = pd.Timestamp("2007-01-01")
UNDATED = -1
COORD_DECIMALS = 5
# Rough Barcelona bounds, to drop bad coordinates.
LAT_RANGE = (41.30, 41.47)
LON_RANGE = (2.05, 2.24)

GROUP_PLANE, GROUP_PALM, GROUP_OTHER = 0, 1, 2
PALM_GENERA = (
    "Phoenix",
    "Washingtonia",
    "Trachycarpus",
    "Chamaerops",
    "Livistona",
    "Butia",
    "Syagrus",
)


def species_group(scientific_name: str) -> int:
    if scientific_name.startswith("Platanus"):
        return GROUP_PLANE
    if scientific_name.startswith(PALM_GENERA):
        return GROUP_PALM
    return GROUP_OTHER


def main() -> None:
    trees = pd.read_csv(SOURCE_CSV, dtype=str)
    trees["lat"] = pd.to_numeric(trees["latitud"], errors="coerce")
    trees["lon"] = pd.to_numeric(trees["longitud"], errors="coerce")
    trees = trees.dropna(subset=["lat", "lon"])
    trees = trees[trees["lat"].between(*LAT_RANGE) & trees["lon"].between(*LON_RANGE)]

    planted = pd.to_datetime(trees["data_plantacio"], errors="coerce")
    days = (planted - EPOCH).dt.days
    trees["t"] = days.where(days >= 0, UNDATED).fillna(UNDATED).astype(int)
    trees["g"] = trees["cat_nom_cientific"].fillna("").map(species_group)
    trees = trees.sort_values("t")

    barri_names = sorted(trees["nom_barri"].dropna().unique())
    barri_index = {name: i for i, name in enumerate(barri_names)}
    trees["b"] = trees["nom_barri"].map(barri_index).fillna(UNDATED).astype(int)

    payload = {
        "epoch": EPOCH.strftime("%Y-%m-%d"),
        "barris": barri_names,
        "b": trees["b"].tolist(),
        "lon": trees["lon"].round(COORD_DECIMALS).tolist(),
        "lat": trees["lat"].round(COORD_DECIMALS).tolist(),
        "t": trees["t"].tolist(),
        "g": trees["g"].tolist(),
    }
    OUTPUT_JSON.write_text(json.dumps(payload, separators=(",", ":")))
    dated = int((trees["t"] != UNDATED).sum())
    print(
        f"{len(trees)} trees, {dated} dated -> {OUTPUT_JSON} ({OUTPUT_JSON.stat().st_size / 1e6:.1f} MB)"
    )


if __name__ == "__main__":
    main()
