# Ingest

Python catalog pipeline for What's that flower. Always run from this directory
with `.venv/bin/python`.

```
add_species.py     daily dry-run / incremental publish CLI
constants.py       local paths and Firebase constants
plant/             job packets: resolve, assemble, draft, media, validate
catalog/           filter indexes, APG tree, website catalog, publish, promote
sources/           WCVP, Wikidata, floras, Commons, GBIF, …
storage/           GCS upload and public ACL
scripts/           operator CLIs (photos, notifications, one-off patches)
tests/
data/              botanical_sources.json, maps, IPNI overrides
fixtures/          offline HTML/JSON for tests
```

```bash
cd ~/whatsthatflower/ingest
.venv/bin/python add_species.py "Genus epithet"
.venv/bin/python -m catalog.promote --patch /path/to/index_patch.json
.venv/bin/python -m catalog.refresh --input-dir DUMP --output-dir OUT
.venv/bin/python -m scripts.publish_web_catalog --from-live
.venv/bin/python -m unittest discover -s tests
```

Adding a species: [ADD_PLANT.md](ADD_PLANT.md). Plates: workspace `ILLUSTRATION.md`.
