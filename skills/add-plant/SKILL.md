---
name: add-plant
description: >
  Add a species to the What's that flower / abherbs catalog: dry-run job,
  botanicalillustrations.org plate (Imagine cleanup, colorize monochrome,
  or generate from photos), WCVP distribution map, photo review, traits,
  APG path, sourced English, Slovak body text, vernaculars, and incremental
  live publish only when asked to put it in the database. Use when the user
  says add a plant,
  add a species, add *Latin name*, add to the catalog, add to the database,
  new species, or gives an illustration id; or runs /add-plant.
argument-hint: Genus epithet
metadata:
  short-description: Add a species to the live catalog
---

# Add a plant

Follow `ingest/ADD_PLANT.md` end to end. That file is the source of truth
(commands, photos, traits, APG, English, Slovak, names, publish,
verify). Plates: `/add-illustrations`. Maps: `/add-distribution-map`.
Do not invent a shorter pipeline.

Workspace: `~/whatsthatflower`. Run Python from `ingest/` with
`ingest/.venv/bin/python` (or the path in ADD_PLANT.md). Jobs:
`plants/_jobs/{Genus_epithet}/`. Latin name is the Firebase key.

## Gate

- “Add *Latin*” (optional illustration id) = build and review the packet.
  Do not write Firebase or GCS.
- “Add it to the database” / explicit publish = incremental live publish
  after `plant.validate.validate` is ok.
- Already in `plants_to_update` → stop and say so. Live English / filter
  refresh is `/update-plant`.
- No usable plate and Imagine generation failed → stop before publish.
- No `{slug}_distribution.webp` in the job → stop before publish.
- No full `python -m catalog.promote --apply`. Do not call
  `catalog.publish.publish()` twice (a later text/trait fix is
  `/update-plant`).

## Illustration

Follow `/add-illustrations` for the plate (pick, clean / colorize /
generate, install, review grid, ship). A new-species add still needs
that plate in the job before publish. Look and signature table:
`ILLUSTRATION.md`.

## Distribution map

Follow `/add-distribution-map` (build, review the WebP). A new-species
add still needs `{slug}_distribution.webp` in the job before publish.

## Facts and names

Do not invent. English seven fields from pages that actually cover this
plant. `description` around 50 words; the other six up to 4 sentences.
Lead range with WCVP, not Wikipedia *sensu lato*. Do not mix
split-off or *sensu lato* measurements, or involucre with disc diameter.
RHS spread is not height. Contact rash → `toxicity` text, not class 1/2.
Culinary and traditional use may go in optional `herbalism` (UI: Uses);
keep it out of the seven identification fields. `/update-plant` does
not rewrite live `herbalism`.
Details: `ingest/ADD_PLANT.md` §§4 and 6. When a new web source is useful,
add it to `ingest/data/botanical_sources.json`. Never translate an English
common name; `label` / `names` only from a source for that language. Omit
`label` if none. Do not draft CS/RU/DE/FR/PL/JA/ES body texts unless asked.
`translations/{lang}/{Latin}/sourceUrls` lists pages for that language
(not a copy of English `sourceUrls`).

After rewriting English `inflorescence`, set `plants_v2.inflorescenceType`
from that paragraph (`plant.inflorescence_type.classify`). Array of the
17 legend keys, primary first. Empty if none apply (solitary flower,
catkin, unnamed cluster). Dry-run auto-draft is a guess — reclassify
after the editorial English. Details: `ingest/ADD_PLANT.md` §6.

## Slovak

After English is rewritten, write the same seven fields in Slovak to
`translations/sk.json`, from those sourced facts. `label` / `names` only
from a Slovak source (Wikidata, sk.wikipedia title, EPPO, BOTANY.cz
*Slovenská jména*, Flóra Slovenska). Omit `label` if none — the app and site show Latin.
Diagnostic contrasts may use `<b>…</b>`. `sourceUrls` are the Slovak
pages actually used (Wikidata, sk.wikipedia, EPPO, BOTANY.cz, Flóra
Slovenska, pladias.sk). Goes live only with incremental publish.
