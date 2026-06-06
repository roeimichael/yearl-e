// yearl-e — globe + game loop. v1: single guess per day, no auth, no DB.

const $ = (id) => document.getElementById(id);

// Escape text before injecting into innerHTML. Dataset-supplied strings
// (region names, summaries, ruler names, source labels) flow through here.
const escapeHtml = (s) =>
  String(s ?? "").replace(/[&<>"']/g, (c) => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;",
  })[c]);

const state = {
  date: null,
  year: null,
  label: null,
  era: null,
  played: false,
  regions: [],         // [{id, name, centroid, polygon}]
  mode: "start",       // start | playing | reveal | explore
};

// Region names come from the Cliopatria dataset and are already human-readable
// ("Dutch Republic"). Ocean-split polities carry a trailing ISO-code suffix
// ("Dutch Republic (NLD)") to disambiguate the fragments — strip it for display.
const stripIsoSuffix = (name) =>
  typeof name === "string" ? name.replace(/\s*\([A-Z]{3}\)\s*$/, "") : "";

// Humanize a raw slug id as a last resort (e.g. "dutch_republic_nld" →
// "Dutch Republic Nld"). Only reached when no clean name field is available.
const humanizeId = (id) =>
  typeof id === "string"
    ? id.split("_").map(w => w ? w[0].toUpperCase() + w.slice(1) : w).join(" ")
    : "";

// Clean display name from a region geometry object (carries its own .name).
const displayName = (r) => stripIsoSuffix(r?.name) || humanizeId(r?.id) || "(no region)";

// Clean display name from a backend payload that carries region_name (+ id).
// Prefer the dataset name field; fall back to a humanized id.
const displayNameFor = (name, id) =>
  stripIsoSuffix(name) || humanizeId(id) || "(no region)";

// Fetch + parse JSON with non-200 detection and a clear error message.
// Throws Error on network failure, non-2xx, or malformed JSON.
async function fetchJson(url, opts) {
  let res;
  try {
    res = await fetch(url, opts);
  } catch (e) {
    throw new Error(`Network error reaching ${url}. Is the backend running?`);
  }
  if (!res.ok) {
    const body = await res.text().catch(() => "");
    throw new Error(`HTTP ${res.status} ${res.statusText}${body ? ` — ${body.slice(0, 200)}` : ""}`);
  }
  try {
    return await res.json();
  } catch (e) {
    throw new Error(`Bad response from ${url} (not JSON).`);
  }
}

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
  const todayP = fetchJson("/api/today");
  const regionsP = fetchJson("/api/regions");
  initMap();

  const today = await todayP;
  state.date = today?.date ?? null;
  state.year = today?.year ?? null;
  state.label = today?.label ?? "";
  state.era = today?.era_summary ?? "";
  const dayTag = $("day-tag");
  if (dayTag && today?.day_number != null) dayTag.textContent = `Day ${today.day_number}`;
  const yearLabel = $("year-label");
  if (yearLabel) yearLabel.textContent = state.label;
  const btn = $("btn-start");
  if (btn) {
    btn.disabled = false;
    btn.textContent = "Spin the globe →";
  }

  const regions = await regionsP;
  state.regions = Array.isArray(regions?.regions) ? regions.regions : [];

  await whenMapReady();
  addRegionLayer();
  attachHoverHandlers();

  // Restore "already played today" from localStorage.
  if (state.date) restoreSavedGuess();
}

// Restore a previously-submitted guess for today, if any. Tolerates corrupt
// localStorage by clearing the bad entry instead of crashing boot.
function restoreSavedGuess() {
  const key = `yearle:v1:guess:${state.date}`;
  const saved = localStorage.getItem(key);
  if (!saved) return;
  let payload;
  try {
    payload = JSON.parse(saved);
  } catch (e) {
    console.warn("discarding corrupt saved guess:", e);
    localStorage.removeItem(key);
    return;
  }
  state.played = true;
  $("start-card")?.classList.add("hidden");
  showReveal(payload);
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
        "space-color": "#3a2e1f",
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
    features: state.regions
      .filter(r => r && r.geometry)
      .map(r => ({
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

// Point features at region centroids for the on-globe labels.
function regionLabelsGeoJSON() {
  return {
    type: "FeatureCollection",
    features: state.regions
      .filter(r => Array.isArray(r?.centroid) && r.centroid.length >= 2)
      .map(r => ({
        type: "Feature",
        properties: { name: displayName(r) },
        geometry: { type: "Point", coordinates: [r.centroid[1], r.centroid[0]] },
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
  map.addSource(REGION_LABELS_SRC, { type: "geojson", data: regionLabelsGeoJSON() });
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
    if (state.year == null) {
      showToast("Still loading today's year — try again in a moment.", 2400);
      return;
    }
    const { lat, lng } = e.lngLat;
    setPick(lat, lng);
    state.mode = "submitting";
    setHudBusy(true);
    try {
      const payload = await fetchJson("/api/today/guess", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ year: state.year, lat, lon: lng }),
      });
      try {
        localStorage.setItem(`yearle:v1:guess:${state.date}`, JSON.stringify(payload));
      } catch (e) { /* private mode / quota — non-fatal, reveal still shows */ }
      showReveal(payload);
    } catch (err) {
      console.error("guess submit failed:", err);
      state.mode = "playing";
      clearPick();
      showToast(`Couldn't submit guess. ${err.message || err}`, 4000);
    } finally {
      setHudBusy(false);
    }
  } else if (state.mode === "explore") {
    const feats = map.queryRenderedFeatures(e.point, { layers: [REGION_FILL] });
    if (feats.length && feats[0]?.properties?.id) showExploreDetail(feats[0].properties.id);
  }
}

// Reflect a busy submit on the HUD hint (no new DOM; reuses the hover-region span).
function setHudBusy(busy) {
  const el = $("hud-hover-region");
  if (!el) return;
  if (busy) {
    el.dataset.prev = el.textContent;
    el.textContent = "Scoring your guess…";
  } else if (el.dataset.prev != null) {
    el.textContent = el.dataset.prev;
    delete el.dataset.prev;
  }
}

function clearPick() {
  const src = map?.getSource(PICK_SRC);
  if (src) src.setData({ type: "FeatureCollection", features: [] });
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
  const p = payload || {};
  const g = p.guess || {};
  const score = g.score ?? 0;
  const dayTag = $("day-tag")?.textContent || "";
  const factorOrder = ["safety", "health", "economy", "governance", "religious_tolerance"];
  const grid = factorOrder.map(k => scoreEmoji(g.factors?.[k] ?? 0)).join("");
  const url = location.origin || "yearl-e";
  const where = displayNameFor(g.region_name, g.region_id) || "?";
  const rank = (p.rank != null && p.total_regions != null) ? ` · rank ${p.rank}/${p.total_regions}` : "";
  return `yearl-e ${dayTag} · ${state.label}
${score}/100${rank} · ${where}
${grid}
${url}`;
}

function showToast(msg, ms = 1800) {
  const t = $("toast");
  if (!t) return;
  // Announce toasts (incl. errors) to assistive tech.
  t.setAttribute("role", "status");
  t.setAttribute("aria-live", "polite");
  t.textContent = msg;
  t.classList.remove("hidden");
  clearTimeout(showToast._h);
  showToast._h = setTimeout(() => t.classList.add("hidden"), ms);
}

async function shareResult() {
  const saved = localStorage.getItem(`yearle:v1:guess:${state.date}`);
  if (!saved) return;
  let payload;
  try { payload = JSON.parse(saved); } catch (e) { return; }
  const text = buildShareText(payload);
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

// Null-safe event binding — tolerates a missing DOM id without crashing init.
const on = (id, evt, fn) => { const el = $(id); if (el) el.addEventListener(evt, fn); };

// Track the element to restore focus to when a modal/card closes.
let lastFocused = null;
function openCard(id, focusId) {
  lastFocused = document.activeElement;
  const card = $(id);
  if (!card) return;
  card.classList.remove("hidden");
  const focusTarget = focusId ? $(focusId) : card;
  if (focusTarget && typeof focusTarget.focus === "function") {
    focusTarget.focus({ preventScroll: true });
  }
}
function closeCard(id) {
  $(id)?.classList.add("hidden");
  if (lastFocused && typeof lastFocused.focus === "function") {
    lastFocused.focus({ preventScroll: true });
  }
  lastFocused = null;
}

on("btn-share", "click", shareResult);

// ─── about modal ─────────────────────────────────────────────────────────────

on("link-about", "click", (e) => {
  e.preventDefault();
  openCard("about-card", "btn-about-close");
});
on("btn-about-close", "click", () => closeCard("about-card"));

on("btn-start", "click", () => {
  $("start-card")?.classList.add("hidden");
  $("hud")?.classList.remove("hidden");
  state.mode = "playing";
});

on("btn-explore", "click", async () => {
  if (state.year == null) {
    showToast("Year data isn't available right now.", 2400);
    return;
  }
  $("reveal-card")?.classList.add("hidden");
  $("explore-card")?.classList.remove("hidden");
  const yearEl = $("explore-year");
  if (yearEl) yearEl.textContent = state.label;
  $("overlay")?.classList.add("explore-mode");
  state.mode = "explore";
  const btn = $("btn-explore");
  if (btn) btn.disabled = true;
  // Fetch full year data + recolor by score.
  try {
    const res = await fetchJson(`/api/year/${state.year}/regions`);
    state._yearData = res?.regions || {};
    recolorRegions(state._yearData);
  } catch (err) {
    console.error("year regions fetch failed:", err);
    showToast(`Couldn't load the year's regions. ${err.message || err}`, 4000);
  } finally {
    if (btn) btn.disabled = false;
  }
});

on("btn-explore-close", "click", () => {
  $("explore-card")?.classList.add("hidden");
  $("overlay")?.classList.remove("explore-mode");
  $("reveal-card")?.classList.remove("hidden");
  state.mode = "reveal";
});

// Esc closes whichever overlay card is open (about → explore).
document.addEventListener("keydown", (e) => {
  if (e.key !== "Escape") return;
  if (!$("about-card")?.classList.contains("hidden")) {
    closeCard("about-card");
  } else if (!$("explore-card")?.classList.contains("hidden")) {
    $("btn-explore-close")?.click();
  }
});

// ─── rendering ───────────────────────────────────────────────────────────────

// Friendly tags for factor_sources values (which dataset/source produced the score).
const SOURCE_TAGS = {
  "maddison": { label: "Maddison", title: "Maddison Project 2023 GDP/cap" },
  "brecke":   { label: "Brecke",   title: "Brecke Conflict Catalog 1400-1999" },
  "ucdp":     { label: "UCDP",     title: "UCDP/PRIO Armed Conflict Dataset v25.1 (2000+ conflicts)" },
  "vdem":     { label: "V-Dem",    title: "Varieties of Democracy v15 — Electoral Democracy Index (polyarchy)" },
  "statehist": { label: "State Hist.", title: "State Antiquity Index (Borcan-Olsson-Putterman) — pre-1789 state-continuity governance proxy" },
  "wiki":     { label: "Wiki",     title: "Wikipedia (manual context)" },
  "neutral":  { label: "neutral",  title: "No sourced data — held at 50" },
  "baseline": { label: "era",      title: "Era baseline with manual adjustment" },
  "lifeexp":  { label: "Life exp.", title: "Life expectancy (Our World in Data: Riley, Zijdeman, UN) — country or regional" },
  "modeled":  { label: "modeled",  title: "Modeled estimate from the era's regional pattern (no direct dataset)" },
  "witch-trials": { label: "Witch trials", title: "Leeson & Russ witch-trial database — recorded persecution lowers tolerance" },
};

// Per-year emphasis banner: what the dynamic weights leaned on this year, with a
// compact readout of the (uniform, world-wide) factor weights.
function renderEmphasis(emphasis, weights) {
  const el = $("reveal-emphasis");
  if (!el) return;
  if (!emphasis) { el.classList.add("hidden"); el.innerHTML = ""; return; }
  let bars = "";
  if (weights && Object.keys(weights).length) {
    bars = `<div class="emphasis-weights">` + Object.entries(weights)
      .sort((a, b) => b[1] - a[1])
      .map(([k, v]) =>
        `<span class="ew" title="${escapeHtml(k.replace(/_/g, " "))}: ${Math.round(v * 100)}% weight">` +
        `${escapeHtml(k.replace(/_/g, " "))} ${Math.round(v * 100)}%</span>`)
      .join("") + `</div>`;
  }
  el.innerHTML = `<span class="emphasis-mark">⚖</span> <em>${escapeHtml(emphasis)}</em>${bars}`;
  el.classList.remove("hidden");
}

// Honest data-quality chip: how many of the 5 factors rest on real measured data.
function qualityChip(dq) {
  if (dq == null) return "";
  const n = Number(dq) || 0;
  const cls = n >= 4 ? "dq-good" : n <= 2 ? "dq-thin" : "dq-mid";
  const title = `${n}/5 factors from real measured data (rest modeled/neutral)`;
  return ` <span class="dq-chip ${cls}" title="${escapeHtml(title)}">data ${n}/5</span>`;
}

function renderFactors(factors, factorSources) {
  if (!factors || !Object.keys(factors).length) return "";
  return Object.entries(factors).map(([k, v]) => {
    const num = Number(v) || 0;
    const cls = num >= 70 ? "high" : num <= 35 ? "low" : "";
    const pct = Math.max(0, Math.min(100, num));
    const srcKey = factorSources?.[k];
    const tag = SOURCE_TAGS[srcKey];
    const srcChip = tag
      ? `<span class="src-chip src-${escapeHtml(srcKey)}" title="${escapeHtml(tag.title)}">${escapeHtml(tag.label)}</span>`
      : "";
    return `<div class="factor">
      <span class="factor-label">${escapeHtml(String(k).replace(/_/g, " "))}${srcChip}</span>
      <span class="factor-bar ${cls}"><span style="width:${pct}%"></span></span>
      <span class="factor-val">${num}</span>
    </div>`;
  }).join("");
}

// Only http(s) links are rendered as anchors; anything else is escaped text.
function safeUrl(url) {
  try {
    const u = new URL(url, location.origin);
    return (u.protocol === "http:" || u.protocol === "https:") ? u.href : null;
  } catch (e) {
    return null;
  }
}

function renderSources(sources) {
  if (!sources || !sources.length) return `<div class="muted">No sources cited yet.</div>`;
  return sources.map(s => {
    const label = escapeHtml(s?.label || s?.url || "source");
    const href = safeUrl(s?.url);
    return href
      ? `<a href="${escapeHtml(href)}" target="_blank" rel="noopener">↗ ${label}</a>`
      : `<span class="muted">↗ ${label}</span>`;
  }).join("");
}

const prefersReducedMotion = () =>
  window.matchMedia?.("(prefers-reduced-motion: reduce)").matches ?? false;

function countUp(el, target, duration = 700) {
  if (!el) return;
  const final = Number(target) || 0;
  // Respect reduced-motion: jump straight to the final value.
  if (prefersReducedMotion()) { el.textContent = String(final); return; }
  const start = performance.now();
  const from = 0;
  const tick = (t) => {
    const k = Math.min(1, (t - start) / duration);
    // ease-out cubic
    const eased = 1 - Math.pow(1 - k, 3);
    el.textContent = Math.round(from + (final - from) * eased);
    if (k < 1) requestAnimationFrame(tick);
    else el.textContent = String(final);
  };
  requestAnimationFrame(tick);
}

// Null-safe innerHTML write.
const setHtml = (id, html) => { const el = $(id); if (el) el.innerHTML = html; };

function showReveal(p) {
  if (!p || typeof p !== "object") return;
  state.mode = "reveal";
  $("hud")?.classList.add("hidden");
  const g = p.guess || {};
  const score = g.score ?? 0;
  const rankText = (p.rank != null && p.total_regions != null)
    ? `rank ${p.rank} of ${p.total_regions}` : "";
  // Legacy field (kept harmless if removed from DOM later).
  const legacy = $("reveal-score");
  if (legacy) legacy.textContent = `Your score: ${score} / 100 · ${rankText}`;
  const numEl = $("reveal-score-num");
  if (numEl) {
    numEl.textContent = "0";
    countUp(numEl, score);
  }
  const rankEl = $("reveal-score-rank");
  if (rankEl) rankEl.textContent = rankText;
  const eraYearEl = $("reveal-era-year");
  const eraSumEl = $("reveal-era-summary");
  if (eraYearEl) eraYearEl.textContent = p.label || state.label || "";
  if (eraSumEl) eraSumEl.textContent = p.era_summary || state.era || "";
  renderEmphasis(p.emphasis, p.weights);
  const pickName = displayNameFor(g.region_name, g.region_id);
  setHtml("reveal-pick",
    `<strong>You picked: ${escapeHtml(pickName)}</strong>${qualityChip(g.data_quality)}` +
    `<div>${escapeHtml(g.summary || "")}</div>`);
  setHtml("reveal-pick-factors", renderFactors(g.factors, g.factor_sources));
  setHtml("reveal-pick-sources", renderSources(g.sources));
  const top = p.top || {};
  const topName = displayNameFor(top.region_name, top.region_id);
  setHtml("reveal-top",
    `<strong>${escapeHtml(topName)} · ${top.score ?? 0}/100</strong>${qualityChip(top.data_quality)}` +
    `<div>${escapeHtml(top.summary || "")}</div>`);
  setHtml("reveal-top-factors", renderFactors(top.factors, top.factor_sources));
  setHtml("reveal-top-sources", renderSources(top.sources));
  $("reveal-card")?.classList.remove("hidden");
}

function showExploreDetail(rid) {
  const cell = state._yearData?.[rid];
  if (!cell) return;
  const region = state.regions.find(r => r.id === rid);
  const name = displayName(region || { id: rid });
  const ranking = Object.entries(state._yearData).sort((a, b) => (b[1].score ?? 0) - (a[1].score ?? 0));
  const rankIdx = ranking.findIndex(([id]) => id === rid) + 1;
  const cellScore = cell.score ?? 0;
  const scoreCls = cellScore >= 65 ? "high" : cellScore <= 40 ? "low" : "";
  const isWinner = rankIdx === 1;
  const rankPill = `<span class="ed-rank${isWinner ? " ed-rank-winner" : ""}">` +
    (isWinner ? "🏛 " : "") + `#${rankIdx} of ${ranking.length}</span>`;
  const rulerLine = cell.ruler
    ? `<div class="ed-ruler"><span class="ed-ruler-icon">👑</span>${escapeHtml(cell.ruler)}</div>` : "";
  const detail = $("explore-detail");
  if (!detail) return;
  detail.className = "";
  detail.innerHTML =
    `<div class="ed-header">
       <div class="ed-header-l">
         <div class="ed-name">${escapeHtml(name)}</div>
         ${rankPill}
       </div>
       <div class="ed-score ${scoreCls}">${cellScore}<span class="ed-score-denom">/100</span></div>
     </div>` +
    rulerLine +
    `<p class="ed-summary">${escapeHtml(cell.summary || "")}</p>` +
    `<div class="factors ed-factors">${renderFactors(cell.factors, cell.factor_sources)}</div>` +
    (cell.sources?.length
      ? `<div class="ed-sources"><span class="ed-sources-label">Sources</span>${renderSources(cell.sources)}</div>`
      : "");
}

// ─── go ──────────────────────────────────────────────────────────────────────

boot().catch(err => {
  console.error("boot failed:", err);
  const btn = $("btn-start");
  if (btn) {
    btn.disabled = true;
    btn.textContent = "Couldn't load — tap to retry";
    btn.classList.remove("hidden");
    btn.disabled = false;
    btn.onclick = () => location.reload();
    btn.setAttribute("aria-label", "Reload the page to retry loading");
  }
  showToast(`Couldn't load today's puzzle. ${err.message || err}`, 6000);
});
