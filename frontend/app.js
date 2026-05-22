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
const REGION_LABELS_SRC = "regions-labels-src";
const REGION_LABELS = "regions-labels";
const PICK_SRC = "pick-src";
const PICK_LAYER = "pick-layer";

let map;

// ─── boot ────────────────────────────────────────────────────────────────────

async function boot() {
  // Kick API fetches in parallel with map load.
  const [todayP, regionsP] = [fetch("/api/today").then(r => r.json()),
                              fetch("/api/regions").then(r => r.json())];
  initMap();
  // Subtle loading hint while /api/today resolves.
  $("start-era").textContent = "loading today's year…";
  $("start-era").classList.add("loading");
  const today = await todayP;
  $("start-era").classList.remove("loading");
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
  attachHoverHandlers();

  // Restore "already played today" from localStorage.
  const saved = localStorage.getItem(`yearle:v1:guess:${state.date}`);
  if (saved) {
    state.played = true;
    const payload = JSON.parse(saved);
    $("start-card").classList.add("hidden");
    showReveal(payload);
  }
}

function initMap() {
  // MapLibre's free demo tiles — vector world (land/countries/ocean), no API key.
  // We post-style it to a parchment palette via paint overrides on load.
  map = new maplibregl.Map({
    container: "map",
    style: "https://demotiles.maplibre.org/style.json",
    center: [20, 25],
    zoom: 1.6,
    projection: "globe",
    attributionControl: false,
  });

  map.on("style.load", () => {
    // Re-affirm globe (some demotile styles can override after load).
    try { map.setProjection({ type: "globe" }); } catch (e) {}
    const setIf = (id, prop, val) => { if (map.getLayer(id)) map.setPaintProperty(id, prop, val); };
    const hide = (id) => { if (map.getLayer(id)) map.setLayoutProperty(id, "visibility", "none"); };
    // Parchment palette.
    setIf("background", "background-color", "#1a1410");
    setIf("countries-fill", "fill-color", "#cfba8a");
    setIf("countries-boundary", "line-color", "#9a7740");
    setIf("countries-boundary", "line-width", 0.5);
    setIf("countries-boundary", "line-opacity", 0.55);
    setIf("coastline", "line-color", "#7a5a30");
    setIf("coastline", "line-width", 0.7);
    setIf("crimea-fill", "fill-color", "#cfba8a");
    // Hide graticule + per-country labels — region labels go on top instead.
    hide("geolines");
    hide("geolines-label");
    hide("countries-label");
    // Add a subtle atmospheric tint around the globe.
    try {
      map.setFog({
        color: "rgba(214, 184, 125, 0.10)",
        "high-color": "rgba(60, 36, 18, 0.7)",
        "horizon-blend": 0.15,
        "space-color": "#0a0805",
        "star-intensity": 0.0,
      });
    } catch (e) {}
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
      geometry: r.geometry,
    })),
  };
}

function addRegionLayer() {
  map.addSource(REGION_SRC, { type: "geojson", data: regionsAsGeoJSON() });
  // Fill — invisible until scores are known (reveal/explore mode).
  map.addLayer({
    id: REGION_FILL,
    type: "fill",
    source: REGION_SRC,
    paint: {
      "fill-color": [
        "case",
        ["==", ["get", "score"], null], "transparent",
        ["interpolate", ["linear"], ["get", "score"],
          0, "#5a2a2a", 30, "#8b5a3a", 50, "#c9a86a", 70, "#9bbf7a", 100, "#3a8b5e"]
      ],
      "fill-opacity": [
        "case",
        ["==", ["get", "score"], null], 0,
        0.32
      ],
    },
  });
  // Thin border so regions are still discoverable while playing.
  map.addLayer({
    id: REGION_OUTLINE,
    type: "line",
    source: REGION_SRC,
    paint: { "line-color": "#5a4424", "line-width": 0.6, "line-opacity": 0.5, "line-dasharray": [2, 3] },
  });
  // Region names rendered at centroids — replaces demotiles country labels.
  map.addSource(REGION_LABELS_SRC, {
    type: "geojson",
    data: {
      type: "FeatureCollection",
      features: state.regions.map(r => ({
        type: "Feature",
        properties: {
          name: r.name.split(" (")[0],
          min_zoom: r.min_zoom ?? 1.0,
        },
        geometry: { type: "Point", coordinates: [r.centroid[1], r.centroid[0]] },
      })),
    },
  });
  map.addLayer({
    id: REGION_LABELS,
    type: "symbol",
    source: REGION_LABELS_SRC,
    layout: {
      "text-field": ["get", "name"],
      "text-size": ["interpolate", ["linear"], ["zoom"], 1, 11, 4, 14],
      "text-letter-spacing": 0.04,
      "text-anchor": "center",
      "text-allow-overlap": false,
      "text-padding": 4,
    },
    paint: {
      "text-color": "#3a2a18",
      "text-halo-color": "#ede4cf",
      "text-halo-width": 1.4,
      "text-halo-blur": 0.6,
      // Hide labels for small regions until user zooms in.
      "text-opacity": [
        "case",
        ["<", ["zoom"], ["get", "min_zoom"]], 0,
        0.92
      ],
    },
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
    try {
      const res = await fetch("/api/today/guess", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ year: state.year, lat, lon: lng }),
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const payload = await res.json();
      localStorage.setItem(`yearle:v1:guess:${state.date}`, JSON.stringify(payload));
      showReveal(payload);
    } catch (err) {
      console.error("guess submit failed:", err);
      state.mode = "playing";
      alert("Couldn't submit your guess — check your connection and try again.");
    }
  } else if (state.mode === "explore") {
    const feats = map.queryRenderedFeatures(e.point, { layers: [REGION_FILL] });
    if (feats.length) showExploreDetail(feats[0].properties.id);
  }
}

// Hover affordance on globe regions during explore mode.
function attachHoverHandlers() {
  map.on("mousemove", (e) => {
    if (state.mode !== "explore") {
      document.body.classList.remove("map-hover-explore");
      return;
    }
    const feats = map.queryRenderedFeatures(e.point, { layers: [REGION_FILL] });
    document.body.classList.toggle("map-hover-explore", feats.length > 0);
  });
  map.on("mouseleave", () => document.body.classList.remove("map-hover-explore"));
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

// Friendly tags for factor_sources values (which dataset/source produced the score).
const SOURCE_TAGS = {
  "maddison": { label: "Maddison", title: "Maddison Project 2023 GDP/cap" },
  "brecke":   { label: "Brecke",   title: "Brecke Conflict Catalog 1400-2000" },
  "wiki":     { label: "Wiki",     title: "Wikipedia (manual context)" },
  "neutral":  { label: "neutral",  title: "No sourced data — held at 50" },
  "baseline": { label: "era",      title: "Era baseline with manual adjustment" },
};

function renderFactors(factors, factorSources) {
  if (!factors || !Object.keys(factors).length) return "";
  return Object.entries(factors).map(([k, v]) => {
    const cls = v >= 70 ? "high" : v <= 35 ? "low" : "";
    const pct = Math.max(0, Math.min(100, v));
    const srcKey = factorSources?.[k];
    const tag = SOURCE_TAGS[srcKey];
    const srcChip = tag
      ? `<span class="src-chip src-${srcKey}" title="${tag.title}">${tag.label}</span>`
      : "";
    return `<div class="factor">
      <span class="factor-label">${k.replace(/_/g, " ")}${srcChip}</span>
      <span class="factor-bar ${cls}"><span style="width:${pct}%"></span></span>
      <span class="factor-val">${v}</span>
    </div>`;
  }).join("");
}

function renderSources(sources) {
  if (!sources || !sources.length) return `<div class="muted">No sources cited yet.</div>`;
  return sources.map(s => `<a href="${s.url}" target="_blank" rel="noopener">↗ ${s.label}</a>`).join("");
}

function countUp(el, target, duration = 700) {
  if (!el) return;
  const start = performance.now();
  const from = 0;
  const tick = (t) => {
    const k = Math.min(1, (t - start) / duration);
    // ease-out cubic
    const eased = 1 - Math.pow(1 - k, 3);
    el.textContent = Math.round(from + (target - from) * eased);
    if (k < 1) requestAnimationFrame(tick);
    else el.textContent = String(target);
  };
  requestAnimationFrame(tick);
}

function showReveal(p) {
  state.mode = "reveal";
  $("hud").classList.add("hidden");
  const g = p.guess || {};
  const score = g.score ?? 0;
  // Legacy field (kept harmless if removed from DOM later).
  const legacy = $("reveal-score");
  if (legacy) legacy.textContent = `Your score: ${score} / 100 · rank ${p.rank}/${p.total_regions}`;
  const numEl = $("reveal-score-num");
  if (numEl) {
    numEl.textContent = "0";
    countUp(numEl, score);
  }
  const rankEl = $("reveal-score-rank");
  if (rankEl) rankEl.textContent = `rank ${p.rank} of ${p.total_regions}`;
  $("reveal-pick").innerHTML =
    `<strong>You picked: ${g.region_name || "(no region)"}</strong>` +
    `<div>${g.summary || ""}</div>`;
  $("reveal-pick-factors").innerHTML = renderFactors(g.factors, g.factor_sources);
  $("reveal-pick-sources").innerHTML = renderSources(g.sources);
  $("reveal-top").innerHTML =
    `<strong>${p.top.region_name} · ${p.top.score}/100</strong>` +
    `<div>${p.top.summary}</div>`;
  $("reveal-top-factors").innerHTML = renderFactors(p.top.factors, p.top.factor_sources);
  $("reveal-top-sources").innerHTML = renderSources(p.top.sources);
  $("reveal-card").classList.remove("hidden");
}

function showExploreDetail(rid) {
  const cell = state._yearData?.[rid];
  if (!cell) return;
  const region = state.regions.find(r => r.id === rid);
  // Rank position for this region in the year.
  const ranking = Object.entries(state._yearData).sort((a,b) => b[1].score - a[1].score);
  const rankIdx = ranking.findIndex(([id]) => id === rid) + 1;
  const scoreCls = cell.score >= 65 ? "high" : cell.score <= 40 ? "low" : "";
  const rulerLine = cell.ruler ? `<div class="explore-ruler">👑 ${cell.ruler}</div>` : "";
  const isWinner = rankIdx === 1;
  const pillCls = isWinner ? "explore-rank-pill rank-winner" : "explore-rank-pill";
  const laurel = isWinner ? `<span class="laurel" title="Top-ranked region this year">🏛</span>` : "";
  $("explore-detail").innerHTML =
    `<div class="explore-headline">
       <div>
         <div class="explore-headline-name">${region.name}</div>
         <span class="${pillCls}">${laurel}rank ${rankIdx} of ${ranking.length}</span>
       </div>
       <div class="explore-headline-score ${scoreCls}">${cell.score}</div>
     </div>` +
    rulerLine +
    `<div class="explore-summary">${cell.summary || ""}</div>` +
    `<div class="factors">${renderFactors(cell.factors, cell.factor_sources)}</div>` +
    `<div class="sources">${renderSources(cell.sources)}</div>`;
}

// ─── go ──────────────────────────────────────────────────────────────────────

boot().catch(err => {
  console.error(err);
  $("start-era").textContent = "Failed to load. Check console.";
});
