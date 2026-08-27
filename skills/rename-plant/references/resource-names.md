# GCS paths that still use a different Latin name

Catalog **key is already correct**. Plate, photos, and/or the
distribution map still live under an old synonym, spelling, or typo.
This is a GCS + URL remap, **not** `/rename-plant`.

Source: live `plants_v2` 2026-08-27 (1,421 species). 44 mismatches;
3 done. Website map path is
`{illustration_stem}_distribution.webp` next to the plate
(`web/src/api.js` `distributionRel`). No `distributionUrl` field.

Prefix: `https://storage.googleapis.com/abherbs-resources/photos/`.

After a fix: copy GCS (including `@1600` / `@400` / `_distribution` /
`.thumbnails`), HEAD 200, patch `plants_v2` `illustrationUrl` +
`photoUrls`, `plants_headers/{id}/url`, `web/catalog/{id}`, delete the
old folder, set `versions/db_update`, move the row to **Done**.
Leave Order/Family folders and the Firebase key alone unless asked.
When shipping a new plate, keep the **live basename** until that row
is remapped.

Do not mix this with APG Order/Family folder drift (Capparales vs
Brassicales, etc.).

## Done

| Catalog | Id | Old folder | When |
|---|---:|---|---|
| Anthericum ramosum | 41 | `Anthericum_amosum/` (missing r) | 2026-08-27 |
| Asarum europaeum | 60 | `Asarum_europaneum/` (extra n) | 2026-08-27 |
| Blitum bonus-henricus | 74 | `Chenopodium_bonus-henricus/` (`cbN` → `bbN`) | 2026-08-27 |

## 1. Folder still uses an old name

Illustration, photos, and map all sit in the old slug folder. Photo
prefix is usually the old initials too. Target folder slug = catalog
name with spaces → `_`. Remap photo prefix to
`plant.resolve.photo_prefix` unless asked to keep it.

| Id | Catalog | Current folder | Plate file | Photos | Map file | Resource name |
|---:|---|---|---|---|---|---|
| 129 | Clinopodium acinos | `Lamiales/Lamiaceae/Acinos_arvensis/` | `Acinos_arvensis.webp` | `aaN` | `Acinos_arvensis_distribution.webp` | Acinos arvensis |
| 143 | Crataegus germanica | `Rosales/Rosaceae/Mespilus_germanica/` | `Mespilus_germanica.webp` | `mgN` | `Mespilus_germanica_distribution.webp` | Mespilus germanica |
| 189 | Erigeron acris | `Asterales/Asteraceae/Erigeron_acer/` | `Erigeron_acer.webp` | `eaN` | `Erigeron_acer_distribution.webp` | Erigeron acer (gender) |
| 191 | Draba verna | `Capparales/Brassicaceae/Europhila_verna/` | `Erophila_verna.webp` | `evN` | `Erophila_verna_distribution.webp` | Erophila verna; folder typo Europhila |
| 214 | Frangula alnus | `Rosales/Rhamnaceae/Rhamnus_frangula/` | `Rhamnus_frangula.webp` | `rfN` | `Rhamnus_frangula_distribution.webp` | Rhamnus frangula |
| 289 | Jacobaea erucifolia | `Asterales/Asteraceae/Senecio_erucifolius/` | `Senecio_erucifolius.webp` | `seN` | `Senecio_erucifolius_distribution.webp` | Senecio erucifolius |
| 297 | Lamium galeobdolon | `Lamiales/Lamiaceae/Galeobdolon_luteum/` | `Galeobdolon_luteum.webp` | `glN` | `Galeobdolon_luteum_distribution.webp` | Galeobdolon luteum |
| 314 | Lepidium draba | `Capparales/Brassicaceae/Cardaria_draba/` | `Cardaria_draba.webp` | `cdN` | `Cardaria_draba_distribution.webp` | Cardaria draba |
| 325 | Lotus maritimus | `Fabales/Fabaceae/Tetragonolobus_maritimus/` | `Tetragonolobus_maritimus.webp` | `tmN` | `Tetragonolobus_maritimus_distribution.webp` | Tetragonolobus maritimus |
| 414 | Pilosella officinarum | `Asterales/Asteraceae/Hieracium_pilosella/` | `Hieracium_pilosella.webp` | `hpN` | `Hieracium_pilosella_distribution.webp` | Hieracium pilosella |
| 439 | Potentilla pusilla | `Rosales/Rosaceae/Potentilla_neumanniana/` | `Potentilla_verna.webp` | `pnN` | `Potentilla_verna_distribution.webp` | folder *P. neumanniana*; plate *P. verna* |
| 448 | Prunus avium | `Rosales/Rosaceae/Cerasus_avium/` | `Cerasus_avium.webp` | `caN` | `Cerasus_avium_distribution.webp` | Cerasus avium |
| 472 | Ranunculus trichophyllus | `Ranunculales/Ranunculaceae/Batrachium_trichophyllum/` | `Batrachium_trichophyllum.webp` | `btN` | `Batrachium_trichophyllum_distribution.webp` | Batrachium trichophyllum |
| 519 | Scorzoneroides autumnalis | `Asterales/Asteraceae/Leontodon_autumnalis/` | `Leontodon_autumnalis.webp` | `laN` | `Leontodon_autumnalis_distribution.webp` | Leontodon autumnalis |
| 528 | Jacobaea vulgaris | `Asterales/Asteraceae/Senecio_jacobaea/` | `Senecio_jacobaea.webp` | `sjN` | `Senecio_jacobaea_distribution.webp` | Senecio jacobaea |
| 647 | Calyptocarpus vialis | `Asterales/Asteraceae/Calyptocarpus_vitalis/` | `Calyptocarpus_vitalis.webp` | `cvN` | `Calyptocarpus_vitalis_distribution.webp` | vitalis (spelling) |
| 940 | Datura innoxia | `Solanales/Solanaceae/Datura_inoxia/` | `Datura_inoxia.webp` | `diN` | `Datura_inoxia_distribution.webp` | Datura inoxia (WCVP spelling) |
| 1129 | Salvia yangii | `Lamiales/Lamiaceae/Perovskia_atriplicifolia/` | `Perovskia_atriplicifolia.webp` | `paN` | `Perovskia_atriplicifolia_distribution.webp` | Perovskia atriplicifolia |
| 1140 | Melaleuca citrina | `Myrtales/Myrtaceae/Callistemon_citrinus/` | `Callistemon_citrinus.webp` | `ccN` | `Callistemon_citrinus_distribution.webp` | Callistemon citrinus |

Catalog-named `{Slug}_distribution.webp` in the catalog folder is 404
for every row above; the live map is the plate-stem file in the old
folder.

## 2. Illustration filename only

Folder and photo files already match the catalog name. Map inherits the
**plate stem**, so it is mismatched too.

| Id | Catalog | Folder (ok) | Plate file | Map file | Kind |
|---:|---|---|---|---|---|
| 49 | Arctium minus | `…/Arctium_minus/` | `Arctium_minor.webp` | `Arctium_minor_distribution.webp` | gender |
| 98 | Carum carvi | `…/Carum_carvi/` | `carum_carvi.webp` | derived `carum_carvi_distribution.webp` **404**; actual `Carum_carvi_distribution.webp` **200** | case; website map broken |
| 132 | Comarum palustre | `…/Comarum_palustre/` | `Potentilla_palustris.webp` | `Potentilla_palustris_distribution.webp` | synonym |
| 142 | Cotoneaster integerrimus | `…/Cotoneaster_integerrimus/` | `Cotoneaster_integerrima.webp` | `Cotoneaster_integerrima_distribution.webp` | gender |
| 300 | Lapsana communis | `…/Lapsana_communis/` | `Lampsana_communis.webp` | `Lampsana_communis_distribution.webp` | spelling |
| 305 | Lathyrus sylvestris | `…/Lathyrus_sylvestris/` | `Lathyrus_silvestris.webp` | `Lathyrus_silvestris_distribution.webp` | y/i |
| 374 | Neottia ovata | `…/Neottia_ovata/` | `neottia_ovata.webp` | `neottia_ovata_distribution.webp` | case |
| 406 | Persicaria lapathifolia | `…/Persicaria_lapathifolia/` | `Polygonum_lapathifolium.webp` | `Polygonum_lapathifolium_distribution.webp` | synonym |
| 428 | Polygala vulgaris | `…/Polygala_vulgaris/` | `Polygala_vulgare.webp` | `Polygala_vulgare_distribution.webp` | ending |
| 431 | Polygonatum verticillatum | `…/Polygonatum_verticillatum/` | `Polygonatum-verticillatum.webp` | `Polygonatum-verticillatum_distribution.webp` | hyphen |
| 474 | Reseda lutea | `…/Reseda_lutea/` | `Reseda_luteola.webp` | `Reseda_luteola_distribution.webp` | **wrong species** (luteola is catalog id 1141) |
| 476 | Rhinanthus alectorolophus | `…/Rhinanthus_alectorolophus/` | `Rhinanthus_alectolophorus.webp` | `Rhinanthus_alectolophorus_distribution.webp` | typo |
| 544 | Soldanella carpatica | `…/Soldanella_carpatica/` | `Soldanella_carpathica.webp` | `Soldanella_carpathica_distribution.webp` | spelling |
| 559 | Stachys sylvatica | `…/Stachys_sylvatica/` | `Stachys_silvatica.webp` | `Stachys_silvatica_distribution.webp` | y/i |
| 573 | Thalictrum aquilegiifolium | `…/Thalictrum_aquilegiifolium/` | `Thalictrum_aquilegifolium.webp` | `Thalictrum_aquilegifolium_distribution.webp` | missing i |
| 605 | Vaccinium vitis-idaea | `…/Vaccinium_vitis-idaea/` | `Vaccinium_vitis_idaea.webp` | `Vaccinium_vitis_idaea_distribution.webp` | hyphen vs `_` |
| 616 | Veronica anagallis-aquatica | `…/Veronica_anagallis-aquatica/` | `Veronica_anagallis.webp` | `Veronica_anagallis_distribution.webp` | truncated |

## 3. Photo prefix only

Plate folder, plate filename, and map already use the catalog name.

| Id | Catalog | Expected | Actual photos | From |
|---:|---|---|---|---|
| 27 | Anacamptis morio | `amN` | `omN` | Orchis morio |
| 28 | Lysimachia arvensis | `laN` | `aaN` | Anagallis arvensis |
| 92 | Capsella bursa-pastoris | `cbN` | `cbpN` | 3-letter from hyphenated epithet |
| 128 | Clematis vitalba | `cvN` | `caN` | origin unclear |
| 529 | Senecio ovatus | `soN` | `sfN` | Senecio fuchsii |
