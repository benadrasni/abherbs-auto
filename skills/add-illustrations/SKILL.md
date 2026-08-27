---
name: add-illustrations
description: >
  Create or replace botanical plates for a list of catalog species given as
  Latin names or plants_to_update indexes. Pick a botanicalillustrations.org
  plate, Imagine clean / colorize / generate, install official WebPs, then
  show a 400×600 contact sheet for review. Use when the user says prepare
  plates, new plates, add illustrations, replace illustrations, plate batch,
  or runs /add-illustrations.
argument-hint: Latin names or plants_to_update indexes
metadata:
  short-description: Create or replace plates for a list of species
---

# Add illustrations

Batch plate work only. Not a full species add (that is `/add-plant`).
Do not write Firebase or GCS until the user says ship / push / upload.

Look and signature table: workspace `ILLUSTRATION.md`. Exact Imagine
strings: `plant.media.imagine_prompt(kind, author=…)`. Python:
`~/whatsthatflower/ingest/.venv/bin/python` from `ingest/`.

Jobs: `plants/_jobs/{Genus_epithet}/` using the **catalog / Firebase
key** (may differ from the WCVP accepted name). Official files:
`{slug}.webp`, `{slug}@1600.webp` (1600×2400), `{slug}@400.webp`
(400×600).

## Input

Resolve the list first:

- Latin names as given.
- Integers → `plants_to_update/list[i]` via
  `sources.catalog_rest.plants_to_update()`.
- Note WCVP status (`wcvp.lookup`) but do **not** rename the catalog
  key unless asked. Search the illustration site under the catalog
  name and, if needed, the accepted name / a site synonym.

Skip a name that already has a finished cream plate in `media/` unless
the user asked to replace it.

## Per plant

1. **Pick.** User-given illustration id wins. Else search
   botanicalillustrations.org over **HTTP** (HTTPS times out). Download
   a few thumbs per plant and choose from a pick-grid, not by opening
   every HD. Choose the plate that best *represents the plant*: typical
   flower, readable habit, colour when possible. Prefer a diagnostic flowering shoot over fruit-only,
   outline, analytic, or multi-species sheets. Flora Danica / Flora
   Batava colour plates are often right; do not take `score_plate` or
   the first hit blindly. If the accepted name has 0 plates, search
   the synonym the site uses (e.g. *Anemone hepatica* for *Hepatica
   nobilis*, *Lithospermum* for *Aegonychon*). If there is still no
   usable drawing, **stop and ask** before `generate`: generate from
   photos, use the live catalog plate, or skip. Do not generate until
   the user chooses.
2. **Author.** `author_from_plate_title`: text after ` / `, then before
   the first comma. Ignore any mark printed on the scan.
3. **Pass.** Write `plant.media.imagine_prompt(kind, author=…)` to
   `media/illustration_imagine_prompt.txt` and use that exact string.

   | Source | `kind` | Mark |
   |---|---|---|
   | colour plate | `clean` | site author only; no Grok |
   | only monochrome from the site | `colorize` | keep that author and add `colored by Grok Imagine` |
   | no drawing, and the user said generate | `generate` | `Grok Imagine` only |

   A monochrome engraving is still a plate — colorize from photos of
   this species (binomial gate). Do not invent colour or paste photo
   parts onto the drawing. Never restyle an old catalog drawing.
4. **Imagine.** Download HD to `illustration_raw.jpg`. Pad to 2:3
   cream before `image_edit` (non-2:3 scans come back letterboxed):

   ```bash
   ~/whatsthatflower/ingest/.venv/bin/python \
     ~/whatsthatflower/.grok/skills/add-illustrations/scripts/plate_fix.py \
     prepare --job "Genus epithet"
   ```

   That writes `media/illustration_raw_23.jpg` (~1067×1600) from
   `illustration_raw.jpg`. Pass it to `image_edit`. Portrait **2:3**.
   Always pass `ingest/data/background.webp` as the **last** image. The
   prompt tells Imagine to use that last image as the page. Do not
   describe the cream field. `image_edit` accepts **at most 3 images**.
   **Clean:** plate, then `background.webp`.
   **Colorize:** plate, one photo (habit or flower), then `background.webp`.
   **Generate:** one photo (habit; flower if no habit), then
   `background.webp`. Downsample photo refs to ~1280 on the long side
   and crop scale bars first (raw ~3000 px fails).
   Keep iters. One change per follow-up. Do **not** pass another
   species’ plate as a vignette, style, or signature reference —
   Imagine merges the plants.
5. **Check the winner** before install:
   - composition kept (do not restack parts)
   - habit / flower / leaf match the photos on colorize and generate
   - no labels, letters (`a`–`e`), plate numbers, or titles
   - no open-book binding, inner plate-mark, white letterbox, or burnt
     dark frame (vignette as soft as the rest of the batch)
   - signature **small**, bottom-right (about as close as
     *Aconitum napellus* / *Angelica sylvestris*), exact wording
   - discard an iter that invents a historic artist, doubles the
     author, drops dissected parts, or changes organs

   White bars, burnt/pale corners, or a huge signature: **PIL first**,
   not another `image_edit`. Still `image_edit` for labels, restacked
   parts, wrong colour, or a missing mark.

   ```bash
   ~/whatsthatflower/ingest/.venv/bin/python \
     ~/whatsthatflower/.grok/skills/add-illustrations/scripts/plate_fix.py \
     letterbox --job "Genus epithet" --install
   ~/whatsthatflower/ingest/.venv/bin/python \
     ~/whatsthatflower/.grok/skills/add-illustrations/scripts/plate_fix.py \
     edges --job "Genus epithet" --install
   ~/whatsthatflower/ingest/.venv/bin/python \
     ~/whatsthatflower/.grok/skills/add-illustrations/scripts/plate_fix.py \
     signature --job "Genus epithet" --from /path/to/same-author.jpg --install
   ```

   `letterbox` / `edges` / `signature` read the latest `iterN.jpg` (or
   the official plate) and write the next iter. `--install` runs
   `import_imagine_result`. Same author on `--from`; if extract fails,
   pick a cleaner donor — do not `image_edit` a second species onto this
   plate. `detect --job …` prints bar sizes without writing.
6. **Install.** `plant.media.import_imagine_result` → official WebPs.
   `plate.json`: `accepted_name` (catalog key), `id_illustration`,
   `author`, `title`, `source_url`, `cleaner=imagine`,
   `source=clean|colorized|generated`, `status=prepared`.

## Review grid

After every plant in the list is installed, build a contact sheet of
the `@400` (400×600) plates and **show that image** in the reply.
Inspect that sheet (and a pick-grid of thumbs if you made one). Do
not read every thumbnail, HD scan, or iter.

```bash
~/whatsthatflower/ingest/.venv/bin/python \
  ~/whatsthatflower/.grok/skills/add-illustrations/scripts/plate_grid.py \
  --out ~/whatsthatflower/plants/_jobs/_plate_pick/grid.jpg \
  --names "Genus epithet" "Genus epithet" \
  --indexes 30 31
```

`--indexes` is optional (same order as `--names`). Five columns, as
many rows as needed. Open the JPEG in the reply so the user can
inspect. Fix named problems, rebuild the grid, then wait again. Do
not ship from this step.

## Ship (only when asked)

Do **not** call `catalog.publish.publish()`. Upload the three official WebPs
to the folder and **basename** in live
`plants_v2/{Latin}/illustrationUrl` (that basename can be an old
synonym: *Anacamptis morio* → `Orchis_morio.webp`). Make them public.
HEAD-check size against local files. Set `plate.json` `status=shipped`.
Leave Firebase paths alone unless the user asked to rename files or
the plant.
