---
name: add-distribution-map
description: >
  Build WCVP native/introduced world distribution WebPs for a list of
  catalog species given as Latin names. Fills ingest/data/maps/blank_world.svg
  (countries; US states, Canadian provinces, Chinese provinces; Russia as
  ru-eu / ru-sib / ru-fe), olive native and terracotta introduced, then
  screenshots to 2754×1398 WebP. Use when the user says distribution map,
  range map, add distribution, redo a map, or runs /add-distribution-map.
argument-hint: Latin names
metadata:
  short-description: Native/introduced world maps for a list of species
---

# Add distribution map

Batch range maps only. A new-species add (`/add-plant`) runs this
build/review for that plant and ships the WebP with incremental
publish. Do not write Firebase or GCS until the user says ship / push /
upload (or `/add-plant` is told to add it to the database).

Workspace: `~/whatsthatflower`. Python:
`~/whatsthatflower/ingest/.venv/bin/python`. Jobs:
`plants/_jobs/{Genus_epithet}/` using the **catalog / Firebase key**.
Official file: `{slug}_distribution.webp` (2754×1398) plus the `.svg`
and a `.json` of the WCVP codes.

Source of truth for L3 → CSS classes:
`.grok/skills/add-distribution-map/scripts/l3_map.py`.
Do not invent a parallel table. If a new L3 has no polygon, add it
there.

## Input

Resolve the list first:

- Latin names as given.
- Integers → `plants_to_update/list[i]` via
  `sources.catalog_rest.plants_to_update()`.
- Note WCVP status (`wcvp.lookup`) but do **not** rename the catalog
  key unless asked.

Skip a name that already has `{slug}_distribution.webp` unless the
user asked to replace it.

## Per plant

```bash
~/whatsthatflower/ingest/.venv/bin/python \
  ~/whatsthatflower/.grok/skills/add-distribution-map/scripts/make_map.py \
  --replace \
  "Genus epithet"
```

Omit `--replace` when skipping existing files. Several names on one
line is fine.

The script:

1. Looks up accepted WCVP L3 (`native_l3` / `introduced_l3`). Extinct
   and doubtful areas are already dropped.
2. Maps L3 through `l3_map.py`.
3. Fills `ingest/data/maps/blank_world.svg` via `fill_blank_world.py`
   (token-exact class match — `az` must not paint `us-az`).
4. Olive `#7a9855` native, terracotta `#c17a3a` introduced. Do **not**
   bake a legend into the WebP; the website draws a localized key
   above the map.
5. Chrome headless 2754×1398 → WebP. If native+introduced sit on
   **one continent**, crop to that landmass. If they sit on **one
   island** (Iceland, Hawaii, Madagascar, Japan, …), enlarge that
   island and centre it. Otherwise keep the world.

Do not paint from Wikipedia *sensu lato* or from `filterDistribution`
L2 alone. Lead with WCVP. If POWO’s live Native/Introduced list
disagrees with the local sqlite, say so and follow the page that
covers this plant.

## Grain

| Region | Fill |
|---|---|
| most of the world | ISO country (`.de`, `.fr`, …) |
| USA | `us-or`, `us-co`, … never `.us` unless every state is listed |
| Canada | `ca-ab`, `ca-on`, … |
| China | `cn-xj`, `cn-sc`, … never `.cn` unless every province is listed |
| Russia | `ru-eu` / `ru-sib` / `ru-fe` (WCVP L2 14 / 30 / 31) |

`.fr` is metropolitan France only (not Guiana). `.nl` is European
Netherlands. `.no` excludes Svalbard (`.sj`). North Caucasus (`NCS`)
has no polygon; it rides inside `ru-eu`. Paint `.ge` / `.am` / `.az`
for Transcaucasus. Australia, Mexico, Brazil, India stay country-level.

If the script prints `unmapped L3`, fix `l3_map.py` or leave a note
in the review. Do not silently drop a country that has a class.

## Review

After every name in the list has a WebP, **show those images** in the
reply (the `{slug}_distribution.webp` files). Check:

- native vs introduced colours match WCVP
- no whole-US / whole-China / whole-Canada blob
- Ireland / Portugal / Turkey / Svalbard / French Guiana only if listed
- Russia split looks right when only one of 14 / 30 / 31 is occupied
- no baked-in English legend on the WebP
- single-continent ranges are cropped to that continent; single-island
  endemics are enlarged and centred

Fix named problems, re-run `--replace` for those names, show again.
Do not ship from this step.

## Ship (only when asked)

Do **not** call `catalog.publish.publish()`. Upload
`{illustration_stem}_distribution.webp` to the same GCS folder as the
plate (`plants_v2/{Latin}/illustrationUrl`). Make it public. HEAD-check
size against the local file.

The website derives the path from the plate stem
(`web/src/api.js` `distributionRel`). Do not add `distributionUrl`
unless the file cannot sit next to the plate. Leave other Firebase
paths alone.
