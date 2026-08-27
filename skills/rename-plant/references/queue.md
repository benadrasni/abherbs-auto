# Catalog names that are not WCVP-accepted as written

Source: live `plants_to_update` vs `wcvp/wcvp.sqlite` (2026-08-25).
Catalog count 1421. Authority is current WCVP; re-check `wcvp.lookup`
before `--apply`. After a successful rename, move the row to **Done**.

## Done

| Catalog | Id | Accepted | When |
|---|---:|---|---|
| Acca sellowiana | 892 | Feijoa sellowiana | 2026-08-25 |
| Anemone narcissiflora | 32 | Anemonastrum narcissiflorum | 2026-08-25 |
| Anemonella thalictroides | 1372 | Thalictrum thalictroides | 2026-08-25 |
| Aphanes arvensis | 44 | Alchemilla arvensis | 2026-08-25 |
| Balsamorhiza sagittata | 952 | Wyethia sagittata | 2026-08-25 |
| Calystegia sepium | 84 | Convolvulus sepium | 2026-08-25 |
| Centranthus ruber | 1137 | Valeriana rubra | 2026-08-25 |
| Chamerion angustifolium | 112 | Epilobium angustifolium | 2026-08-25 |
| Consolida regalis | 134 | Delphinium consolida | 2026-08-25 |
| Conyza canadensis | 137 | Erigeron canadensis | 2026-08-25 |
| Ficaria verna | 206 | Ranunculus ficaria | 2026-08-25 |
| Filago minima | 207 | Logfia minima | 2026-08-25 |
| Globularia punctata | 920 | Globularia bisnagarica | 2026-08-25 |
| Gnaphalium sylvaticum | 250 | Omalotheca sylvatica | 2026-08-25 |
| Gypsophila muralis | 253 | Psammophiliella muralis | 2026-08-25 |
| Hibiscus moscheutos | 754 | Muenchhusia moscheutos | 2026-08-25 |
| Hyssopus officinalis | 1003 | Dracocephalum officinale | 2026-08-25 |
| Inula salicina | 285 | Pentanema salicinum | 2026-08-25 |
| Justicia americana | 697 | Dianthera americana | 2026-08-25 |
| Lavatera thuringiaca | 1029 | Malva thuringiaca | 2026-08-25 |
| Leopoldia comosa | 1096 | Muscari comosum | 2026-08-25 |
| Kosteletzkya virginica | 707 | Kosteletzkya pentacarpos | 2026-08-25 |
| Lychnis flos-cuculi | 329 | Silene flos-cuculi | 2026-08-25 |
| Matricaria recutita | 345 | Matricaria chamomilla | 2026-08-26 |
| Mycelis muralis | 365 | Lactuca muralis | 2026-08-26 |
| Myosoton aquaticum | 369 | Stellaria aquatica | 2026-08-26 |
| Papaver argemone | 398 | Roemeria argemone | 2026-08-26 |
| Polygala chamaebuxus | 426 | Chamaebuxus unguiculata | 2026-08-26 |
| Polygala lutea | 777 | Senega lutea | 2026-08-26 |
| Polygaloides paucifolia | 778 | Chamaebuxus paucifolia | 2026-08-26 |
| Potentilla anserina | 53 | Argentina anserina | 2026-08-26 |
| Prunus dulcis | 850 | Prunus amygdalus | 2026-08-26 |
| Rosmarinus officinalis | 852 | Salvia rosmarinus | 2026-08-26 |
| Rubus plicatus | 495 | Rubus fruticosus | 2026-08-26 |
| Scrophularia umbrosa | 521 | Scrophularia oblongifolia | 2026-08-26 |
| Securigera varia | 524 | Coronilla varia | 2026-08-26 |
| Silene viscaria | 538 | Viscaria vulgaris | 2026-08-26 |
| Sinapis arvensis | 540 | Mutarda arvensis | 2026-08-26 |
| Sorbus aria | 549 | Aria edulis | 2026-08-26 |
| Sorbus torminalis | 551 | Aria torminalis | 2026-08-26 |
| Stachys officinalis | 556 | Betonica officinalis | 2026-08-26 |
| Stellaria holostea | 562 | Rabelera holostea | 2026-08-26 |
| Thlaspi caerulescens | 1092 | Noccaea caerulescens | 2026-08-26 |
| Thlaspi perfoliatum | 577 | Noccaea perfoliata | 2026-08-26 |
| Atropa belladonna | 66 | Atropa bella-donna | 2026-08-26 |
| Cirsium acaule | 122 | Cirsium acaulon | 2026-08-26 |
| Dahlia × pinnata | 1155 | Dahlia pinnata | 2026-08-26 |
| Hibiscus rosa-sinensis | 954 | Hibiscus × rosa-sinensis | 2026-08-26 |
| Paeonia suffruticosa | 809 | Paeonia × suffruticosa | 2026-08-26 |
| Pentanema britannicum | 1253 | Pentanema britannica | 2026-08-26 |
| Pseudofumaria lutea | 658 | Pseudo-fumaria lutea | 2026-08-26 |
| Spirodela polyrrhiza | 554 | Spirodela polyrhiza | 2026-08-26 |
| Consolida ajacis | 825 | Delphinium ajacis | 2026-08-26 |

## Pending 1:1 (species)

Synonym or illegitimate; accepted rank Species; target not already in
the catalog. Safe to run through `/rename-plant` after the SKILL.md
gates (especially APG if the genus changes).

| Catalog | Id | WCVP | Accepted | Note |
|---|---:|---|---|---|

## Pending spelling

Catalog string is missing from WCVP; the intended taxon **is** accepted
under the spelling on the right. Rename is a slug/hyphen/× fix, not a
synonym move.

| Catalog | Id | WCVP accepted spelling |
|---|---:|---|

## Stop (not a 1:1 rename)

Do not `--apply` until the user chooses a species-rank key.

| Catalog | Id | WCVP target | Why |
|---|---:|---|---|
| Taraxacum officinale | 569 | Taraxacum sect. Taraxacum | Accepted is a section, not a species |
| Bryonia dioica | 75 | Bryonia cretica subsp. dioica | Accepted rank subspecies |
| Euphrasia rostkoviana | 204 | Euphrasia officinalis subsp. pratensis | Accepted rank subspecies |
| Knautia dipsacifolia | 292 | Knautia maxima subsp. maxima | Author Kreutzer; accepted rank subspecies |
| Nymphaea caerulea | 660 | Nymphaea nouchali var. caerulea | Accepted rank variety |
| Ophrys fuciflora | 385 | Ophrys holosericea subsp. holosericea | Accepted rank subspecies |
| Rhinanthus angustifolius | 477 | Rhinanthus major var. major | Accepted rank variety |
| Citrus sinensis | 729 | Citrus × aurantium | Synonym of a hybrid forma; sweet vs sour orange |

*Citrus × sinensis* (with ×) is also a WCVP synonym of *Citrus × aurantium*,
not an accepted spelling of the catalog name.
