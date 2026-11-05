# Product

<!-- impeccable:product-schema 1 -->

## Platform

web

## Stack

Static page: plain HTML/JS, no framework, no build step beyond `prep.py` (data prep). Deployed on GitHub Pages.

## Users

People in the #30DayMapChallenge community, mostly viewing a shared LinkedIn post, often on a phone, deciding in seconds whether to watch. Author: Renzo, data scientist and teacher in Barcelona.

## Product Purpose

An animated map of Barcelona's street trees by planting date, made as a #30DayMapChallenge entry. Success: a viewer watches it through, understands that trees appear as they were planted, and shares it.

## Positioning

Barcelona's official street-tree registry records a planting date per tree, so the animation shows real planting history rather than a staged order. It also shows the gap: only about 22% of trees have a date (32,130 of 145,397), so dated plantings appear against the faint undated rest of the city. It is a Barcelona rework of a Cluj-Napoca tree-growth animation (Craig Taylor's 2019 New York animation was that post's inspiration) with a different look.

## Operating Context

- Data: Open Data BCN "Arbrat viari" CSV (`data/arbrat_viari.csv`), prepared by `prep.py` into `trees.json`.
- Dated trees run 2007 to 2026; a handful are earlier and are treated as dated.
- Species group: plane trees (*Platanus*), palms, other.
- Each tree has a neighbourhood (`nom_barri`) and district (`nom_districte`) in the source data; `prep.py` does not export them yet.
- Local preview: `python3 -m http.server` in this folder.

## Capabilities and Constraints

Current: play/pause, scrubber, year counter, live count, species legend, light and dark themes (system preference).

Requested by the author, not yet built:
- 3D view, with trees dropping into place as they are planted.
- Speed control (faster and slower).
- Division by neighbourhood (barri).
- Better overall design and theme than the current flat page.

Must hold:
- Works at phone width (375px).
- Light and dark themes.
- Data credit (Ajuntament de Barcelona, Open Data BCN, CC BY 4.0) and the 22% dated caveat stay visible.

Open: the 3D technique and library (a new dependency to flag), and what "divide by neighbourhood" looks like (filter, small multiples, or a ranking).

## Brand Commitments

None beyond the title "Barcelona Plantings". Author inspiration (the Cluj-Napoca map and Craig Taylor's New York animation) should be credited where the map is posted.

## Evidence on Hand

- Real data: `data/arbrat_viari.csv` (145,397 trees), `trees.json` (3.2 MB).
- Working prototype: `index.html`.
- Not available and not to be invented: any per-tree height or crown size (the current data has none), planting dates for the undated 78%.

## Product Principles

1. Show real data; never stage or invent planting order.
2. State the data's limits (22% dated) on the page, not only in the post.
3. The map is the point; controls support it and stay out of the way.
4. Works first for a phone-sized viewer who gives it a few seconds.
5. Readable and credited so it can be shared as-is.

## Accessibility & Inclusion

Respect the visitor's light/dark preference. Controls must be keyboard-operable with visible focus. Colour coding by species must stay distinguishable (current navy/green/orange palette is weak for the plane-tree green; to be reviewed in design).
