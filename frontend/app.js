// yearl-e — globe + game loop. v1: single guess per day, no auth, no DB.

const $ = (id) => document.getElementById(id);

const state = {
  date: null,
  year: null,
  label: null,
  era: null,
  played: false,
  regions: [],         // [{id, name, centroid, polygon}]
  mode: "start",       // start | playing | reveal | explore
};

const REGION_SRC = "regions-src";
const REGION_FILL = "regions-fill";
const REGION_OUTLINE = "regions-outline";
const PICK_SRC = "pick-src";
const PICK_LAYER = "pick-layer";

let map;

// ─── boot ────────────────────────────────────────────────────────────────────

async function boot() {
  // Kick API fetches in parallel with map load.
  const [todayP, regionsP] = [fetch("/api/today").then(r => r.json()),
                              fetch("/api/regions").then(r => r.json())];
  initMap();
  const today = await todayP;
  state.date = today.date;
  state.year = today.year;
  state.label = today.label;
  state.era = today.era_summary;
  $("day-tag").textContent = `Day ${today.day_number}`;
  $("start-year").textContent = today.label;
  $("start-era").textContent = today.era_summary;
  $("year-label").textContent = today.label;
  $("era-summary").textContent = today.era_summary;

  const regions = await regionsP;
  state.regions = regions.regions;

  await whenMapReady();
  addRegionLayer();

  // Restore "already played today" from localStorage.
  const saved = localStorage.getItem(`yearle:${state.date}`);
  if (saved) {
    state.played = true;
    const payload = JSON.parse(saved);
    $("start-card").classList.add("hidden");
    showReveal(payload);
  }
}

function initMap() {
  map = new maplibregl.Map({
    container: "map",
    // Plain parchment-style style — no satellite. Solid background, vector regions on top.
    style: {
      version: 8,
      sources: {},
      layers: [
        { id: "sky", type: "background", paint: { "background-color": "#0e0a06" } }
      ],
      glyphs: "https://demotiles.maplibre.org/font/{fontstack}/{range}.pbf"
    },
    center: [20, 30],
    zoom: 1.4,
    projection: { type: "globe" },
    attributionControl: false,
  });

  map.on("click", onMapClick);
}

function whenMapReady() {
  return new Promise((res) => {
    if (map.isStyleLoaded()) res();
    else map.once("load", res);
  });
}

// ─── region layer ────────────────────────────────────────────────────────────

function regionsAsGeoJSON(scoreLookup) {
  return {
    type: "FeatureCollection",
    features: state.regions.map(r => ({
      type: "Feature",
      properties: {
        id: r.id,
        name: r.name,
        score: scoreLookup ? (scoreLookup[r.id]?.score ?? null) : null,
      },
      geometry: { type: "Polygon", coordinates: [r.polygon] },
    })),
  };
}

function addRegionLayer() {
  map.addSource(REGION_SRC, { type: "geojson", data: regionsAsGeoJSON() });
  map.addLayer({
    id: REGION_FILL,
    type: "fill",
    source: REGION_SRC,
    paint: {
      "fill-color": [
        "case",
        ["==", ["get", "score"], null], "#ede4cf",
        ["interpolate", ["linear"], ["get", "score"],
          0, "#5a2a2a", 30, "#8b5a3a", 50, "#c9a86a", 70, "#9bbf7a", 100, "#3a8b5e"]
      ],
      "fill-opacity": 0.55,
    },
  });
  map.addLayer({
    id: REGION_OUTLINE,
    type: "line",
    source: REGION_SRC,
    paint: { "line-color": "#8b6b3a", "line-width": 1.2 },
  });
  map.addSource(PICK_SRC, { type: "geojson", data: { type: "FeatureCollection", features: [] } });
  map.addLayer({
    id: PICK_LAYER,
    type: "circle",
    source: PICK_SRC,
    paint: { "circle-radius": 7, "circle-color": "#d4a76a", "circle-stroke-color": "#1a1410", "circle-stroke-width": 2 },
  });
}

function recolorRegions(scoreLookup) {
  const src = map.getSource(REGION_SRC);
  if (src) src.setData(regionsAsGeoJSON(scoreLookup));
}

function setPick(lat, lon) {
  const src = map.getSource(PICK_SRC);
  if (!src) return;
  src.setData({
    type: "FeatureCollection",
    features: [{ type: "Feature", geometry: { type: "Point", coordinates: [lon, lat] }, properties: {} }],
  });
}

// ─── interactions ────────────────────────────────────────────────────────────

async function onMapClick(e) {
  if (state.mode === "playing") {
    const { lat, lng } = e.lngLat;
    setPick(lat, lng);
    state.mode = "submitting";
    const res = await fetch("/api/today/guess", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ year: state.year, lat, lon: lng }),
    });
    const payload = await res.json();
    localStorage.setItem(`yearle:${state.date}`, JSON.stringify(payload));
    showReveal(payload);
  } else if (state.mode === "explore") {
    const feats = map.queryRenderedFeatures(e.point, { layers: [REGION_FILL] });
    if (feats.length) showExploreDetail(feats[0].properties.id);
  }
}

$("btn-start").addEventListener("click", () => {
  $("start-card").classList.add("hidden");
  $("hud").classList.remove("hidden");
  state.mode = "playing";
});

$("btn-explore").addEventListener("click", async () => {
  $("reveal-card").classList.add("hidden");
  $("explore-card").classList.remove("hidden");
  $("explore-year").textContent = state.label;
  $("overlay").classList.add("explore-mode");
  state.mode = "explore";
  // Fetch full year data + recolor by score.
  const res = await fetch(`/api/year/${state.year}/regions`).then(r => r.json());
  state._yearData = res.regions;
  recolorRegions(res.regions);
});

$("btn-explore-close").addEventListener("click", () => {
  $("explore-card").classList.add("hidden");
  $("overlay").classList.remove("explore-mode");
  $("reveal-card").classList.remove("hidden");
  state.mode = "reveal";
});

// ─── rendering ───────────────────────────────────────────────────────────────

function renderFactors(factors) {
  if (!factors || !Object.keys(factors).length) return "";
  return Object.entries(factors)
    .map(([k, v]) => `<div class="factor"><span>${k.replace(/_/g, " ")}</span><b>${v}</b></div>`)
    .join("");
}

function renderSources(sources) {
  if (!sources || !sources.length) return `<div class="muted">No sources cited yet.</div>`;
  return sources.map(s => `<a href="${s.url}" target="_blank" rel="noopener">↗ ${s.label}</a>`).join("");
}

function showReveal(p) {
  state.mode = "reveal";
  $("hud").classList.add("hidden");
  const g = p.guess || {};
  $("reveal-score").textContent = `Your score: ${g.score ?? 0} / 100 · rank ${p.rank}/${p.total_regions}`;
  $("reveal-pick").innerHTML =
    `<strong>You picked: ${g.region_name || "(no region)"}</strong>` +
    `<div>${g.summary || ""}</div>`;
  $("reveal-pick-factors").innerHTML = renderFactors(g.factors);
  $("reveal-pick-sources").innerHTML = renderSources(g.sources);
  $("reveal-top").innerHTML =
    `<strong>${p.top.region_name} · ${p.top.score}/100</strong>` +
    `<div>${p.top.summary}</div>`;
  $("reveal-top-factors").innerHTML = renderFactors(p.top.factors);
  $("reveal-top-sources").innerHTML = renderSources(p.top.sources);
  $("reveal-card").classList.remove("hidden");
}

function showExploreDetail(rid) {
  const cell = state._yearData?.[rid];
  if (!cell) return;
  const region = state.regions.find(r => r.id === rid);
  $("explore-detail").innerHTML =
    `<strong>${region.name} · ${cell.score}/100</strong>` +
    `<div style="font-size:13px;margin:6px 0;">${cell.summary}</div>` +
    `<div class="factors">${renderFactors(cell.factors)}</div>` +
    `<div class="sources">${renderSources(cell.sources)}</div>`;
}

// ─── go ──────────────────────────────────────────────────────────────────────

boot().catch(err => {
  console.error(err);
  $("start-era").textContent = "Failed to load. Check console.";
});
