# Add a plant to the live catalog

Follow this pipeline whenever the user asks to add a species (usually
“add *Latin name*” and optionally “with illustration *id*”). “Add it
to the database” is an explicit Firebase + GCS write after the packet
is reviewed.

Do **not** run a full index promote (`promote_indexes.py --apply`) unless
asked. One-plant adds are incremental on live. Do **not** call
`publish.publish()` twice (counts would double).

Python: `/Users/adrianbenko/PycharmProjects/abherbs-auto/.venv/bin/python`
(system `/usr/bin/python3` lacks BeautifulSoup). GCS uploads need
`GOOGLE_APPLICATION_CREDENTIALS` pointing at
`~/Development/Keystore/abherbs-backend-firebase-adminsdk-l5787-839f896846.json`.

Job packets: `~/whatsthatflower/plants/_jobs/{Genus_epithet}/`.
Latin name is the Firebase key (`plants_v2/{Latin name}`).

## 1. Dry-run packet

```bash
cd ~/whatsthatflower/ingest
.venv/bin/python add_species.py "Genus epithet" --illustration-id ID
```

If there is no illustration id yet, run without `--illustration-id`
(or resolve the plate first — see §2) so the job still builds.

This resolves WCVP / Wikidata / IPNI / GBIF, drafts English, fetches
illustration + Commons/GBIF photos, writes the job dir, and does **not**
touch Firebase.

If the name is already in `plants_to_update`, stop and say so.

## 2. Illustration

Plate from botanicalillustrations.org. Download is
`media/illustration_raw.jpg`.

**If the user gave an illustration id, use that.**

**If they did not**, search botanicalillustrations.org for the accepted
name, open the species gallery, and look at the available plates
(thumbnails / HD). Choose the one that best *represents the plant* —
typical flower colour and shape, readable habit, a clean colour plate
when possible. Prefer a diagnostic flowering shoot over fruit-only,
outline, analytic, or multi-species sheets. Do not blindly take the
first gallery hit or the auto `score_plate` rank; look at the pictures
and pick. Then fetch that id (re-run with `--illustration-id` or
download HD into the job). If there is no usable plate, say so and
stop before publish.

Clean with Imagine, prompt exactly:

> Clean up, make background white, remove all labels

Install with `media.import_imagine_result` as
`media/{Genus_epithet}.webp` and set `job.illustration.cleaner = imagine`.
PIL flatten is a fallback only.

## 3. Photos

3–5 photos, **flower first**. Skip fruit if there is none. Prefer
Commons with a license we can use; the filename/description must be
this species (binomial gate). Review every candidate — auto-pick is
often a macro, the wrong organ, or insect-damaged.

Typical set: flower, habit, leaf, fruit (if sourced). Process with
`media.process_photo` (512 WebP + thumbnail).

## 4. Traits (best guess from sources, then an editorial pass)

Auto-infer is a draft. Fix nonsense (height 30–30 cm from “spread 30 cm”,
green from leaves, etc.).

| Axis | Codes |
|---|---|
| color | 1 white, 2 yellow, 3 red, 4 blue-purple, 5 green |
| habitat | 1 meadow, 2 garden, 3 wetland, 4 woodland, 5 rock, 6 tree |
| petal | 1 four, 2 five, 3 many, 4 zygomorphic |
| distribution | WCVP TDWG L2 (native + introduced unless told otherwise) |

Height and flowering months from metric sources. Prefer metres/cm over
inches. Habitat codes must be backed by real habitat text (garden =
cultivated / RHS AGM; woodland = forest/woods; rock = rocky/scrub/cliff).

Toxicity class: do not invent; leave for human review if unsure.

## 5. APG browse path

`plants_v2.APGIV` must walk the **live** `APG IV_v3` tree, including extra
ranks already there (subfamily, tribe, section). Reuse
Digitalideae/Digitalis, Lilioideae/Lilium/Liriotypus, Lamioideae/Marrubieae,
etc. Do **not** create a sibling `Familia/Genus` next to a classified
subtree.

Check live children before publish. After publish, confirm the new id is
on the nested node and **not** as a stray family-level genus.

## 6. English (seven mandatory fields)

`isTranslated()` needs: `description`, `flower`, `inflorescence`, `fruit`,
`leaf`, `stem`, `habitat`. Inflorescence is mandatory for the app.

Rewrite the auto-draft. Rules:

- Multiple sources; short, accurate, easy to read.
- Up to 4 sentences per field, only if the sources have the facts.
- Do not invent.
- Do not repeat description facts in habitat.
- Habitat text must support the `filterHabitat` codes from sources.
- Skip culture, culinary, pet-toxicity, and other-species asides.
- `sourceUrls` on the English record: Wikipedia + the floras actually used.

Reliable sources (see `data/botanical_sources.json`): Wikipedia, PFAF,
RHS, Luontoportti, Missouri Plants, BOTANY.cz, EPPO (names). POWO is
Cloudflare-blocked; use local WCVP. When a new site is useful, add it to
the registry (`reliable: true` if it is a real flora).

## 7. Common names

Never translate an English common name. `label` / `names` only from:

- Wikidata label/alias (skip if it is the Latin name or a Latin synonym)
- that language’s Wikipedia title (if not Latin)
- EPPO Global Database common-name table (`https://gd.eppo.int/taxon/{code}`)
- a flora line such as BOTANY.cz *Česká / Slovenská jména*

If a language has no sourced name, **omit `label`**. The app shows Latin.
Do not draft SK/CS/RU/DE/FR/PL/JA/ES body texts unless asked.

## 8. Publish (only when asked to add to the database)

`validate.validate` must be ok. Then incremental live publish
(`publish.publish`):

1. Upload official WebP + thumbnails to
   `gs://abherbs-resources/photos/{order}/{family}/{slug}/`.
2. Write `plants_v2`, `plants_headers/{id}`, `synonyms`, `translations`.
3. `plants_to_update/list/{id} = Latin`, `count = id + 1`.
4. Write the slim website catalog: `web/catalog/{id}` (`id`, `name`, `family`, `url`, `illustrationUrl` from `plants_v2`) and `web/labels/{lang}/{id}` for each sourced vernacular (omit if that language has no `label`; never `*-GT` or Latin). Do not derive labels from `search_v3`.
5. `apply_apg_live` along the nested path.
6. Increment `counts_4_v2` and set `lists_4_v2` for every matching
   filter key (white plants also go on empty-color keys).
7. Update `search_v3` and `search_photo`. Search keys must not contain
   `./#$[]` (skip those names).
8. Set `versions/db_update` to today’s ISO date.

Do **not** rebuild staging `*_new` unless asked. Staging is for full
rebuilds.

## 9. Verify live

- `plants_v2/{Latin}.id` and `plants_headers/{id}`
- `web/catalog/{id}` has the same id, Latin name, and `illustrationUrl`
- `web/labels/en/{id}` matches the sourced English `label` (absent if none)
- English seven fields present
- photos and illustration publicly readable on GCS
- APG nested node includes the id; no stray sibling genus
- `search_v3/la/{latin lower}` has the id
- `plants_to_update/count` is next id

Same-day `versions/db_update` can leave the mobile app on yesterday’s
`once()` cache (color-page counts look stale). That is expected.

## 10. Afterward

Other languages, FCM, family icons, and a full promote are separate
asks. Rebuild the slim website catalog locally with
`publish_web_catalog.py --from-live`; add `--apply` only when asked to
write `web/catalog` and `web/labels`. If publish crashes after media +
records but during search, finish search/photo only — do not
re-increment counts.
