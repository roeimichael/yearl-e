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

// Display names for early_modern region IDs — the raw IDs in the data are
// programmatic ("rome_italy"); these are what we actually paint on the globe.
const DISPLAY_NAMES = {
  rome_italy: "Italy",
  andalusia_iberia: "Iberia",
  francia: "France",
  england: "Britain",
  rus: "Russia",
  constantinople_balkans: "Ottoman Empire",
  persia: "Persia",
  central_asia: "Central Asia",
  egypt_nile: "Egypt",
  arabia: "Arabia",
  ethiopia: "Ethiopia",
  han_china: "China",
  japan: "Japan",
  north_america_east: "N. America",
  andes: "Andes",
  brazil_amazon: "Brazil",
  sweden_empire: "Sweden",
  denmark_norway: "Denmark-Norway",
  swedish_baltic: "Baltic",
  habsburg_austria: "Austria",
  prussia_brandenburg: "Prussia",
  german_princes: "German States",
  polish_lithuanian_commonwealth: "Poland-Lithuania",
  mughal_north: "Mughal India",
  maratha_confederacy: "Marathas",
  bengal: "Bengal",
  deccan_sultanates: "Deccan",
  voc_indonesia: "Dutch Indies",
  siam_vietnam_burma: "SE Asia",
  spanish_philippines: "Philippines",
  kongo_angola: "Kongo",
  southern_africa: "S. Africa",
  asante_coast: "Gold Coast",
  sahel_interior: "Sahel",
  new_spain: "New Spain",
  caribbean: "Caribbean",
};

const displayName = (r) => DISPLAY_NAMES[r.id] || r.name.split(" (")[0];

// Same lookup but by raw id string (for backend payloads that don't carry the
// region object). Falls back to a humanized version of the id.
const displayNameById = (id) =>
  DISPLAY_NAMES[id] || id.split("_").map(w => w[0].toUpperCase() + w.slice(1)).join(" ");

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
  const today = await todayP;
  state.date = today.date;
  state.year = today.year;
  state.label = today.label;
  state.era = today.era_summary;
  $("day-tag").textContent = `Day ${today.day_number}`;
  const btn = $("btn-start");
  btn.disabled = false;
  btn.textContent = "Spin the globe →";
  $("year-label").textContent = today.label;

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
    center: [34.8, 31.5],  // Israel
    zoom: 2.4,
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
        name: displayName(r),
        score: scoreLookup ? (scoreLookup[r.id]?.score ?? null) : null,
      },
      geometry: r.geometry,
    })),
  };
}

function addRegionLayer() {
  // promoteId lets us key feature-state by our string id (for hover state).
  map.addSource(REGION_SRC, { type: "geojson", data: regionsAsGeoJSON(), promoteId: "id" });
  // Fill — translucent hint while playing so boundaries are readable;
  // jumps to color gradient on reveal/explore.
  map.addLayer({
    id: REGION_FILL,
    type: "fill",
    source: REGION_SRC,
    paint: {
      "fill-color": [
        "case",
        ["==", ["get", "score"], null], "#8b6b3a",
        ["interpolate", ["linear"], ["get", "score"],
          0,   "#4a1818",
          15,  "#7a2f1f",
          30,  "#a85a2c",
          45,  "#c89148",
          55,  "#d8c075",
          65,  "#b6c772",
          78,  "#7ab86a",
          90,  "#3f9558",
          100, "#246d3e"]
      ],
      "fill-opacity": [
        "case",
        ["boolean", ["feature-state", "hover"], false],
          ["case", ["==", ["get", "score"], null], 0.22, 0.70],
        ["case", ["==", ["get", "score"], null], 0.08, 0.48]
      ],
      "fill-opacity-transition": { duration: 180 },
    },
  });
  // Outline — solid + bolder on hover for the "pop" effect.
  map.addLayer({
    id: REGION_OUTLINE,
    type: "line",
    source: REGION_SRC,
    paint: {
      "line-color": [
        "case",
        ["boolean", ["feature-state", "hover"], false], "#f0c98a",
        "#5a3a1a"
      ],
      "line-width": [
        "case",
        ["boolean", ["feature-state", "hover"], false], 2.4,
        1.0
      ],
      "line-opacity": [
        "case",
        ["boolean", ["feature-state", "hover"], false], 1.0,
        0.7
      ],
      "line-width-transition": { duration: 180 },
      "line-color-transition": { duration: 180 },
    },
  });
  // Region names rendered at centroids — replaces demotiles country labels.
  map.addSource(REGION_LABELS_SRC, {
    type: "geojson",
    data: {
      type: "FeatureCollection",
      features: state.regions.map(r => ({
        type: "Feature",
        properties: { name: displayName(r) },
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
      "text-size": ["interpolate", ["linear"], ["zoom"], 1.5, 10, 3, 13, 5, 16],
      "text-letter-spacing": 0.05,
      "text-anchor": "center",
      "text-allow-overlap": false,
      "text-ignore-placement": false,
      "text-padding": 2,
    },
    paint: {
      "text-color": "#2a1f12",
      "text-halo-color": "#ede4cf",
      "text-halo-width": 1.6,
      "text-halo-blur": 0.4,
      "text-opacity": 0.95,
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
    if (state._longPress) { state._longPress = false; return; }
    const { lat, lng } = e.lngLat;
    setPick(lat, lng);
    state.mode = "submitting";
    try {
      const res = await fetch("/api/today/guess", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ year: state.year, lat, lon: lng }),
      });
      if (!res.ok) {
        const body = await res.text().catch(() => "");
        throw new Error(`HTTP ${res.status} ${res.statusText} — ${body.slice(0, 200)}`);
      }
      const payload = await res.json();
      localStorage.setItem(`yearle:v1:guess:${state.date}`, JSON.stringify(payload));
      showReveal(payload);
    } catch (err) {
      console.error("guess submit failed:", err);
      state.mode = "playing";
      alert(`Couldn't submit guess.\n${err.message || err}\n\nIs the backend running?`);
    }
  } else if (state.mode === "explore") {
    const feats = map.queryRenderedFeatures(e.point, { layers: [REGION_FILL] });
    if (feats.length) showExploreDetail(feats[0].properties.id);
  }
}

// Hover state — drives both the HUD hint and the per-region "pop" via
// feature-state. Touch uses a 300ms long-press to preview without submitting.
let hoveredRid = null;
function setHoverRegion(rid) {
  if (hoveredRid === rid) return;
  if (hoveredRid) {
    map.setFeatureState({ source: REGION_SRC, id: hoveredRid }, { hover: false });
  }
  hoveredRid = rid;
  if (rid) {
    map.setFeatureState({ source: REGION_SRC, id: rid }, { hover: true });
  }
}

function attachHoverHandlers() {
  const hoverEl = $("hud-hover-region");
  const defaultHint = hoverEl ? hoverEl.textContent : "";

  const updateHoverFromPoint = (point) => {
    if (state.mode !== "playing" && state.mode !== "explore") {
      setHoverRegion(null);
      if (hoverEl) hoverEl.textContent = defaultHint;
      return;
    }
    const feats = map.queryRenderedFeatures(point, { layers: [REGION_FILL] });
    const f = feats[0];
    setHoverRegion(f ? f.properties.id : null);
    if (state.mode === "playing" && hoverEl) {
      hoverEl.textContent = f?.properties?.name || defaultHint;
    }
    document.body.classList.toggle("map-hover-play", state.mode === "playing" && !!f);
    document.body.classList.toggle("map-hover-explore", state.mode === "explore" && !!f);
  };

  map.on("mousemove", (e) => updateHoverFromPoint(e.point));
  map.on("mouseout", () => {
    setHoverRegion(null);
    document.body.classList.remove("map-hover-explore", "map-hover-play");
    if (hoverEl) hoverEl.textContent = defaultHint;
  });

  // Touch long-press = preview, not submit. 300ms hold to pop; release fades.
  let pressTimer = null;
  map.on("touchstart", (e) => {
    state._longPress = false;
    if (e.points && e.points.length > 1) return;
    const pt = e.point;
    pressTimer = setTimeout(() => {
      state._longPress = true;
      updateHoverFromPoint(pt);
    }, 300);
  });
  const clearPress = () => { if (pressTimer) { clearTimeout(pressTimer); pressTimer = null; } };
  map.on("touchend", () => {
    clearPress();
    setTimeout(() => {
      setHoverRegion(null);
      if (hoverEl) hoverEl.textContent = defaultHint;
    }, 600);
  });
  map.on("touchmove", () => { clearPress(); state._longPress = true; });
}

// ─── share ───────────────────────────────────────────────────────────────────

function scoreEmoji(v) {
  if (v >= 80) return "🟩";
  if (v >= 60) return "🟨";
  if (v >= 40) return "🟧";
  if (v >= 20) return "🟥";
  return "⬛";
}

function buildShareText(payload) {
  const g = payload.guess || {};
  const score = g.score ?? 0;
  const dayTag = $("day-tag")?.textContent || "";
  const factorOrder = ["safety", "health", "economy", "governance", "religious_tolerance"];
  const grid = factorOrder.map(k => scoreEmoji(g.factors?.[k] ?? 0)).join("");
  const url = location.origin || "yearl-e";
  return `yearl-e ${dayTag} · ${state.label}
${score}/100 · rank ${payload.rank}/${payload.total_regions} · ${g.region_name || "?"}
${grid}
${url}`;
}

function showToast(msg, ms = 1800) {
  const t = $("toast");
  if (!t) return;
  t.textContent = msg;
  t.classList.remove("hidden");
  clearTimeout(showToast._h);
  showToast._h = setTimeout(() => t.classList.add("hidden"), ms);
}

async function shareResult() {
  const saved = localStorage.getItem(`yearle:v1:guess:${state.date}`);
  if (!saved) return;
  const text = buildShareText(JSON.parse(saved));
  // Prefer native share on mobile; fall back to clipboard.
  if (navigator.share) {
    try { await navigator.share({ text }); return; } catch (e) { /* fall through */ }
  }
  try {
    await navigator.clipboard.writeText(text);
    showToast("Copied to clipboard");
  } catch (e) {
    // Last-resort textarea trick for old browsers.
    const ta = document.createElement("textarea");
    ta.value = text; document.body.appendChild(ta); ta.select();
    document.execCommand("copy"); ta.remove();
    showToast("Copied");
  }
}

$("btn-share").addEventListener("click", shareResult);

// ─── about modal ─────────────────────────────────────────────────────────────

$("link-about").addEventListener("click", (e) => {
  e.preventDefault();
  $("about-card").classList.remove("hidden");
});
$("btn-about-close").addEventListener("click", () => {
  $("about-card").classList.add("hidden");
});

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
  "vdem":     { label: "V-Dem",    title: "Varieties of Democracy v15 — Electoral Democracy Index (polyarchy)" },
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
  const eraYearEl = $("reveal-era-year");
  const eraSumEl = $("reveal-era-summary");
  if (eraYearEl) eraYearEl.textContent = p.label || state.label || "";
  if (eraSumEl) eraSumEl.textContent = p.era_summary || state.era || "";
  const pickName = g.region_id ? displayNameById(g.region_id) : (g.region_name || "(no region)");
  $("reveal-pick").innerHTML =
    `<strong>You picked: ${pickName}</strong>` +
    `<div>${g.summary || ""}</div>`;
  $("reveal-pick-factors").innerHTML = renderFactors(g.factors, g.factor_sources);
  $("reveal-pick-sources").innerHTML = renderSources(g.sources);
  const topName = p.top.region_id ? displayNameById(p.top.region_id) : p.top.region_name;
  $("reveal-top").innerHTML =
    `<strong>${topName} · ${p.top.score}/100</strong>` +
    `<div>${p.top.summary}</div>`;
  $("reveal-top-factors").innerHTML = renderFactors(p.top.factors, p.top.factor_sources);
  $("reveal-top-sources").innerHTML = renderSources(p.top.sources);
  $("reveal-card").classList.remove("hidden");
}

function showExploreDetail(rid) {
  const cell = state._yearData?.[rid];
  if (!cell) return;
  const region = state.regions.find(r => r.id === rid);
  const ranking = Object.entries(state._yearData).sort((a,b) => b[1].score - a[1].score);
  const rankIdx = ranking.findIndex(([id]) => id === rid) + 1;
  const scoreCls = cell.score >= 65 ? "high" : cell.score <= 40 ? "low" : "";
  const isWinner = rankIdx === 1;
  const rankPill = `<span class="ed-rank${isWinner ? " ed-rank-winner" : ""}">` +
    (isWinner ? "🏛 " : "") + `#${rankIdx} of ${ranking.length}</span>`;
  const rulerLine = cell.ruler
    ? `<div class="ed-ruler"><span class="ed-ruler-icon">👑</span>${cell.ruler}</div>` : "";
  $("explore-detail").className = "";
  $("explore-detail").innerHTML =
    `<div class="ed-header">
       <div class="ed-header-l">
         <div class="ed-name">${displayName(region)}</div>
         ${rankPill}
       </div>
       <div class="ed-score ${scoreCls}">${cell.score}<span class="ed-score-denom">/100</span></div>
     </div>` +
    rulerLine +
    `<p class="ed-summary">${cell.summary || ""}</p>` +
    `<div class="factors ed-factors">${renderFactors(cell.factors, cell.factor_sources)}</div>` +
    (cell.sources?.length
      ? `<div class="ed-sources"><span class="ed-sources-label">Sources</span>${renderSources(cell.sources)}</div>`
      : "");
}

// ─── go ──────────────────────────────────────────────────────────────────────

boot().catch(err => {
  console.error(err);
  const btn = $("btn-start");
  if (btn) btn.textContent = `Failed to load — ${err.message || err}`;
});
