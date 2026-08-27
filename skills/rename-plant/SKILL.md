---
name: rename-plant
description: >
  Rename a live What's that flower catalog species to its WCVP accepted
  Latin name, including GCS photos, translations, search, APG, and
  observations. Use when the user says rename a plant, rename a species,
  not accepted, WCVP synonym, unaccepted name, or runs /rename-plant.
argument-hint: Old Latin → accepted Latin
metadata:
  short-description: Rename a catalog species to the WCVP accepted name
---

# Rename a plant

Move the Firebase key and GCS objects. Do not add a species (`/add-plant`).
Do not rebuild 4-step filter indexes (`lists_4_v2` / `counts_4_v2` key by
numeric id). No `catalog.promote`.

Workspace: `~/whatsthatflower`. Python from `ingest/`:
`ingest/.venv/bin/python`. Credentials:
`GOOGLE_APPLICATION_CREDENTIALS` →
`~/Development/Keystore/abherbs-backend-firebase-adminsdk-l5787-839f896846.json`.

Queue (pending / stop / keep / done): `references/queue.md`. After a
successful rename, move that row to **Done** with the date. If the user
declines a rename, move the row to **Keep**. Do not invent names;
WCVP sqlite `wcvp/wcvp.sqlite` via `sources.wcvp.lookup`.

GCS paths that still use a different Latin folder or filename while the
catalog key is already correct: `references/resource-names.md`. Remap
objects + URLs; do not run this skill.

## Gate

- Named plant, or “next” = first **Pending 1:1** row. Listing the queue
  is read-only. One `--apply` per plant unless the user lists several
  that all pass these gates.
- Dry-run first. `--apply` only when asked to rename (this skill’s
  trigger is that ask).
- Target already in `plants_to_update` → **stop** (merge, not rename).
- Two catalog species → one accepted name → **stop** (merge).
- WCVP accepted rank is not `Species` (subsp, var, forma, section) →
  **stop and ask**. Catalog keys are species binomials.
- Homonyms: match `plants_v2.author` to WCVP `taxon_authors`. Do not
  take the first sqlite row.
- WCVP family or order differs from the live folder
  `{Order}/{Family}/{Slug}` → **stop**. The script remaps only the
  species slug and photo prefix (`as1` → `fs1`), not family/order.
- Old genus == new genus → skip APG move.
- Old genus still has other catalog plants → do **not** delete that
  APG node; remove only this id. `move_apg` deletes the old genus only
  when its list is empty.
- New genus already exists with other plants (e.g. *Rosmarinus* →
  *Salvia*) → add this id to that list; do not overwrite `list`.
- New genus does not exist → create it as a **sibling of the live old
  genus** (Sorbus under Malinae → Aria under Malinae). Do not use the
  APGIV parent when that parent omitted a live subtribe.
- Old genus: richest namesake under the family (same picker as new).
  APGIV often omits Subfamilia; delete leftover copies when empty.
- `update_search_photo` remaps species paths and genus tokens (keep and
  decrement the old genus when others remain; create or increment the
  new genus key; a singleton old genus token points at the species).

## CLI

```bash
cd ~/whatsthatflower/ingest
.venv/bin/python -m scripts.rename_plant "Old name" "New name"
.venv/bin/python -m scripts.rename_plant "Old name" "New name" --apply
```

Dry-run is the default. `--keep-old-gcs` leaves the old photo folder.

Confirm WCVP `accepted_name == New name` and `status == Accepted` for
the **new** name. Lookup the old name only to record it as a synonym.

## What `--apply` must do

Copy then delete. New GCS objects HTTP 200 before deleting the old
catalog folder. `plants_v2/{new}` written before old translations are
removed.

| Surface | Action |
|---|---|
| GCS `photos/{Order}/{Family}/{Slug}/` | Copy; remap slug; `asN.webp` → `{new_prefix}N.webp`; plate `{Old_slug}.webp` / `@1600` / `@400` / `_distribution.webp`. Then delete old folder. If the live folder already uses the accepted slug (copy would be identity), skip copy-to-self and do not delete. |
| GCS `observations/{uid}/{Slug}/` | Copy folder; do not rename `as_…` observation files. |
| `plants_v2` | New key: `name`, WCVP `author` + `ipniId`, GBIF accepted `usage_key`, `APGIV` Genus, remapped `illustrationUrl` / `photoUrls`, `synonyms` includes old binomial. Delete old key. |
| `plants_headers/{id}` | `name` + `url` |
| `plants_to_update/list/{id}` | New Latin |
| `web/catalog/{id}` | `name`, `url`, `illustrationUrl` |
| `web/labels` | Unchanged (keyed by id) |
| `synonyms/{new}` | Copy IPNI list; add old binomial; drop the accepted name as a synonym. Delete `synonyms/{old}` |
| `translations/{lang}/{name}` and `translations_new` | Copy payload as-is; then delete old. Do not rewrite body text or Wikipedia URLs. |
| `search_v3/la` | New binomial `is_label: true`; old binomial stays in `list`, `is_label` removed |
| `search_photo` | Every `path` that was the old Latin → new Latin; keep old binomial as a synonym key; update genus tokens; `m/{freebase}` path |
| `APG IV_v3` | See gates. Do not use `apg_tree.apply_plant` (it can nest the new genus as a subgenus). |
| `observations/public` and `by users/…` `by plant` + `by date` | `plant` field + `photoPaths` slug |
| `versions/db_update` | Today’s date |
| Local `plants/_jobs/{Slug}/` | Rename folder + plate files if present |

Photo prefix: first letter of genus + first letter of the last epithet
(`plant.resolve.photo_prefix`). Filter color/habitat/petal/distribution
arrays stay.

Do not invent vernaculars. Do not translate English common names.

## Verify

Live read-back: `plants_v2/{new}` exists, `{old}` is null, list[id] is
the new name. HEAD new plate + `fs1.webp` (or the new prefix) at
`https://storage.googleapis.com/abherbs-resources/photos/…`.

On https://whatsthatflower.com (no hosting deploy needed; the SPA reads
RTDB):

- `/plant/{New%20name}` — heading, author, photos, synonyms include the old name
- Family and new-genus pages list it
- Search for the **new** name and the **old** name both hit this plant
- Old `/plant/{Old%20name}` 404s (no alias key)

Sitemap HTML shells stay stale until a hosting deploy.

## Worked example

*Acca sellowiana* → *Feijoa sellowiana* (id 892, 2026-08-25). Singleton
genus Acca deleted; genus Feijoa created under Myrteae. Photos
`asN` → `fsN`. Public observation photo copied.

*Anemone narcissiflora* → *Anemonastrum narcissiflorum* (id 32,
2026-08-25). Genus Anemone kept (5 other species); genus Anemonastrum
created under Anemoneae. Photos stayed `anN`. Nested Anemonidium /
Omalocarpus deleted once empty.

*Matricaria recutita* → *Matricaria chamomilla* (id 345, 2026-08-26).
Same genus; APG skipped. Catalog photos already lived under
`Matricaria_chamomilla/` / `mcN.webp`, so GCS catalog copy/delete was a
no-op. Observation folders still remapped.

*Mycelis muralis* → *Lactuca muralis* (id 365, 2026-08-26). Singleton
genus Mycelis deleted; id added to existing Lactuca under Lactucinae
(with *L. serriola*). Photos `mmN` → `lmN`. Hieraciinae dropped 365
(divergent old subtribe; not a common ancestor of the new genus).

*Myosoton aquaticum* → *Stellaria aquatica* (id 369, 2026-08-26).
Homonym *S. aquatica* Pollich is *S. alsine*; catalog author (L.)
Moench → accepted (L.) Scop. Singleton Myosoton deleted (Alsinoideae
plus a stray family-level Alsineae copy). Id added to existing
Stellaria under Alsineae (5 other species). Photos `maN` → `saN`.
Public observation photo copied.

*Papaver argemone* → *Roemeria argemone* (id 398, 2026-08-26).
Genus Papaver kept (3 other species); genus Roemeria created under
Papavereae. Nested section Argemonidium deleted. Photos `paN` → `raN`.

*Polygala chamaebuxus* → *Chamaebuxus unguiculata* (id 426,
2026-08-26). Genus Polygala kept (4 other species); genus Chamaebuxus
created under Polygaleae. Photos `pcN` → `cuN`. Catalog author was
(L.) O.Schwarz (IPNI of *Polygaloides chamaebuxus*); WCVP accepted
author is (Poir.) J.F.B.Pastore.

*Polygala lutea* → *Senega lutea* (id 777, 2026-08-26). Genus Polygala
kept (3 other species); genus Senega created under Polygaleae. Photos
`plN` → `slN`. Author L. → (L.) J.F.B.Pastore & J.R.Abbott.

*Polygaloides paucifolia* → *Chamaebuxus paucifolia* (id 778,
2026-08-26). Singleton genus Polygaloides deleted; id added to existing
Chamaebuxus under Polygaleae (with *C. unguiculata*). Photos `ppN` →
`cpN`. Author (Willd.) J.R.Abbott → (Willd.) J.F.B.Pastore &
Agust.Martinez.

*Potentilla anserina* → *Argentina anserina* (id 53, 2026-08-26).
Genus Potentilla kept (8 other species); genus Argentina created under
Potentillinae. Catalog photos already lived under
`Argentina_anserina/` / `aaN.webp`; plate files remapped in place.
Observation folders remapped.

*Prunus dulcis* → *Prunus amygdalus* (id 850, 2026-08-26). Same genus;
APG skipped. Homonym *P. dulcis* Rouchy is *P. avium*; catalog author
(Mill.) D.A.Webb → accepted Batsch. Photos `pdN` → `paN`.

*Rosmarinus officinalis* → *Salvia rosmarinus* (id 852, 2026-08-26).
Singleton genus Rosmarinus deleted; id added to existing Salvia under
Salviinae (10 other species). Author L. → Spenn. Photos `roN` → `srN`.
Public observation photo copied.

*Rubus plicatus* → *Rubus fruticosus* (id 495, 2026-08-26). Same genus;
APG skipped. Catalog author Weihe & Nees (not illegitimate C.A.Mey. →
*R. persicus*). Photos already lived under `Rubus_fruticosus/` /
`rfN.webp`. Observation folders remapped.

*Scrophularia umbrosa* → *Scrophularia oblongifolia* (id 521, 2026-08-26).
Same genus; APG skipped. Catalog author Dumort. → accepted Loisel. (not
illegitimate Merino). Photos `suN` → `soN`.

*Securigera varia* → *Coronilla varia* (id 524, 2026-08-26). Singleton
genus Securigera deleted; genus Coronilla created under Loteae. Author
(L.) Lassen → L. Photos `svN` → `cvN`. Public observation photos copied.

*Silene viscaria* → *Viscaria vulgaris* (id 538, 2026-08-26). Genus
Silene kept (9 other species); genus Viscaria created under Sileneae.
Author Bernh. Photos `svN` → `vvN`. Observation folders remapped.

*Sinapis arvensis* → *Mutarda arvensis* (id 540, 2026-08-26). Genus
Sinapis kept (*S. alba*); genus Mutarda created under Brassiceae.
Homonym *S. arvensis* O.F.Müll. is illegitimate → *Raphanus
raphanistrum* subsp. *raphanistrum*; catalog author L. → accepted (L.)
D.A.German. Photos `saN` → `maN`. Public observation photos copied.

*Sorbus aria* → *Aria edulis* (id 549, 2026-08-26). Genus Sorbus kept
(*S. aucuparia*, *S. torminalis*); genus Aria created under Malinae
(APGIV omitted that subtribe; live Sorbus is nested there). Nested
subgenus Aria deleted. Author (L.) Crantz → (Willd.) M.Roem. Photos
`saN` → `aeN`.

*Sorbus torminalis* → *Aria torminalis* (id 551, 2026-08-26). Genus
Sorbus kept (*S. aucuparia*); id added to existing Aria under Malinae
(with *A. edulis*). Nested subgenus Torminaria deleted. Author (L.)
Crantz → (L.) Beck. Photos `stN` → `atN`.

*Stachys officinalis* → *Betonica officinalis* (id 556, 2026-08-26).
Genus Stachys kept (4 other species); genus Betonica created under
Stachydeae. Nested section Betonica deleted. Author (L.) Trevis. → L.
Photos `soN` → `boN`. Public observation photos copied.

*Stellaria holostea* → *Rabelera holostea* (id 562, 2026-08-26). Genus
Stellaria kept (5 other species); genus Rabelera created under Alsineae.
Author L. → (L.) M.T.Sharples & E.A.Tripp. Photos `shN` → `rhN`.
Observation folders remapped.

*Thlaspi caerulescens* → *Noccaea caerulescens* (id 1092, 2026-08-26).
Genus Thlaspi kept (*T. arvense*, *T. perfoliatum*); genus Noccaea
created under Thlaspideae. Photos `tcN` → `ncN`. Author already
(J.Presl & C.Presl) F.K.Mey.

*Thlaspi perfoliatum* → *Noccaea perfoliata* (id 577, 2026-08-26).
Genus Thlaspi kept (*T. arvense*); id added to existing Noccaea under
Thlaspideae (with *N. caerulescens*). Author L. → (L.) Al-Shehbaz.
Photos `tpN` → `npN`.

*Atropa belladonna* → *Atropa bella-donna* (id 66, 2026-08-26). Same
genus; APG skipped. Catalog spelling was missing from WCVP; accepted
is the hyphenated binomial. Photos stayed `abN`. Author already L.

*Cirsium acaule* → *Cirsium acaulon* (id 122, 2026-08-26). Same genus;
APG skipped. Catalog spelling was missing from WCVP; accepted is
*acaulon*. Photos stayed `caN`. Author already (L.) Scop.

*Dahlia × pinnata* → *Dahlia pinnata* (id 1155, 2026-08-26). Same genus;
APG skipped. Catalog spelling with hybrid sign was missing from WCVP;
accepted is the unhybridized binomial. Photos stayed `dpN`. Author
already Cav. Public observation photos copied.

*Hibiscus rosa-sinensis* → *Hibiscus × rosa-sinensis* (id 954,
2026-08-26). Same genus; APG skipped. Catalog spelling was missing from
WCVP; accepted is the hybrid binomial. Photos stayed `hrN`. Author
already L. Public observation photo copied. `verify_public` percent-encodes
`×` in GCS URLs (`Hibiscus_%C3%97_rosa-sinensis`).

*Paeonia suffruticosa* → *Paeonia × suffruticosa* (id 809, 2026-08-26). Same
genus; APG skipped. Catalog spelling was missing from WCVP; accepted
is the hybrid binomial. Photos stayed `psN`. Author already Andrews.
Public observation row remapped. Plate and catalog photos copied to
`Paeonia_%C3%97_suffruticosa/`.

*Pentanema britannicum* → *Pentanema britannica* (id 1253, 2026-08-26). Same
genus; APG skipped. Catalog spelling was missing from WCVP; accepted is
*britannica*. Photos stayed `pbN`. Author already (L.) D.Gut.Larr.,
Santos-Vicente, Anderb., E.Rico & M.M.Mart.Ort. Plate and catalog photos
copied to `Pentanema_britannica/`.

*Pseudofumaria lutea* → *Pseudo-fumaria lutea* (id 658, 2026-08-26). Catalog
spelling was missing from WCVP; accepted is the hyphenated genus.
Singleton genus Pseudofumaria deleted; genus Pseudo-fumaria created under
Fumarieae. Photos stayed `plN`. Author already (L.) Borkh. User observation
row remapped; GCS observation objects were already absent. Plate and
catalog photos copied to `Pseudo-fumaria_lutea/`.

*Spirodela polyrrhiza* → *Spirodela polyrhiza* (id 554, 2026-08-26). Same
genus; APG skipped. Catalog spelling was missing from WCVP; accepted is
*polyrhiza*. Photos stayed `spN`. Author already (L.) Schleid. Catalog
photos already lived under `Spirodela_polyrhiza/`.

*Consolida ajacis* → *Delphinium ajacis* (id 825, 2026-08-26). User
overrode the merge stop (*C. orientalis* id 826 still live; same WCVP
accepted name). Genus Consolida kept; id added to existing Delphinium
under Delphinieae (with *D. consolida*, *D. elatum*, *D. oxysepalum*).
Nested section Consolida kept (826). Photos `caN` → `daN`. Author (L.)
Schur → L.

*Bryonia dioica* → *Bryonia cretica* (id 75, 2026-08-27). Same genus;
APG skipped. User chose the parent species as the catalog key (WCVP
accepted is *B. cretica* subsp. *dioica*). Photos `bdN` → `bcN`.
Author set to L. (from *B. cretica*). Plate and catalog photos copied
to `Bryonia_cretica/`.

*Euphrasia rostkoviana* → *Euphrasia officinalis* (id 204, 2026-08-27).
Same genus; APG skipped. User chose the parent species as the catalog
key (WCVP accepted is *E. officinalis* subsp. *pratensis*). Photos
`erN` → `eoN`. Author Hayne → L. Catalog photos stayed under
`Lamiales/Scrophulariaceae/` (historical folder; live APG family is
Orobanchaceae, same as *E. stricta*). Genus Euphrasia kept (*E. stricta*,
*E. nemorosa*).

*Knautia dipsacifolia* → *Knautia maxima* (id 292, 2026-08-27). Same
genus; APG skipped. User chose the parent species as the catalog key
(WCVP accepted is *K. maxima* subsp. *maxima*). Homonym *K. dipsacifolia*
Heuff. is illegitimate → *K. drymeja* subsp. *drymeja*; catalog author
Kreutzer → accepted (Opiz) J.Ortmann. Photos `kdN` → `kmN`. Genus
Knautia kept (*K. arvensis*). Plate and catalog photos copied to
`Knautia_maxima/`.

*Nymphaea caerulea* → *Nymphaea nouchali* (id 660, 2026-08-27). Same
genus; APG skipped. User chose the parent species as the catalog key
(WCVP accepted is *N. nouchali* var. *caerulea*). Photos `ncN` → `nnN`.
Author set to Burm.f. (from *N. nouchali*). Genus Nymphaea kept
(*N. alba*, *N. odorata*). Plate and catalog photos copied to
`Nymphaea_nouchali/`.

*Ophrys fuciflora* → *Ophrys holosericea* (id 385, 2026-08-27). Same
genus; APG skipped. User chose the parent species as the catalog key
(WCVP accepted is *O. holosericea* subsp. *holosericea*). Homonym
*O. fuciflora* (Crantz) Rchb.f. is illegitimate → same subspecies;
catalog author (F.W.Schmidt) Moench → accepted (Burm.f.) Greuter.
Photos `ofN` → `ohN`. Genus Ophrys kept (*O. apifera*, *O. insectifera*,
*O. sphegodes*). Plate and catalog photos copied to
`Ophrys_holosericea/`.

*Rhinanthus angustifolius* → *Rhinanthus major* (id 477, 2026-08-27).
Same genus; APG skipped. User chose the parent species as the catalog
key (WCVP accepted is *R. major* var. *major*). Photos `raN` → `rmN`.
Author C.C.Gmel. → L. Genus Rhinanthus kept (*R. alectorolophus*,
*R. minor*). Plate and catalog photos copied to `Rhinanthus_major/`.
Public observation photo copied.

*Citrus sinensis* → *Citrus × aurantium* (id 729, 2026-08-27). Same
genus; APG skipped. User chose the parent species as the catalog key
(WCVP accepted is *C. × aurantium* f. *aurantium*). Photos `csN` →
`caN`. Author (L.) Osbeck → L. Plate and catalog photos copied to
`Citrus_%C3%97_aurantium/`. English label stayed sweet orange.
