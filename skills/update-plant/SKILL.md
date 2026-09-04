---
name: update-plant
description: >
  Update a live What's that flower catalog species: rewrite English
  seven fields from ingest/data/botanical_sources.json pages that cover
  the plant, retune 4-step filters (color, habitat, petal, WCVP L2) from
  those texts, and patch lists_4_v2 / counts_4_v2 as a remove-old/add-new
  diff. Use when the user says update a plant, update English, rewrite
  English, refresh text, accuracy fix, update filters, or runs
  /update-plant.
argument-hint: Latin names or plants_to_update indexes
metadata:
  short-description: Rewrite live English, filters, and filter indexes
---

# Update a plant

English, traits, and 4-step filter indexes for a species **already in
the catalog**. Same facts-and-filters pass as `/add-plant`
(`ingest/ADD_PLANT.md` §§4, 6, 7). Not a new-species add. Not a rename
(`/rename-plant`). No plates, maps, photos, APG, or Slovak unless asked.

Workspace: `~/whatsthatflower`. Python from `ingest/`:
`ingest/.venv/bin/python`. Credentials for `--apply`:
`GOOGLE_APPLICATION_CREDENTIALS` →
`~/Development/Keystore/abherbs-backend-firebase-adminsdk-l5787-839f896846.json`.
Latin name is the **catalog / Firebase key**.

Write path: `scripts.apply_accuracy_patches`. Do **not** call
`catalog.publish.publish()` or `catalog.promote` (counts and
`plants_to_update` would double).

## Gate

- Named plant, index, or a list = dump and rewrite. Do not write
  Firebase until asked to apply / put it live.
- Not in `plants_to_update` → **stop**. That is `/add-plant`.
- WCVP accepted name ≠ catalog key → keep the catalog key; say so.
  Moving the key is `/rename-plant`.
- Do not invent. Only use a page that actually covers this plant.
- Auto-draft / `infer_traits` is a guess. Editorial pass required.

## Input

Resolve the list first:

- Latin names as given (catalog key).
- Integers → `plants_to_update/list[i]`.
- Note WCVP status (`wcvp.lookup`) but do **not** rename.

## Dump

```bash
cd ~/whatsthatflower/ingest
.venv/bin/python -m scripts.update_plant "Genus epithet"
.venv/bin/python -m scripts.update_plant 56
.venv/bin/python -m scripts.update_plant 56 "Arnica montana" --no-fetch
```

Writes `plants/_jobs/_update/{id}_{Slug}/`:

| File | Role |
|---|---|
| `_live.json` | Live `plants_v2`, `plants_headers/{id}`, `translations/en`, WCVP |
| `_hints.json` | `botanical.hints_for` from `ingest/data/botanical_sources.json` |
| `_extracts.json` | Latin-lookup pages + Wikipedia extract (omit with `--no-fetch`) |

`apply_accuracy_patches` skips `_*.json`. Open every **reliable** hint
that returns a page for this species, plus WCVP (local sqlite; live
POWO is Cloudflare-blocked). 404 / empty is normal when the flora does
not cover the plant — skip it. When a new web source is useful, add it
to the registry.

Patch JSON shape: `plants/_jobs/_accuracy_fix/` (e.g.
`publish_51_59/51_Arctostaphylos_uva-ursi.json`).

## English and filters

Rewrite live `translations/en`. Rules and filter codes:
`ingest/ADD_PLANT.md` §§4, 6, 7. Registry: `botanical_sources.json`.

- Seven fields: `description`, `flower`, `inflorescence`, `fruit`,
  `leaf`, `stem`, `habitat`. `description` around 50 words; other
  six up to 4 sentences (`ingest/ADD_PLANT.md` §6). `sourceUrls` = pages actually used.
  Body text states the facts only — no source names in brackets
  (`(WCVP)`, `(BOTANY.cz)`, `(Flora Helvetica)`, `(POWO)`, …).
  Conflicting measurements go in `changelog`, not in the field.
- Lead native range with WCVP, not Wikipedia *sensu lato*.
- Habitat text must support the `filterHabitat` codes.
- Then retune `plants_headers` `filterColor` / `filterHabitat` /
  `filterPetal` from those texts, and `filterDistribution` from WCVP L2
  (native + introduced unless told otherwise). Leave an axis unchanged
  when the live codes still match the sources.
- Height, flowering months, and `toxicityClass` on `plants_v2` from the
  same sources (contact rash → `toxicity` text, not class 1/2).
- Keep culture, culinary, pet-toxicity, and other-species asides out of
  the seven fields. Culinary and traditional use belong in live
  `herbalism` (Uses); leave that field unchanged.
- English `label` / `names` only from an English source. Omit `label`
  if none. Never translate a vernacular into another language.

Do not draft other-language body texts unless asked. If you do,
`translations/{lang}/sourceUrls` lists pages for that language, not a
copy of English `sourceUrls`.

## Patch

Write `{id}_{Slug}.json` in the dump folder (full English replace):

```json
{
  "id": 56,
  "name": "Arnica montana",
  "plants_v2": {},
  "header": {},
  "translations_en": {},
  "sources": [],
  "changelog": []
}
```

- `translations_en` is a **full** `translations/en/{Latin}` payload
  (`.set`). Keep `wikipedia`, `label`, `names`, `toxicity` unless the
  changelog says why they go. Leave live `trivia` and `herbalism`
  unchanged; apply copies them from live onto the payload. Do not
  rewrite trivia or herbalism (Uses).
- `header` only the filter arrays that change (full new lists, not a
  code-level delta). `{}` = leave filters.
- `plants_v2` only fields that change (`heightFrom` / `heightTo`,
  `floweringFrom` / `floweringTo`, `toxicityClass`, …).
- `changelog` one line per decision (kept vs changed, and the source).

Show the changelog and filter delta in the reply. Wait for apply.

## Apply (only when asked)

```bash
cd ~/whatsthatflower/ingest
.venv/bin/python -m scripts.apply_accuracy_patches --dir ~/whatsthatflower/plants/_jobs/_update/56_Arnica_montana
.venv/bin/python -m scripts.apply_accuracy_patches --dir ~/whatsthatflower/plants/_jobs/_update/56_Arnica_montana --apply
```

Dry-run first. `--apply` writes `plants_v2` (update), header filter
arrays, `translations/en` (replace), then `lists_4_v2` / `counts_4_v2`
as **remove-old / add-new** so counts do not double. English
`label` / `names` diffs update `search_v3/en` and `web/labels/en`.
Sets `versions/db_update`. Does not touch `plants_to_update`.

Several plants in one `--apply`: copy only the patch JSON files into
one folder (no `_live.json` needed).

## Verify

- Live `translations/en/{Latin}` has the seven fields and `sourceUrls`
- Header filters match the changelog
- If filters changed: a new key lists the id; a removed key does not;
  `counts_4_v2` moved by 1, not doubled
- If English `label` changed: `web/labels/en/{id}` matches (absent if none)
- https://whatsthatflower.com/plant/{Latin} shows the new English
