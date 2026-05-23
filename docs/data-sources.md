# yearl-e data sources catalog (1500–2026)

Generated 2026-05-23 from research survey. Reference for integration work.

---

## Section 1 — Quantitative datasets

### 1.1 Economy

#### Maddison Project Database 2023 (already integrated)
- Home: https://www.rug.nl/ggdc/historicaldevelopment/maddison/releases/maddison-project-database-2023
- Coverage: 1 AD – 2022 (sparse pre-1500, dense post-1820); 169 countries; country
- Variables: GDP per capita (2011 int. $), population
- License: CC BY 4.0
- Format: XLSX, Stata
- Direct URL: https://dataverse.nl/api/access/datafile/421302 (xlsx), 421303 (dta)
- Effort: Already integrated.

#### Penn World Table 11.0
- Home: https://www.rug.nl/ggdc/productivity/pwt/  (also https://cid.ucdavis.edu/pwt)
- Coverage: 1950–2023; 185 countries; country
- Variables: Real GDP, GDP per capita, output-side and expenditure-side measures, employment, capital stock, TFP, exchange rates, PPP
- License: Free for research
- Format: XLSX, Stata; CSV via FRED
- Effort: Low. Best modern-era complement to Maddison.

#### Clio-Infra (umbrella, ~86 indicators)
- Home: https://clio-infra.eu/
- Coverage: mostly 1500–2010; 224 countries/regions
- Variables: GDP/capita, life expectancy, infant mortality, height, real wages, prices, urbanization, literacy, numeracy, gender, finance, agriculture
- License: Free academic (CC)
- Format: Compact XLSX per indicator
- Effort: Low to medium. **Highest-value source besides Maddison.**

#### Allen-Unger Global Commodity Prices Database
- Home: https://datasets.iisg.amsterdam/dataset.xhtml?persistentId=hdl:10622/3SV0BO
- Coverage: ~1260–1914; European cities + extensions; city-level
- Variables: Commodity prices, real wages, silver wages, welfare ratios
- License: Free academic
- Format: CSV / XLSX
- Effort: Medium.

#### Allen-Bassino-Ma-Moll-Murata-van Zanden — China wages 1738–1925
- Paper PDF: https://gpih.ucdavis.edu/files/Allen_et_al.pdf
- Coverage: 1738–1925; Beijing/Canton/Suzhou + comparison cities
- Variables: Nominal wages, prices, welfare ratios
- License: Open academic
- Format: XLSX
- Effort: Medium.

#### Global Price and Income History (GPIH) — UC Davis
- Home: https://gpih.ucdavis.edu/  (file list: https://gpih.ucdavis.edu/Datafilelist.htm)
- Coverage: wages/prices ~1500–1950 (region-dependent); Europe, Africa, Asia (esp. China, Egypt, S. Africa), the Americas; city-level
- License: Free academic
- Format: scattered XLSX/CSV per paper
- Effort: High — fragmented.

#### Broadberry historical national accounts (UK/IT/ES/NL/JP/IN/CN)
- Reference: Cambridge volumes; usually distributed via personal pages
- Coverage: 1270–1870 (UK); similar windows for others
- Variables: Sectoral GDP, population
- License: Mixed
- Effort: High. Mostly already merged into Maddison 2023.

#### World Bank WDI
- Home: https://data.worldbank.org/
- Coverage: 1960–present; 217 economies; country
- Variables: 1,400+ indicators
- License: CC BY 4.0
- Format: CSV bulk, REST API (https://api.worldbank.org/v2/)
- Effort: Low. Post-1960 spine.

#### Bairoch / Buringh European city populations
- Bairoch CSV: https://github.com/JakeRuss/bairoch-1988
- Buringh expanded: https://www.doi.org/10.17026/dans-xzy-u62q
- Coverage: 800–2000; ~26 European countries; city
- License: Open
- Format: CSV
- Effort: Low.

#### Reba/Chandler/Modelski global urban populations (SEDAC)
- Home: https://sedac.ciesin.columbia.edu/data/set/urbanspatial-hist-urban-pop-3700bc-ad2000
- Coverage: 3700 BCE–2000 CE; global; city-level (name, lat/long, year, pop, reliability)
- License: Open (SEDAC/CC)
- Format: CSV
- Effort: Low. **Best source for "biggest cities in region X around year Y" globally.**

### 1.2 Health / demography

#### HYDE 3.3 — gridded population & land use
- Home: https://themasites.pbl.nl/tridion/en/themasites/hyde/download/index-2.html  (portal: https://hyde-portal.geo.uu.nl/)
- Coverage: 10,000 BCE – 2023 CE; global; 5-arcmin grid (~85 km²)
- Variables: Total/urban/rural population + density, built-up area, cropland, grazing
- License: CC BY 3.0
- Format: ESRI ASCII grid + netCDF
- Effort: Medium-high. Few GB raw → aggregate once per region/year, cache as small CSV.

#### Human Mortality Database (HMD)
- Home: https://www.mortality.org/
- Coverage: ~1751–present (varies); ~40 industrialized countries
- Variables: Deaths, births, life tables, exposure
- License: Free w/ registration
- Format: TXT/CSV zips
- Effort: Medium.

#### Human Life-Table Database (HLD)
- Home: https://www.lifetable.de/
- Coverage: 15,008 life tables, 142 countries
- License: Free
- Effort: Medium.

#### Riley life expectancy (2005)
- OWID: https://github.com/owid/owid-datasets/tree/master/datasets/Life%20expectancy%20-%20Riley%20(2005),%20Clio%20Infra%20(2015),%20and%20UN%20(2019)
- Coverage: 1800–2001; ~200 reconstructed countries
- License: Open via OWID
- Format: CSV
- Effort: Low. Direct fit for `health`.

#### Baten/Blum historical heights
- Clio-Infra: https://clio-infra.eu/Indicators/Height.html
- Coverage: 1810–1989 (165 countries); 1500–1800 subset
- License: Open
- Format: XLSX
- Effort: Low. Nutrition proxy.

#### Our World in Data — long-term reconstructions
- Home: https://ourworldindata.org/  (chart API: https://docs.owid.io/projects/etl/api/chart-api/)
- Coverage: varies per chart; many back to 1500–1800
- License: CC BY (most)
- Format: `<chart-url>.csv` + `.metadata.json`
- Effort: Very low. **Best aggregator for harmonized single-factor series.**

### 1.3 Conflict / war

#### Brecke Conflict Catalog (already integrated)
- Home: https://brecke.inta.gatech.edu/research/conflict/
- Direct: https://brecke.inta.gatech.edu/wp-content/uploads/sites/19/2018/09/Conflict-Catalog-18-vars.xlsx
- Coverage: 1400–2000; global; conflict-level (3,708 conflicts)
- Already wired. No further updates planned.

#### UCDP/PRIO Armed Conflict Dataset v25.1
- Home: https://ucdp.uu.se/downloads/
- Coverage: 1946–2024; global; conflict-year
- Variables: Conflict ID, dyads, type, intensity, location, battle deaths
- License: CC BY 4.0
- Format: CSV/XLSX/Stata/R
- Effort: Low. **Best modern complement to Brecke (covers 1946+).**

#### UCDP GED v25.1
- Home: https://ucdp.uu.se/downloads/ged/
- Coverage: 1989–2024; global; individual events with lat/long
- License: CC BY 4.0
- Format: CSV/XLSX/Stata/R + REST API
- Effort: Medium (~1 GB CSV; aggregate to region-year).

#### UCDP Battle-Related Deaths
- Home: https://ucdp.uu.se/downloads/brd/
- Coverage: 1989–2023; dyadic + conflict-year
- Effort: Low.

#### Correlates of War — Inter-State War v4.0 / Intra-State v5.1
- Home: https://correlatesofwar.org/data-sets/cow-war/
- Coverage: 1816–2007 (interstate); 1816–2014 (intra-state)
- License: Free
- Format: CSV / Stata
- Effort: Low.

#### COW MID v5.0
- Home: https://correlatesofwar.org/data-sets/mids/
- Coverage: 1816–2014; dyadic
- Effort: Low.

#### Levy Great Power Wars 1495–1815 (ICPSR 9955)
- Home: https://www.icpsr.umich.edu/web/ICPSR/studies/9955
- Coverage: 1495–1815; great-power wars
- License: ICPSR (free w/ reg)
- Format: codebook + data
- Effort: Medium. **Important early-modern conflict supplement.**

#### ACLED (modern)
- Home: https://acleddata.com/conflict-data/download-data
- API: https://acleddata.com/api-documentation/acled-endpoint
- Coverage: Africa 1997+; ME 2015–17+; full global 2018+
- License: Free w/ account; non-commercial
- Format: CSV / API
- Effort: Low.

#### Rummel Statistics of Democide
- Internet Archive: https://archive.org/details/statisticsofdemo0000rumm
- 20th century; data trapped in PDFs.
- Effort: High. Use OWID curated derivative instead.

### 1.4 Governance

#### V-Dem v14
- Home: https://www.v-dem.net/data/the-v-dem-dataset/  (archive: https://www.v-dem.net/data/dataset-archive/)
- Coverage: 1789–present; 202 polities
- Variables: 500 indicators, 245 indices (electoral/liberal/participatory/deliberative/egalitarian democracy + sub-indices)
- License: Free academic
- Format: CSV, R, Stata, SPSS zip
- Effort: Low. **Strongest single source for `governance` + many sub-dimensions (women's empowerment, judicial independence, freedom of religion).**

#### Polity 5
- Home: https://www.systemicpeace.org/inscrdata.html
- Coverage: 1800–2018; 167 countries
- License: Free
- Format: CSV + SPSS
- Effort: Low. Older standard; V-Dem better.

#### Boix-Miller-Rosato Dichotomous Democracy v4.0
- Harvard Dataverse: https://dataverse.harvard.edu/dataset.xhtml?persistentId=doi:10.7910/DVN/FENWWR
- Authors: https://sites.google.com/site/mkmtwo/data
- Coverage: 1800–2020; 222 countries
- License: Free
- Format: Stata, Excel, R, CSV
- Effort: Very low.

#### Regimes of the World (in V-Dem)
- Coverage: 1789–present
- Variables: 4-category typology
- Effort: Low.

#### Freedom House — Freedom in the World
- Home: https://freedomhouse.org/report/freedom-world
- Direct XLSX: https://freedomhouse.org/sites/default/files/2025-02/Country_and_Territory_Ratings_and_Statuses_FIW_1973-2024.xlsx
- Coverage: 1972–present
- License: Free for academic/personal
- Effort: Very low.

#### Worldwide Governance Indicators
- Home: https://www.worldbank.org/en/publication/worldwide-governance-indicators
- Bulk CSV: https://databank.worldbank.org/data/download/WGI_CSV.zip
- Coverage: 1996–present; ~200 countries
- License: Open
- Effort: Very low.

#### Archigos (leaders)
- Paper: https://www.rochester.edu/college/faculty/hgoemans/GGC_finalsubmission.pdf
- Coverage: 1875–2015; 188 countries
- Variables: Leader name, dates, entry/exit, age, gender, post-tenure fate
- License: Free academic
- Format: Stata/CSV
- Effort: Low. "Who ruled X in year Y" for modern era.

### 1.5 Religion / tolerance

#### Religious Characteristics of States (RCS-Dem 2.0)
- ARDA Countries: https://www.thearda.com/data-archive?fid=RCSDEM2
- ARDA Regions: https://www.thearda.com/data-archive?fid=RCSREG2
- OSF: https://osf.io/7sr4m/
- Coverage: 1800/1900–2015; 220 states + 26 substate + 41 dependencies
- Variables: Adherent count and % for ~100 denominations
- License: Free academic
- Format: CSV / SPSS
- Effort: Low-medium. **Best religious demography source.**

#### Pew Global Restrictions on Religion
- Pew: https://www.pewresearch.org/dataset/dataset-global-restrictions-on-religion-2007-2022/
- ARDA mirror: https://www.thearda.com/data-archive?fid=GRELREST
- Coverage: 2007–2022; 198 countries
- Variables: GRI (20 indicators), SHI (13)
- License: Free academic
- Effort: Very low. Direct fit for `religious_tolerance`.

#### ARDA International Data Archive (umbrella)
- Home: https://www.thearda.com/data-archive/browse-categories?cid=A
- Coverage: 900+ surveys
- License: Free academic
- Effort: Medium.

### 1.6 Technology, innovation, literacy

#### Comin-Hobijn CHAT
- NBER: https://www.nber.org/papers/w15319
- Data: http://www.nber.org/data/chat
- Coverage: 1800–~2003; 161 countries; 104 technologies
- Variables: Adoption levels (telegraph, railroad, electricity, telephones, internet, etc.)
- License: Free academic
- Format: Stata/CSV
- Effort: Low. **Enables new tech-adoption factor.**

#### Buringh & van Zanden historical literacy
- Wikimedia tab: https://commons.wikimedia.org/wiki/Data:Estimated_historical_literacy_rates_-_Buringh_and_Van_Zanden_(2009)_(OWID_2703).tab
- GitHub: https://github.com/manjunath5496/CSV-Datasets_1/blob/master/Estimated%20historical%20literacy%20rates%20-%20Buringh%20and%20Van%20Zanden%20(2009).csv
- Coverage: ~1450–1800; Europe; country
- License: CC BY 3.0
- Format: CSV / tab
- Effort: Very low. **New literacy factor for early-modern Europe.**

#### UNESCO UIS (modern literacy/education)
- Home: https://uis.unesco.org/bdds
- Coverage: 1970–present; ~200 countries
- License: Free
- Format: XLSX bulk, API
- Effort: Low.

#### Murray Human Accomplishment
- Wikipedia: https://en.wikipedia.org/wiki/Human_Accomplishment
- Data location unclear; flagged as "find on OSF before relying"
- Effort: Medium.

#### Slave Voyages (Trans-Atlantic + Intra-American)
- Home: https://www.slavevoyages.org/voyage/database/
- Legacy downloads: https://legacy.slavevoyages.org/blog/downloads-trans-atlantic
- Coverage: ~1500–1866; ~36,000 voyages
- Variables: 274 fields (embarkation/disembarkation ports, captives, dates)
- License: Open (Rice University)
- Format: SPSS, CSV
- Effort: Medium. **Strong dignity/safety signal both source and destination regions.**

---

## Section 2 — Rulers, events, qualitative

### 2.1 Rulers

#### Wikidata SPARQL
- Endpoint: https://query.wikidata.org/sparql
- Coverage: global; pre-modern to present (depends on item completeness)
- Variables: heads of state (P35), heads of government (P6), capitals (P36), positions held with start/end qualifiers (P580/P582)
- License: CC0
- Format: SPARQL → JSON/CSV/TSV
- Effort: Medium. **Best free way to answer "who ruled X in year Y".**

#### Archigos
Modern rulers 1875–2015, simple CSV. (See 1.4)

#### CHGIS political units (China)
- Home: https://chgis.fas.harvard.edu/
- Harvard Dataverse: https://dataverse.harvard.edu/dataset.xhtml?persistentId=doi:10.7910/DVN/29302
- Coverage: 221 BCE – 1911 CE; China
- Variables: provinces, circuits, prefectures, counties; placenames with date ranges
- License: Free academic
- Format: Shapefile + CSV
- Effort: Medium. **Essential for Chinese subnational through 1911.**

### 2.2 Events

#### Wikipedia REST (already integrated)
- API: https://en.wikipedia.org/api/rest_v1/page/summary/{year}

#### HistoryLabs Events API
- API: https://events.historylabs.io/
- GitHub: https://github.com/HistoryLabs/events-api
- Coverage: Wikipedia by year/month/day
- Format: JSON REST
- Effort: Low. Better than parsing year pages yourself.

#### DBpedia historical events (Hienert/Luczak-Roesch)
- Paper: https://arxiv.org/pdf/1205.4138
- ~121,812 events from 300 BCE+, 9+ languages, SPARQL historically.
- Effort: Medium (check endpoint freshness).

#### EM-DAT Disasters
- Home: https://www.emdat.be/
- Coverage: 1900–present; 27,000+ disasters
- Variables: type, deaths, affected, damage, date, location
- License: Free academic/non-commercial; registration
- Format: XLSX
- Effort: Low. **Direct fit for `safety` 1900+.**

#### HDX Global Pandemic & Epidemic Outbreaks
- Home: https://data.humdata.org/dataset/global-pandemic-and-epidemic-outbreaks
- Coverage: 1996–present; 236 countries; 3,000+ outbreaks
- License: CC BY-IGO
- Effort: Low.

#### Human Epidemic Database (HED, Nature 2025)
- Paper: https://www.nature.com/articles/s41597-025-04663-z
- Coverage: 1963–2023; 237 countries; 3,300+ outbreaks; 170+ pathogens
- Format: CSV via Zenodo
- Effort: Low.

#### OWID Historical Pandemics
- Home: https://ourworldindata.org/historical-pandemics
- Small curated CSV (Black Death, smallpox, etc.)
- Effort: Very low.

#### Avalon Project (Yale)
- Home: https://avalon.law.yale.edu/
- HTML only, no API/bulk. Skip in favor of ICOW.

#### ICOW Multilateral Treaties of Pacific Settlement
- Search: ICOW Project (Paul Hensel, UNT)
- Modern; structured CSV.

#### Seshat: Global History Databank
- Home: https://seshatdatabank.info/databrowser/downloads.html
- Coverage: polity-level over 10,000 years; 100s of pre-industrial polities
- Variables: ~50 social complexity variables
- License: CC BY-NC-SA
- Format: spreadsheet / Zenodo Equinox dataset
- Effort: Medium. **Pre-1800 governance/complexity proxies.**

### 2.3 Wars (more)

#### OWID curated war and peace
- Home: https://ourworldindata.org/war-and-peace
- One-stop harmonized series (Brecke + COW + UCDP).
- Effort: Very low.

#### Clodfelter print encyclopedia
- 4th ed. 2017; not machine-readable.

---

## Section 3 — Historical polygons

### 3.1 Free / open

#### Natural Earth (already integrated for modern)
- Home: https://www.naturalearthdata.com/downloads/10m-cultural-vectors/
- Public domain.

#### aourednik / historical-basemaps (GitHub)
- Repo: https://github.com/aourednik/historical-basemaps
- Coverage: global; multiple snapshot years (1492, 1880, 1938, etc.)
- License: GPL-3.0 (note: may force GPL on derivative polygons if redistributed)
- Format: GeoJSON per year + SVG; WGS84
- Effort: Low. **Best free global historical polygon source.**

#### CShapes 2.0
- Home: https://icr.ethz.ch/data/cshapes/
- Coverage: 1886–2019 global; 1816+ Europe
- Variables: independent states + colonies/dependencies with start/end dates, capital lat/long
- License: CC BY-NC-SA
- Format: Shapefile, GeoJSON, CSV, SQL, R
- Effort: Low. **Essential for 1886+ polygons including colonial era.**

#### Centennia Historical Atlas
- Home: https://www.clockwk.com/centennia/
- Commercial Windows software; no GIS export. **Skip.**

#### Running Reality
- Docs: https://runningreality.org/docs/index.jsp
- Internal GeoJSON; curated world model not bulk-downloadable. **High effort to extract.**

#### CHGIS (Chinese subnational)
- See 2.1.

#### ORBIS Stanford (Roman)
- Home: https://orbis.stanford.edu/orbis2012/
- Out of scope for 1500+.

#### Wikidata historical entities
- SPARQL by P31 historical-country with P580/P582 dates. Centroids only, rarely polygons.
- Effort: High; discovery layer, not polygon source.

### 3.2 Commercial / restricted

#### Euratlas Periodis
- Shop: https://www.euratlas.net/shop/maps_gis/
- Coverage: Europe; every century 1–2000 CE
- License: Paid (~€140/century; ~€840 for 1500–2000)
- Format: Shapefile
- Effort: Low integration, high cost.

#### GeaCron
- http://geacron.com/
- Mobile/web tool; no polygon export. **Skip.**

#### East View Geospatial historical maps
- Paid per country. **Skip.**

### 3.3 Polygon recommendation

| Period | Best free source |
|---|---|
| 1500–1885 (global) | aourednik historical-basemaps (sparse snapshots) |
| 1500–1911 (China subnational) | CHGIS |
| 1886–present (global, incl. colonies) | CShapes 2.0 |
| Today | Natural Earth |

---

## Section 4 — Top-10 integration plan

### Already-easy wins
1. **Our World in Data CSV API** — predictable `<chart>.csv`; CC BY; harmonized stitches of Maddison/Riley/V-Dem/Brecke/UCDP.
2. **V-Dem v14** — single ZIP; 1789–present; 500 indicators. Replaces Polity for `governance` + adds religious freedom, gender, judicial.
3. **UCDP ACD + BRD** — extends `safety` past 2000.
4. **CShapes 2.0** — real 1886+ polygons including colonial empires.
5. **aourednik historical-basemaps** — drop-in pre-1886 polygons.
6. **Pew GRI/SHI** — religious tolerance 2007+.
7. **Boix-Miller-Rosato v4.0** — simple binary regime fallback.
8. **Reba/SEDAC urban populations** — biggest-cities flavor + urbanization axis.

### Big-payoff but harder
9. **Wikidata SPARQL** — rulers per region per year.
10. **Seshat** — pre-industrial polity-level proxies.
11. **HYDE 3.3** — gridded population for urbanization factor.
12. **Slave Voyages** — slavery exposure as safety/dignity signal.
13. **CHGIS** — Chinese subnational polygons + units.

### Skip-for-now
- Euratlas (€840), Centennia/GeaCron (no export), Rummel (PDFs), Avalon (no API), Murray (data unclear), HMD (narrow + replaceable by Clio-Infra+OWID), ACLED (UCDP overlap).

### New factors enabled

| New factor | Source |
|---|---|
| Literacy | Buringh-van Zanden (1500–1800 EU) + UNESCO UIS (1970+) + OWID |
| Tech adoption | Comin-Hobijn CHAT (1800+) |
| Urbanization | HYDE 3.3 + Bairoch + Reba/SEDAC |
| Slavery exposure | Slave Voyages |
| Religious pluralism | RCS-Dem (Herfindahl) + Pew GRI |
| Disasters / epidemics | EM-DAT + HDX + OWID pandemics |
| Height / nutrition | Baten/Blum (Clio-Infra) |
| Heads of state | Wikidata + Archigos |

### Suggested integration order (concrete)
1. Switch governance: Polity → V-Dem v14.
2. Extend safety past 2000 with UCDP ACD + BRD.
3. Add urbanization factor via HYDE 3.3 (pre-aggregated per region).
4. Add literacy: Buringh-van Zanden + UNESCO UIS.
5. Upgrade religious_tolerance: RCS-Dem denomination shares + Pew GRI.
6. Replace polygons: aourednik (1500–1885), CShapes (1886+), CHGIS (China).
7. Flavor: Wikidata rulers + Reba cities + EM-DAT disaster overlays.
8. Add tech_adoption from CHAT (1800+).

Disk: all CSV/XLSX combined <500 MB. HYDE raw grids only GB-scale item — pre-aggregate once and discard raw. Polygons combined <300 MB simplified.
