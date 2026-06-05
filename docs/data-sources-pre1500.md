# yearl-e data sources catalog — PRE-1500 + all-era boundaries (1000 BCE – 1500 CE)

Generated 2026-06-05 from a deep-research survey (search phase salvaged after the
verify phase crashed). Extends `data-sources.md` (which stops at 1500) into the
ancient + medieval gap. Scope per user: **scoring data + region boundaries only**
(narrative sources skipped). Every entry below was surfaced by web search and most
were adversarially verified before the harness died; treat unverified ones as
"needs a confirming fetch before integration."

---

## ★ KEYSTONE — Cliopatria (Seshat geospatial)

The single biggest find. Reframes the whole boundary + granularity problem.

- **What:** year-keyed GeoJSON of ~1,600 worldwide political entities, **3400 BCE – 2024 CE**.
- **Repo:** https://github.com/Seshat-Global-History-Databank/cliopatria
- **Archive:** Zenodo record 13363121 · **Paper:** Nature Scientific Data (PMC11822181), peer-reviewed.
- **License:** **CC-BY 4.0** (fully open, commercial OK).
- **Format:** single `cliopatria.geojson`, EPSG:4326, ~14,000 rows.
- **Lookup:** each row has `FromYear`/`ToYear`; polygon for any `(entity, year)` = the row whose range contains the year. Ranges per entity are non-overlapping → deterministic. Maps *directly* onto our `(region, year)` grid.
- **Join keys:** `SeshatID` → links polygons to Seshat governance data; `Wikidata` IDs → links to rulers/events.
- **Caveats:** coverage gaps exist (lookup returns "if any"); borders carry unquantified uncertainty; reflects one territorial interpretation.

**Why it matters for our goals:**
1. Solves period-accurate boundaries for the *entire* 1000 BCE–2026 vision in one file — replaces modern-only Natural Earth and the crude aourednik basemaps.
2. Lets regions be defined as **real polities per era** instead of hand-grouped modern countries → the granularity + coverage control the user asked for.
3. `SeshatID` is a ready-made join to governance scoring; `Wikidata` to everything else.

---

## Section B — Other boundary / polygon sources

#### OpenHistoricalMap (OHM)
- URL: https://www.openhistoricalmap.org · wiki: OSM Wiki / OpenHistoricalMap
- Coverage: **4001 BCE – present**; OSM-style crowd-edited, time-versioned features.
- Dates: ISO 8601 + EDTF (`start_date:edtf`/`end_date:edtf`) supporting uncertainty/approximation; tiles filter on `start_decdate`/`end_decdate`.
- Model: intentionally multiple features per place across time, grouped by `chronology` relations.
- License: ODbL (open). Format: vector tiles / OSM export / Overpass.
- Map to grid: query features active in target year; quality varies by how well-mapped a region is. Complements Cliopatria where Cliopatria has gaps.

#### DARMC / Mapping Past Societies (MAPS) — Harvard
- URL: https://darmc.harvard.edu/data-availability · Dataverse: dataverse.harvard.edu/dataverse/darmc
- Coverage: Roman + medieval world; many themed layers (e.g. "France: Diocese & Archdiocese Boundaries ca. 1000", MAPS Scholarly Data Series 2013-4).
- License: free/open with attribution ("free to download and use… as long as you acknowledge MAPS").
- Format: shapefiles. (darmc.harvard.edu returned 403 to the bot; access via Dataverse.)
- Map to grid: snapshot polygons at specific dates; best for fine ecclesiastical/administrative detail in Europe + Mediterranean.

#### CHGIS v6 — China Historical GIS (already in main catalog, pre-1500 confirmed)
- URL: http://www.fas.harvard.edu/~chgis/data/chgis/v6/
- Coverage: **221 BCE – 1911 CE**; Harvard-Yenching + Fudan. Free. Admin units + populated places.
- Map to grid: subnational China detail for every era — fills han_china granularity.

#### HGIS de las Indias
- URL: https://www.hgis-indias.net
- Coverage: 1701–1808, colonial Spanish America; base maps at 1701/1750/1800.
- License: free. Format: GIS. Tangential to pre-1500 but fills New Spain / Andes / Río de la Plata detail in early-modern.

#### (rejected) World Historical Gazetteer — place-name gazetteer, NOT polygons; post-1500 focus. Skip for boundaries.
#### (rejected) Thinkquest archived world shapefiles 2000 BCE–1994 — ±40 mi error, site defunct since 2013. Low reliability.

---

## Section 1 — Pre-1500 scoring data

### 1.3 Conflict / safety

#### Historical Conflict Event Dataset (HCED) ★
- Coverage: **~8,800 battles/sieges, 1468 BCE – 2003 CE**, with coordinates, year, participants.
- The direct pre-1400 successor to the already-integrated Brecke catalog.
- Map to grid: count active conflicts per `(region, year)` exactly like Brecke; covers the full ancient+medieval span Brecke misses.

#### HiSCoD — Historical Social Conflict Database
- Coverage: **20,000+ revolts/rebellions, c. 1000 – 1870 CE**, 25+ countries. Free CSV.
- Captures *internal* violence (rebellion sub-factor) that HCED's interstate battles miss.

#### Leeson & Russ "Witch Trials" replication repo (also conflict-adjacent)
- CSV `battles.csv` + `trials.csv`, geocoded to GADM adm0/1/2 + lon/lat.
- Economic Journal 2018, DOI 10.1111/ecoj.12498. Open CSV.

#### Supporting: OWID long-run conflict deaths (global normalizer); PNAS early-farmer/bioarchaeology trauma corpus (only credible violence proxy for deep prehistory near the 1000 BCE edge).

### 1.4 Governance / state capacity

#### Extended State History Index / "Statehist" (Borcan, Olsson & Putterman 2018) ★
- Coverage: **~3500 BCE – 2000 CE**, modern-country territories, fixed **50-year bins**, state-presence/capacity score. Free Excel.
- Nearly drop-in for our `(region, year)` grid — modern-country + 50-yr structure maps almost directly.

#### Seshat Equinox2020
- Zenodo DOI 10.5281/zenodo.6642229. ~10,000 yrs, 1,500+ variables; strongest single quantitative governance source for 1000 BCE–1500 CE. Joins to Cliopatria via `SeshatID`.
- **License caveat: CC-BY-NC-SA** — non-commercial clause must be cleared for a public game. (Cliopatria itself is CC-BY 4.0; the governance *values* are the NC part.)

#### Supporting: State Capacity in Imperial China 997–1911 (fiscal/bureaucratic, fills medieval China cell); NBER w34370 "Historical Government" (polity-type crosswalk to harmonize codings).

### 1.1 Economy

#### Broadberry et al. British Economic Growth 1270–1870 (Warwick CAGE)
- Downloadable Excel, **annual GDP/population/output from 1270**. The pre-1500 national-accounts extension not yet integrated.

#### ML-augmented historical GDP (PNAS 2024 / arXiv:2505.09399)
- Region-year GDP for hundreds of European regions over ~700 years; published data. A **subnational** successor to Maddison — directly supports finer regions.

#### Allen — Roman/Diocletian real wages (Nuffield, Oxford)
- Welfare-ratio living standards anchored at **301 CE** (Diocletian's Price Edict) + Roman Egypt; same silver-grams metric as modern wage series. Empire-level point estimate, not fine grid.

#### Foldvári & van Leeuwen — ancient per-capita GDP (Review of Income & Wealth 2012)
- 1990 G-K benchmarks for **Mesopotamia, Athens, Rome, Italy, Levant**; Mesopotamia ~700–750 G-K $ in 5th c. BCE. Reaches the 1000 BCE–0 CE window. Peer-reviewed.

#### Hellenistic-world per-capita income (ROIW) — ancient income reconstruction into the 1000 BCE–0 window.

### 1.2 Health / demography

#### Global History of Health Project (GHHP) — European Module "Backbone of Europe" ★
- URL: economics.osu.edu/european-module · **Excel, open**, with codebook.
- Skeletal **Health Index** for 15,000+ individuals, 103 sites, **3rd–19th c. CE**, region-tagged, era-binned. Peer-reviewed.
- Serves health (stature, malnutrition/stress, infection) + safety (skeletal trauma).

#### GHHP Western Hemisphere & Asia Modules
- economics.osu.edu/global-history-health-project — same codebook, Americas (~12,000 individuals, **4000 BCE–present**) + Asia. Fills the non-European pre-1500 health grid.

#### Koepke & Baten — Near East & Europe stature 10,000–1000 BC (Springer s12520-019-00850-3)
- Bayesian spatiotemporal stature surface; uniquely covers the **10000–1000 BCE** deep-antiquity edge.

#### Galofré-Vilà et al. — heights in England, last 2,000 years (Southampton ePrints 418382)
- Rare continuous Roman-to-present single-region series; medieval famine/plague shocks show as height declines.

#### Roosen & Curtis — open georeferenced plague datasets (Biraben re-digitization + Sticker), PMC5749453
- Machine-readable `(place, year)` plague outbreak records, Second Pandemic **1347+** — right format/era for medieval epidemic scoring.

#### Note: data here is **era-binned, not annual** — use period buckets, not per-year. OWID Famines starts ~1870 (modern only).

### 1.5 Religion / tolerance

#### Anti-Jewish persecution dataset (Koyama et al., "Persecution & Weather Shocks", Econ Journal 2017)
- **1,366 events (821 expulsions, 545 pogroms), 936 European cities, 1100–1800**, city-level 5-year panels, from Encyclopaedia Judaica. Maps directly to `(region, year)` tolerance.
- Caveat: Europe-only, Jewish-minority-only — a regional supplement, not a global tolerance index. Machine-readable panel is in journal replication files; article PDF free at GMU mirror.

#### Leeson & Russ "Witch Trials" (Economic Journal 2018, DOI 10.1111/ecoj.12498)
- `trials.csv`: per-record persons tried + killed, geocoded GADM adm0/1/2 + lon/lat, **1343–1737**, multi-country Europe (EST, FIN, HUN, NOR, CHE, DEU). Open CSV in repo.

---

## Integration priority (recommendation)

1. **Cliopatria** → period boundaries for all eras + region-definition backbone. (CC-BY 4.0, low friction.)
2. **HCED + HiSCoD** → pre-1500 conflict (drop-in alongside Brecke).
3. **Statehist** → pre-1500 governance (50-yr bins, modern-country grid).
4. **GHHP Health Index** → pre-1500 health (era buckets).
5. **Foldvári-van Leeuwen + Broadberry + ML-GDP** → pre-1500 economy.
6. Religion (anti-Jewish persecution, witch trials) → Europe-only supplement; needs a global complement for non-European regions.

**Open license flag:** Seshat Equinox2020 governance values are CC-BY-NC-SA (non-commercial) — clear or avoid for a public game. Cliopatria *polygons* are clean CC-BY 4.0.
