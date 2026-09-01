# GCS paths that still use a different Latin name

Catalog **key is already correct**. Plate, photos, and/or the
distribution map still live under an old synonym, spelling, or typo.
This is a GCS + URL remap, **not** `/rename-plant`.

Source: live `plants_v2` 2026-08-27 (1,421 species). 44 mismatches;
44 done. Website map path is
`{illustration_stem}_distribution.webp` next to the plate
(`web/src/api.js` `distributionRel`). No `distributionUrl` field.

Prefix: `https://storage.googleapis.com/abherbs-resources/photos/`.

After a fix: copy GCS (including `@1600` / `@400` / `_distribution` /
`.thumbnails`), HEAD 200, patch `plants_v2` `illustrationUrl` +
`photoUrls`, `plants_headers/{id}/url`, `web/catalog/{id}`, delete the
old folder, set `versions/db_update`, move the row to **Done**.
Leave the Firebase key alone unless asked. Order/Family GCS folders
must match live `plants_v2.APGIV` Ordo/Familia (see **4**).
When shipping a new plate, keep the **live basename** until that row
is remapped.

## Done

| Catalog | Id | Old folder | When |
|---|---:|---|---|
| Anthericum ramosum | 41 | `Anthericum_amosum/` (missing r) | 2026-08-27 |
| Asarum europaeum | 60 | `Asarum_europaneum/` (extra n) | 2026-08-27 |
| Blitum bonus-henricus | 74 | `Chenopodium_bonus-henricus/` (`cbN` → `bbN`) | 2026-08-27 |
| Clinopodium acinos | 129 | `Acinos_arvensis/` (`aaN` → `caN`) | 2026-08-31 |
| Crataegus germanica | 143 | `Mespilus_germanica/` (`mgN` → `cgN`) | 2026-08-31 |
| Erigeron acris | 189 | `Erigeron_acer/` (gender; `eaN` kept) | 2026-08-31 |
| Draba verna | 191 | `Europhila_verna/` (folder typo; plate *Erophila*; `evN` → `dvN`) | 2026-08-31 |
| Frangula alnus | 214 | `Rhamnus_frangula/` (`rfN` → `faN`) | 2026-08-31 |
| Jacobaea erucifolia | 289 | `Senecio_erucifolius/` (`seN` → `jeN`) | 2026-08-31 |
| Lamium galeobdolon | 297 | `Galeobdolon_luteum/` (`glN` → `lgN`) | 2026-08-31 |
| Lepidium draba | 314 | `Cardaria_draba/` (`cdN` → `ldN`) | 2026-08-31 |
| Lotus maritimus | 325 | `Tetragonolobus_maritimus/` (`tmN` → `lmN`) | 2026-08-31 |
| Pilosella officinarum | 414 | `Hieracium_pilosella/` (`hpN` → `poN`) | 2026-08-31 |
| Potentilla pusilla | 439 | `Potentilla_neumanniana/` (plate *P. verna*; `pnN` → `ppN`) | 2026-08-31 |
| Prunus avium | 448 | `Cerasus_avium/` (`caN` → `paN`) | 2026-08-31 |
| Ranunculus trichophyllus | 472 | `Batrachium_trichophyllum/` (`btN` → `rtN`) | 2026-08-31 |
| Scorzoneroides autumnalis | 519 | `Leontodon_autumnalis/` (`laN` → `saN`) | 2026-08-31 |
| Jacobaea vulgaris | 528 | `Senecio_jacobaea/` (`sjN` → `jvN`) | 2026-08-31 |
| Calyptocarpus vialis | 647 | `Calyptocarpus_vitalis/` (spelling; `cvN` kept) | 2026-08-31 |
| Datura innoxia | 940 | `Datura_inoxia/` (WCVP spelling; `diN` kept) | 2026-08-31 |
| Salvia yangii | 1129 | `Perovskia_atriplicifolia/` (`paN` → `syN`) | 2026-08-31 |
| Melaleuca citrina | 1140 | `Callistemon_citrinus/` (`ccN` → `mcN`) | 2026-08-31 |
| Arctium minus | 49 | plate `Arctium_minor.webp` (gender) | 2026-08-31 |
| Carum carvi | 98 | plate `carum_carvi.webp` (case; map already `Carum_carvi_distribution.webp`) | 2026-08-31 |
| Comarum palustre | 132 | plate `Potentilla_palustris.webp` (synonym) | 2026-08-31 |
| Cotoneaster integerrimus | 142 | plate `Cotoneaster_integerrima.webp` (gender) | 2026-08-31 |
| Lapsana communis | 300 | plate `Lampsana_communis.webp` (spelling) | 2026-08-31 |
| Lathyrus sylvestris | 305 | plate `Lathyrus_silvestris.webp` (y/i) | 2026-08-31 |
| Neottia ovata | 374 | plate `neottia_ovata.webp` (case) | 2026-08-31 |
| Persicaria lapathifolia | 406 | plate `Polygonum_lapathifolium.webp` (synonym) | 2026-08-31 |
| Polygala vulgaris | 428 | plate `Polygala_vulgare.webp` (ending) | 2026-08-31 |
| Polygonatum verticillatum | 431 | plate `Polygonatum-verticillatum.webp` (hyphen) | 2026-08-31 |
| Reseda lutea | 474 | plate `Reseda_luteola.webp` in lutea folder (filename only; *R. luteola* id 1141 untouched) | 2026-08-31 |
| Rhinanthus alectorolophus | 476 | plate `Rhinanthus_alectolophorus.webp` (typo) | 2026-08-31 |
| Soldanella carpatica | 544 | plate `Soldanella_carpathica.webp` (spelling) | 2026-08-31 |
| Stachys sylvatica | 559 | plate `Stachys_silvatica.webp` (y/i) | 2026-08-31 |
| Thalictrum aquilegiifolium | 573 | plate `Thalictrum_aquilegifolium.webp` (missing i) | 2026-08-31 |
| Vaccinium vitis-idaea | 605 | plate `Vaccinium_vitis_idaea.webp` (hyphen vs `_`) | 2026-08-31 |
| Veronica anagallis-aquatica | 616 | plate `Veronica_anagallis.webp` (truncated) | 2026-08-31 |
| Anacamptis morio | 27 | photos `omN` → `amN` (Orchis morio) | 2026-08-31 |
| Lysimachia arvensis | 28 | photos `aaN`/`aa.webp` → `laN`/`la.webp` (Anagallis arvensis) | 2026-08-31 |
| Capsella bursa-pastoris | 92 | photos `cbpN` → `cbN` (3-letter hyphen) | 2026-08-31 |
| Clematis vitalba | 128 | photos `caN` → `cvN` | 2026-08-31 |
| Senecio ovatus | 529 | photos `sfN` → `soN` (Senecio fuchsii) | 2026-08-31 |

## 1. Folder still uses an old name

Illustration, photos, and map all sit in the old slug folder. Photo
prefix is usually the old initials too. Target folder slug = catalog
name with spaces → `_`. Remap photo prefix to
`plant.resolve.photo_prefix` unless asked to keep it.

None remaining.

## 2. Illustration filename only

Folder and photo files already match the catalog name. Map inherits the
**plate stem**, so it is mismatched too.

None remaining.

## 3. Photo prefix only

Plate folder, plate filename, and map already use the catalog name.

None remaining.

## 4. APG Order/Family folder drift

GCS `{Order}/{Family}/{Slug}/` must match `plants_v2.APGIV` Ordo and
Familia. Catalog key, slug, plate stem, and photo prefix stay.
`plants_headers.family` already matched APG. Live scan 2026-08-31:
49 plants; **49 done**.

| Kind | n | When |
|---|---:|---|
| Family folder (6 also moved order) | 24 | 2026-08-31 |
| Order folder only (family already APG) | 25 | 2026-08-31 |

Family moves: Liliaceae→Asparagaceae (4), Scrophulariaceae→Plantaginaceae
(4), Fumariaceae→Papaveraceae (3), Scrophulariaceae→Orobanchaceae (2),
Tiliaceae→Malvaceae (2), Valerianaceae→Caprifoliaceae (2), plus one each
Araceae→Acoraceae, Eleagnaceae→Elaeagnaceae, Hippuridaceae→Plantaginaceae,
Apiaceae→Araliaceae, Saxifragaceae→Celastraceae, Caprifoliaceae→Adoxaceae,
Liliaceae→Melanthiaceae.

Order-only: Capparales→Brassicales (21 Brassicaceae), Myrtales→Malvales
(3 *Daphne*), Linales→Malpighiales (*Linum catharticum*).
