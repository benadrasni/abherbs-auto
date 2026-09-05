# Add a plant to the live catalog

Follow this pipeline whenever the user asks to add a species (usually
“add *Latin name*” and optionally “with illustration *id*”). “Add it
to the database” is an explicit Firebase + GCS write after the packet
is reviewed. The packet includes a WCVP distribution map (see §2a).

Do **not** run a full index promote (`python -m catalog.promote --apply`) unless
asked. One-plant adds are incremental on live. Do **not** call
`catalog.publish.publish()` twice (counts would double).

Python: `/Users/adrianbenko/PycharmProjects/abherbs-auto/.venv/bin/python`
(system `/usr/bin/python3` lacks BeautifulSoup). GCS uploads need
`GOOGLE_APPLICATION_CREDENTIALS` pointing at
`~/Development/Keystore/abherbs-backend-firebase-adminsdk-l5787-839f896846.json`.

Job packets: `~/whatsthatflower/plants/_jobs/{Genus_epithet}/`.
Latin name is the Firebase key (`plants_v2/{Latin name}`).

Layout: `plant/` (job packets, media), `catalog/` (indexes, publish),
`sources/`, `storage/`, `scripts/` (operator CLIs). See [README.md](README.md).

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

Follow `/add-illustrations` (skill
`.grok/skills/add-illustrations/SKILL.md`). That is the plate
procedure: pick, clean / colorize / generate, install official WebPs,
review grid, ship. Locked look: `ILLUSTRATION.md`. A new-species add
still needs the official plate in the job before §8.

## 2a. Distribution map

Follow `/add-distribution-map` (skill
`.grok/skills/add-distribution-map/SKILL.md`). Build
`{slug}_distribution.webp` into the job `media/` from WCVP L3 (same
basename as the plate stem). Show the WebP in the review. A
new-species add needs that file in the job before §8; `plant.validate`
refuses publish without it. Incremental publish uploads it next to the
plate. The website derives the path from `illustrationUrl`
(`distributionRel`) — do not add `distributionUrl`.

## 3. Photos

3–5 photos, **flower first**. Skip fruit if there is none. Prefer
Commons with a license we can use; the filename/description must be
this species (binomial gate). Review every candidate — auto-pick is
often a macro, the wrong organ, or insect-damaged.

Typical set: flower, habit, leaf, fruit (if sourced). Process with
`plant.media.process_photo` (512 WebP + thumbnail).

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
inches. RHS “0.5–1 m” is often **spread**, not height — do not copy
spread into `heightTo`. Flowering months are the overlap of floras, not
the single widest interval (especially if it runs into the sourced seed
months). Habitat codes must be backed by real habitat text (garden =
cultivated / RHS AGM; woodland = forest/woods; rock = rocky/scrub/cliff).

Toxicity class: `0` = no poison badge (website “None recorded”), `1`
poisonous, `2` slightly poisonous. Do not invent. Contact rash / sap
irritation from a source such as PFAF goes in translations `toxicity`
text, **not** class 1 or 2. Leave class `0` if only handling irritation
is sourced; leave the class for human review if ingestion poison is
unclear.

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
- `description` around 50 words (habit, range, introductions).
  Other six fields: up to 4 sentences, only if the sources have the facts.
- Do not invent.
- Lead native range with local WCVP (POWO stand-in), not Wikipedia’s
  broader wording. A *sensu lato* / traditional range may follow as a
  second sentence when the species complex was split.
- Do not mix measurements from split-off taxa or from a broader concept
  into the accepted-name description.
- Involucre width is not the flowering-head / disc diameter. Name the
  organ. RHS “heads to 2 cm” and a flora involucre of 6–10 mm can both
  be true; do not collapse them into one number.
- Do not repeat description facts in habitat.
- Habitat text must support the `filterHabitat` codes from sources.
- Skip culture, culinary, pet-toxicity, and other-species asides from
  the seven fields. Culinary and traditional medicinal use go in
  optional `herbalism` (UI: Uses): up to 4 sentences, sourced, no
  doses, no “treats X”. Historical use in past or traditional voice.
  Do not invite ingestion of a poisonous plant. `/update-plant` leaves
  live `herbalism` unchanged. Human contact irritation may go in
  optional `toxicity` text (see §4).
- `sourceUrls` on the English record: English Wikipedia + the floras
  actually used for that English text. Do not put source names in
  brackets in the seven fields or `toxicity`.
- After the rewritten `inflorescence` paragraph, set
  `plants_v2.inflorescenceType` with `plant.inflorescence_type.classify`
  (keys in `TYPES` / `app/docs/DATA_MODEL.md`). Array, primary first.
  Empty `[]` if none of the 17 diagrams apply (solitary flower, catkin,
  unnamed cluster). Dry-run `apply_inference` classifies the auto-draft;
  re-run after editorial English and write `plants_v2.json`. Review
  compound vs simple (umbel / spike), and flowering head → `capitulum`
  not `head`. Do not invent keys. Publish writes the whole `plants_v2`
  record; RTDB omits an empty array.

Reliable sources (see `data/botanical_sources.json`): Wikipedia, PFAF,
RHS, Luontoportti, Missouri Plants, BOTANY.cz, Flóra Slovenska (Slovak
body text; bibdigital volumes under `flora_slovenska`), Flora Iberica
(Iberian/Balearic), Jagiellonian University Repository (RUJ,
https://ruj.uj.edu.pl/; Central Europe WCVP L2 11/13/14), EPPO (names).
POWO is Cloudflare-blocked; use local WCVP. When a new site is useful,
add it to the registry (`reliable: true` if it is a real flora).
Central Europe / Poland: RUJ (`libraries.ruj` / work `ruj`; search the
Latin name, e.g. *Aconitum moldavicum*); RCIN dLibra (`libraries.rcin`);
the Flora Polska work (`flora_polska`) is a hint only until a volume is
used.

Registry shape: `libraries` (bibdigital cite/browse) and `sources`
(works). A work has `kind` (flora / encyclopedia / checklist / garden /
names), `roles`, `fetch` (pipeline / latin / search / manual), and
`when` (`always`, `genera`, `l3`, `wcvp_l2`). Multi-volume floras list
`volumes` with `families`; job review hints the matching volume’s
`idurl`, not the whole series. Do not add the 1000+ bibdigital Flora
search hits as sources.

## 7. Common names

Never translate an English common name. `label` / `names` only from:

- Wikidata label/alias (skip if it is the Latin name or a Latin synonym)
- that language’s Wikipedia title (if not Latin)
- EPPO Global Database common-name table (`https://gd.eppo.int/taxon/{code}`)
- a flora line such as BOTANY.cz *Česká / Slovenská jména* or Flóra Slovenska

If a language has no sourced name, **omit `label`**. The app shows Latin.
Do not draft CS/RU/DE/FR/PL/JA/ES body texts unless asked.

`translations/{lang}/{Latin}/sourceUrls` lists pages **for that language**
that were actually used (that language’s Wikipedia, Wikidata, EPPO names
for that language, floras in that language). Do not copy
`translations/en` `sourceUrls` onto another language.

## 7a. Slovak (always)

After English is rewritten, write `translations/sk.json` with the same
seven fields from the same sourced facts. `label` / `names` only from a
Slovak source (Wikidata, sk.wikipedia title, EPPO, BOTANY.cz *Slovenská
jména*, Flóra Slovenska). Omit `label` if none. Do not translate an English vernacular.
Diagnostic contrasts may use `<b>…</b>`. `sourceUrls` follow §7 (Slovak
pages: Wikidata, sk.wikipedia, EPPO, BOTANY.cz, Flóra Slovenska,
pladias.sk). The file goes live only with incremental publish.

## 8. Publish (only when asked to add to the database)

Plate-only replacement for a species already in the catalog is
`/add-illustrations` (ship), not this full publish.

`plant.validate.validate` must be ok. Then incremental live publish
(`catalog.publish.publish`):

1. Upload official plate WebPs, `{slug}_distribution.webp`, and photo
   thumbnails to
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
- `plants_v2/{Latin}.inflorescenceType` matches the rewritten English
  inflorescence (absent in RTDB when none of the 17 apply)
- photos, illustration, and `{stem}_distribution.webp` publicly readable on GCS
- APG nested node includes the id; no stray sibling genus
- `search_v3/la/{latin lower}` has the id
- `plants_to_update/count` is next id

Same-day `versions/db_update` can leave the mobile app on yesterday’s
`once()` cache (color-page counts look stale). That is expected.

## 10. Afterward

Other languages, FCM, family icons, and a full promote are separate
asks. Rebuild the slim website catalog locally with
`python -m scripts.publish_web_catalog --from-live`; add `--apply` only when asked to
write `web/catalog` and `web/labels`. If publish crashes after media +
records but during search, finish search/photo only — do not
re-increment counts.

To patch live English, filters, or `plants_v2` after a first publish
(or for any species already in the catalog), follow `/update-plant`.
Do **not** call `catalog.publish.publish()` again (counts and
`plants_to_update` would double).
