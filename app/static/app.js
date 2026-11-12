/* TexDex front end. Plain JavaScript, no framework: each tab has a "load"
   function that asks the server for JSON and a "render" function that turns
   it into HTML. All game rules live on the server; this file only draws. */
"use strict";

const $ = (id) => document.getElementById(id);
const TABS = ["camera", "dex", "map", "profile"];
const TIER_LABEL = { common: "Common", uncommon: "Uncommon", rare: "Rare", very_rare: "Very Rare" };
const SEASONS = [["spring", "Sp"], ["summer", "Su"], ["fall", "Fa"], ["winter", "Wi"]];

const state = {
  tab: "camera", stream: null, coords: null, busy: false, lastPhotoUrl: null, authMode: "signup",
  dex: { region: null, group: null },
  map: { data: null, regions: [], region: null, pin: null, view: null },
};

/* ---------- small helpers ---------- */

// Text from the server is always escaped before it goes into HTML.
function esc(text) {
  return String(text ?? "").replace(/[&<>"']/g, (c) => (
    { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
}

async function api(path, options = {}) {
  if (options.json) {
    options.body = JSON.stringify(options.json);
    options.headers = { "Content-Type": "application/json" };
    options.method = options.method || "POST";
  }
  const response = await fetch(path, { credentials: "same-origin", ...options });
  let data = {};
  try { data = await response.json(); } catch (e) { /* empty body */ }
  if (response.status === 401 && path !== "/api/login") showAuth();
  return { ok: response.ok, status: response.status, data };
}

function toast(message) {
  const el = $("toast");
  el.textContent = message;
  el.classList.remove("hidden");
  clearTimeout(toast.timer);
  toast.timer = setTimeout(() => el.classList.add("hidden"), 2800);
}

// Animal icons arrive as an emoji (or "ray"). CSS class "ink" prints them in
// one sepia colour, so they read as an ink stamp rather than a sticker.
const RAY_SVG = '<svg viewBox="0 0 100 100"><path d="M50 6 94 44 60 60 52 96 48 96 40 60 6 44z"/></svg>';
const ink = (icon) => `<span class="ink">${icon === "ray" ? RAY_SVG : esc(icon)}</span>`;

// The picture box for a species:
//   photo  = the user's photo, taped in
//   blank  = an empty pencil frame with a faint sketch (not found yet)
//   sketch = just the ink sketch (used in lists)
function artHtml(sp, { photoUrl = null, blank = false } = {}) {
  if (photoUrl) return `<div class="art photo"><img src="${esc(photoUrl)}" alt="" loading="lazy"></div>`;
  if (blank) return `<div class="art blank">${ink(sp.icon)}<span class="q">?</span></div>`;
  return `<div class="art sketch">${ink(sp.icon)}</div>`;
}

const tierHtml = (tier) => `<span class="tier" data-tier="${esc(tier)}">${TIER_LABEL[tier] || ""}</span>`;
const shortDate = (iso) => new Date(iso.length === 10 ? iso + "T12:00:00" : iso)
  .toLocaleDateString(undefined, { month: "short", day: "numeric", year: "numeric" });
const dexNumber = (n) => "No. " + String(n).padStart(3, "0");

/* ---------- bottom sheet ---------- */

function openSheet(html, { onClose = null } = {}) {
  $("sheet").innerHTML = html;
  $("sheet").scrollTop = 0;
  $("sheet").classList.remove("hidden");
  $("sheet-backdrop").classList.remove("hidden");
  openSheet.onClose = onClose;
}
function closeSheet() {
  $("sheet").classList.add("hidden");
  $("sheet-backdrop").classList.add("hidden");
  const callback = openSheet.onClose;
  openSheet.onClose = null;
  if (callback) callback();
}
$("sheet-backdrop").addEventListener("click", closeSheet);

/* ---------- sign up / log in ---------- */

function showAuth() {
  stopCamera();
  $("auth").classList.remove("hidden");
  $("screens").classList.add("hidden");
  $("tabbar").classList.add("hidden");
}

document.querySelectorAll(".seg button").forEach((button) => button.addEventListener("click", () => {
  state.authMode = button.dataset.mode;
  document.querySelectorAll(".seg button").forEach((b) => b.classList.toggle("on", b === button));
  $("display-row").classList.toggle("hidden", state.authMode === "login");
  $("auth-submit").textContent = state.authMode === "login" ? "Open the journal" : "Start the journal";
  $("auth-error").textContent = "";
}));

$("auth-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  $("auth-error").textContent = "";
  const result = await api("/api/" + state.authMode, { json: {
    username: $("f-username").value, password: $("f-password").value, display_name: $("f-display").value } });
  if (!result.ok) { $("auth-error").textContent = result.data.error || "Something went wrong."; return; }
  $("f-password").value = "";
  enterApp();
});

function enterApp() {
  $("auth").classList.add("hidden");
  $("screens").classList.remove("hidden");
  $("tabbar").classList.remove("hidden");
  switchTab("camera");
}

/* ---------- tabs ---------- */

function switchTab(name) {
  state.tab = name;
  for (const tab of TABS) $("tab-" + tab).classList.toggle("hidden", tab !== name);
  document.querySelectorAll("#tabbar button").forEach((b) => b.classList.toggle("on", b.dataset.tab === name));
  // The camera only runs while its tab is showing (saves battery).
  if (name === "camera") startCamera(); else stopCamera();
  if (name === "dex") loadDex();
  if (name === "map") loadMap();
  if (name === "profile") loadProfile();
}
document.querySelectorAll("#tabbar button").forEach((b) => b.addEventListener("click", () => switchTab(b.dataset.tab)));

/* ---------- tab 1: camera ----------
   Live photos only. There is deliberately no "choose from camera roll"
   button and no file input: a journal entry is something you saw just now. */

async function startCamera() {
  watchLocation();
  if (state.stream || state.busy) return;
  if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) return cameraFallback(
    "This browser can't open a camera on this page. Phones only allow the camera on a secure (https) page.");
  try {
    // facingMode "environment" = the rear camera. "ideal" means: use it if
    // the device has one, otherwise any camera (a laptop webcam, say).
    state.stream = await navigator.mediaDevices.getUserMedia({
      audio: false, video: { facingMode: { ideal: "environment" }, width: { ideal: 1920 }, height: { ideal: 1080 } } });
  } catch (error) {
    return cameraFallback(error.name === "NotAllowedError"
      ? "Camera access is turned off for this page. Allow it in your browser's settings, then try again."
      : "We couldn't find a camera on this device.");
  }
  if (state.tab !== "camera") return stopCamera();
  $("cam").srcObject = state.stream;
  $("cam-fallback").classList.add("hidden");
  $("tab-camera").classList.remove("no-cam");
  ["reticle", "cam-hint", "shutter"].forEach((id) => $(id).classList.remove("hidden"));
  setupZoom();
}

function stopCamera() {
  if (state.stream) state.stream.getTracks().forEach((track) => track.stop());
  state.stream = null;
  $("cam").srcObject = null;
}

function cameraFallback(message) {
  $("cam-fallback-text").textContent = message;
  $("cam-fallback").classList.remove("hidden");
  $("tab-camera").classList.add("no-cam");
  ["reticle", "cam-hint", "shutter", "btn-zoom"].forEach((id) => $(id).classList.add("hidden"));
}
$("cam-retry").addEventListener("click", startCamera);

// Zoom button: only shown when the phone's camera reports that it can zoom.
function setupZoom() {
  const track = state.stream.getVideoTracks()[0];
  const caps = track.getCapabilities ? track.getCapabilities() : {};
  const button = $("btn-zoom");
  button.classList.toggle("hidden", !caps.zoom);
  $("zoom-space").classList.toggle("hidden", !!caps.zoom);
  if (!caps.zoom) return;
  const steps = [1, 2, 3].filter((z) => z >= caps.zoom.min && z <= caps.zoom.max);
  let index = 0;
  button.textContent = "1×";
  button.onclick = () => {
    index = (index + 1) % steps.length;
    track.applyConstraints({ advanced: [{ zoom: steps[index] }] });
    button.textContent = steps[index] + "×";
  };
}

// The phone's GPS reading. It is sent along with each photo, and that is
// what places the catch's pin on the Map tab.
function watchLocation() {
  if (watchLocation.started) return;
  if (!navigator.geolocation) { $("loc-chip").textContent = "No location on this device"; return; }
  watchLocation.started = true;
  navigator.geolocation.watchPosition(async (position) => {
    state.coords = { lat: position.coords.latitude, lon: position.coords.longitude };
    const result = await api(`/api/region?lat=${state.coords.lat}&lon=${state.coords.lon}`);
    const region = result.data.region;
    $("loc-chip").textContent = region ? region.name : "Outside Texas";
  }, () => {
    state.coords = null;
    $("loc-chip").textContent = "Location off: no map pin";
  }, { enableHighAccuracy: true, maximumAge: 60000, timeout: 15000 });
}

$("shutter").addEventListener("click", () => {
  const video = $("cam");
  if (!state.stream || !video.videoWidth || state.busy) return;
  // Copy the current video frame onto a canvas, shrunk to at most 1600 px.
  const scale = Math.min(1, 1600 / Math.max(video.videoWidth, video.videoHeight));
  const canvas = document.createElement("canvas");
  canvas.width = Math.round(video.videoWidth * scale);
  canvas.height = Math.round(video.videoHeight * scale);
  canvas.getContext("2d").drawImage(video, 0, 0, canvas.width, canvas.height);
  canvas.toBlob((blob) => sendPhoto(blob), "image/jpeg", 0.92);
});

const SCAN_NOTES = ["comparing against Texas species…", "checking what lives here this month…",
  "looking at shape, pattern and colour…", "weighing the three best matches…"];

async function sendPhoto(blob) {
  if (state.busy) return;
  state.busy = true;
  if (state.lastPhotoUrl) URL.revokeObjectURL(state.lastPhotoUrl);
  state.lastPhotoUrl = URL.createObjectURL(blob);
  $("frozen").src = state.lastPhotoUrl;
  $("frozen").classList.remove("hidden");
  $("scan").classList.remove("hidden");
  $("shutter").disabled = true;

  const status = (await api("/api/status")).data;
  let note = 0;
  $("scan-fact").textContent = status.model_ready ? SCAN_NOTES[0]
    : "waking up the ID model; the first photo can take about a minute…";
  const ticker = setInterval(() => {
    if (status.model_ready) $("scan-fact").textContent = SCAN_NOTES[++note % SCAN_NOTES.length];
  }, 1800);

  const form = new FormData();
  form.append("photo", blob, "photo.jpg");
  if (state.coords) { form.append("lat", state.coords.lat); form.append("lon", state.coords.lon); }
  let result;
  try {
    result = await api("/api/identify", { method: "POST", body: form });
  } catch (e) {
    result = { ok: false, data: { error: { title: "No connection",
      message: "We couldn't reach TexDex.", tip: "Check your signal and try again." } } };
  }
  clearInterval(ticker);
  $("scan").classList.add("hidden");

  if (result.ok && result.data.ok) showGuesses(result.data);
  else showPhotoError(result.data.error);
}

function resetCamera() {
  state.busy = false;
  $("frozen").classList.add("hidden");
  $("shutter").disabled = false;
  if (state.tab === "camera") startCamera();
}

function showPhotoError(error) {
  // The server sends {title, message, tip} in plain language; we just show it.
  if (!error || typeof error === "string") {
    error = { title: "That didn't work", message: error || "Something went wrong on our side.", tip: "Please try again." };
  }
  openSheet(`
    <h3 class="sheet-title">${esc(error.title)}</h3>
    <p class="sheet-sub">${esc(error.message)}</p>
    <p class="note tip">${esc(error.tip)}</p>
    <div class="row"><button class="btn primary" id="err-retry">Take another</button></div>`, { onClose: resetCamera });
  $("err-retry").addEventListener("click", closeSheet);
}

function guessHtml(guess, top) {
  const percent = Math.round(guess.confidence * 100);
  return `<button class="guess${top ? " top" : ""}" data-species="${esc(guess.species_id)}">
    ${artHtml(guess)}
    <div>
      <strong>${esc(guess.common_name)}</strong>
      <em>${esc(guess.scientific_name)}</em>
      <div class="match">${tierHtml(guess.tier)}<span>${percent}% match</span></div>
    </div></button>`;
}

function showGuesses(data) {
  const [top, ...others] = data.guesses;
  const where = data.region ? ` in the ${esc(data.region.name)}` : "";
  openSheet(`
    <h3 class="sheet-title">Is this what you saw?</h3>
    <p class="sheet-sub">The closest match${where}. Tap the animal you photographed.</p>
    ${guessHtml(top, true)}
    ${others.length ? '<p class="sec">Or possibly</p>' + others.map((g) => guessHtml(g, false)).join("") : ""}
    <div class="row"><button class="btn plain" id="none-btn">None of these, retake</button></div>`, { onClose: resetCamera });
  $("none-btn").addEventListener("click", closeSheet);
  $("sheet").querySelectorAll(".guess").forEach((button) => button.addEventListener("click", async () => {
    const result = await api("/api/catches", { json: { pending_id: data.pending_id, species_id: button.dataset.species } });
    openSheet.onClose = null;  // don't restart the camera underneath the new entry
    closeSheet();
    if (result.ok) showReveal(result.data);
    else { toast(result.data.error || "That catch didn't save."); resetCamera(); }
  }));
}

/* ---------- the new journal entry shown after a catch ---------- */

function showReveal(r) {
  const sp = r.species, lvl = r.level, el = $("reveal");
  const percent = Math.round(100 * lvl.xp_into_level / lvl.xp_for_level);
  const today = new Date().toLocaleDateString(undefined, { weekday: "long", month: "long", day: "numeric", year: "numeric" });
  el.innerHTML = `
    <p class="rv-date">${esc(today)}${r.region ? " · " + esc(r.region.name) : ""}</p>
    <div class="rv-photo">
      ${artHtml(sp, { photoUrl: state.lastPhotoUrl })}
      <span class="rv-stamp${r.is_new_species ? "" : " again"}">${r.is_new_species ? "New species" : "Seen again"}</span>
    </div>
    <div class="rv-name">
      <p class="rv-date">${dexNumber(sp.number)} · ${esc(sp.group_label)} · ${esc(sp.family)}</p>
      <h3>${esc(sp.common_name)}</h3>
      <em>${esc(sp.scientific_name)}</em>
      ${tierHtml(sp.tier)}
    </div>
    ${sp.venomous ? '<p class="note warn">Venomous. Admire it from a distance; never touch, corner or pick it up.</p>' : ""}
    ${r.location_blurred ? '<p class="note shield">Protected species. To keep it safe, only a rough area was saved, not the exact spot.</p>' : ""}
    <p class="rv-xp">+${r.xp} XP</p>
    <div class="rank">
      <div class="line"><span>${r.leveled_up ? "Promoted: " : ""}Level ${lvl.level}, ${esc(lvl.title)}</span><span>${lvl.xp_to_next} XP to go</span></div>
      <div class="meter"><i id="rv-bar"></i></div>
    </div>
    ${r.new_badges.length ? `<p class="sec">New stamp${r.new_badges.length > 1 ? "s" : ""}</p>
      <div class="badges">${r.new_badges.map((b) => `<div class="badge earned"><i>${ink(b.icon)}</i><span>${esc(b.name)}</span></div>`).join("")}</div>` : ""}
    <p class="foot-note">${r.species_count} species in your Dex.</p>
    <div class="row">
      <button class="btn" id="rv-dex">Open the Dex</button>
      <button class="btn primary" id="rv-more">Keep exploring</button>
    </div>`;
  el.scrollTop = 0;
  el.classList.remove("hidden");
  setTimeout(() => { const bar = $("rv-bar"); if (bar) bar.style.width = percent + "%"; }, 600);
  const done = (tab) => { el.classList.add("hidden"); el.innerHTML = ""; state.busy = false;
    $("frozen").classList.add("hidden"); $("shutter").disabled = false; switchTab(tab); };
  $("rv-dex").addEventListener("click", () => done("dex"));
  $("rv-more").addEventListener("click", () => done("camera"));
}

/* ---------- region and group tabs (shared by the Dex and the Map) ---------- */

function regionTabsHtml(regions, selected, countOf) {
  return `<button class="tab${selected ? "" : " on"}" data-region="">All Texas</button>` +
    regions.map((r) => `<button class="tab${r.code === selected ? " on" : ""}" data-region="${esc(r.code)}" style="--c:${esc(r.color)}">
      <i class="sw"></i>${esc(r.name)} <small>${esc(countOf(r))}</small></button>`).join("");
}

function wireStrip(stripId, attribute, onPick) {
  const strip = $(stripId);
  strip.querySelectorAll(".tab").forEach((b) => b.addEventListener("click", () => onPick(b.dataset[attribute] || null)));
  const selected = strip.querySelector(".tab.on");
  if (selected) selected.scrollIntoView({ block: "nearest", inline: "center" });
}

/* ---------- tab 2: the Dex ---------- */

async function loadDex() {
  const query = new URLSearchParams();
  if (state.dex.region) query.set("region", state.dex.region);
  if (state.dex.group) query.set("group", state.dex.group);
  const [dex, status] = await Promise.all([api("/api/dex?" + query), api("/api/status")]);
  if (!dex.ok) return;
  $("demo-note").classList.toggle("hidden", !status.data.demo_data);
  renderDex(dex.data);
}

function renderDex(data) {
  const d = state.dex;
  $("dex-tally").innerHTML = `<b>${data.caught}</b> / ${data.total}<br>found`;
  $("dex-sub").textContent = "Every animal, region by region";

  const region = data.regions.find((r) => r.code === d.region);
  const found = data.entries.filter((e) => e.caught).length;
  $("region-name").textContent = region ? region.name : "All of Texas";
  $("region-blurb").textContent = (region ? region.blurb + ". " : "") + `${found} of ${data.entries.length} on this page found.`;

  $("region-tabs").innerHTML = regionTabsHtml(data.regions, d.region, (r) => `${r.caught}/${r.total}`);
  // Tapping the tab that is already selected clears that filter.
  wireStrip("region-tabs", "region", (code) => { d.region = code === d.region ? null : code; loadDex(); });

  $("group-tabs").innerHTML =
    `<button class="tab${d.group ? "" : " on"}" data-group="">All animals</button>` +
    data.groups.map((g) => `<button class="tab${g.key === d.group ? " on" : ""}" data-group="${esc(g.key)}">
      ${esc(g.label)} <small>${g.caught}/${g.total}</small></button>`).join("");
  wireStrip("group-tabs", "group", (key) => { d.group = key === d.group ? null : key; loadDex(); });

  $("dex-grid").innerHTML = data.entries.length ? data.entries.map((e) => `
    <button class="card${e.caught ? " caught" : ""}" data-tier="${esc(e.tier)}" data-species="${esc(e.species_id)}">
      <span class="num"><span>${dexNumber(e.number)}</span><i>${TIER_LABEL[e.tier] || ""}</i></span>
      ${artHtml(e, { photoUrl: e.caught ? "/api/photos/" + e.photo_id : null, blank: true })}
      <span class="nm">${esc(e.common_name)}</span>
    </button>`).join("")
    : '<p class="empty">Nothing on this page. Try another region or group.</p>';
  $("dex-grid").querySelectorAll(".card").forEach((c) => c.addEventListener("click", () => openSpecies(c.dataset.species)));
}

async function openSpecies(speciesId) {
  const result = await api("/api/species/" + encodeURIComponent(speciesId));
  if (!result.ok) return;
  const sp = result.data, caught = sp.catches.length > 0;
  const where = sp.regions.map((r) => `
    <div class="where" style="--c:${esc(r.color)}"><i class="sw"></i><span>${esc(r.name)}</span>
      <div class="seasons">${SEASONS.map(([key, short]) => r.seasons[key]
        ? `<i data-tier="${esc(r.seasons[key])}" title="${TIER_LABEL[r.seasons[key]]} in ${key}">${short}</i>` : `<i>${short}</i>`).join("")}</div>
    </div>`).join("");
  openSheet(`
    <div class="sp-hero">
      ${artHtml(sp, { photoUrl: caught ? "/api/photos/" + sp.catches[0].catch_id : null, blank: true })}
      <div>
        <div class="num">${dexNumber(sp.number)}</div>
        <h3>${esc(sp.common_name)}</h3>
        <em>${esc(sp.scientific_name)}</em>
        ${tierHtml(sp.tier)}
        <p class="facts">${esc(sp.group_label)} · family ${esc(sp.family)}</p>
      </div>
    </div>
    ${sp.venomous ? '<p class="note warn">Venomous. Keep your distance; never touch, corner or pick up this animal.</p>' : ""}
    ${sp.protected ? '<p class="note shield">Protected in Texas. Where it was photographed is only ever shown as a rough area.</p>' : ""}
    <p class="note">${caught
      ? `Photographed ${sp.catches.length} time${sp.catches.length > 1 ? "s" : ""}. First on ${shortDate(sp.catches[sp.catches.length - 1].caught_at)}.`
      : "Not found yet. The regions and seasons below say where to look."}</p>
    <p class="sec">Where and when it lives</p>
    ${where || '<p class="muted">No region records yet.</p>'}
    <div class="legend">${Object.keys(TIER_LABEL).map(tierHtml).join("")}</div>
    <div class="row"><button class="btn" id="sp-close">Close</button></div>`);
  $("sp-close").addEventListener("click", closeSheet);
}

/* ---------- tab 3: the map ----------
   Every catch that had a location is a pin. Tap a region (on the map or in
   the tabs) to zoom in and see only the photos taken there. */

async function loadMap() {
  const [map, dex] = await Promise.all([api("/api/map"), api("/api/dex")]);
  if (!map.ok || !dex.ok) return;
  state.map.data = map.data;
  state.map.regions = dex.data.regions;
  renderMap();
}

function pickRegion(code) {
  state.map.region = code === state.map.region ? null : code;
  state.map.pin = null;
  renderMap();
}

// The rectangle of the drawing to show: all of Texas, or one region with a margin.
function mapView(map, regionCode) {
  const whole = [-10, -10, map.width + 20, map.height + 20];
  const shape = map.regions.find((r) => r.code === regionCode);
  if (!shape || !shape.bbox) return whole;
  const [x0, y0, x1, y1] = shape.bbox;
  // Keep at least a quarter of the map in view so tiny regions aren't a blur of pixels.
  let w = Math.max(x1 - x0, map.width / 4) * 1.3, h = Math.max(y1 - y0, map.height / 4) * 1.3;
  // Keep the same shape as the full map, so the map box doesn't change height when zooming.
  const shapeOfMap = whole[2] / whole[3];
  if (w / h > shapeOfMap) h = w / shapeOfMap; else w = h * shapeOfMap;
  return [(x0 + x1) / 2 - w / 2, (y0 + y1) / 2 - h / 2, w, h];
}

function renderMap() {
  const m = state.map, map = m.data, box = $("map-box");
  const info = m.regions.find((r) => r.code === m.region);
  if (!map.available) {
    box.innerHTML = '<p class="map-empty">The map appears once the region shapes are downloaded:<br>python -m data_engine.fetch_ecoregions</p>';
    $("map-regions").innerHTML = $("map-list").innerHTML = "";
    return;
  }
  const colour = Object.fromEntries(m.regions.map((r) => [r.code, r.color]));
  const shown = map.pins.map((p, i) => ({ ...p, i })).filter((p) => !m.region || p.region === m.region);
  const view = mapView(map, m.region);
  const r = view[2] * 0.01;  // pin size follows the zoom, so pins look the same size on screen

  // clip-path cuts every region off at the Texas outline, because the EPA
  // shapes carry on into neighbouring states.
  box.innerHTML = `
    <svg viewBox="${(m.view || view).join(" ")}" class="tx${m.region ? " zoomed" : ""}">
      <defs><clipPath id="tx-clip"><path d="${map.outline}"/></clipPath></defs>
      <g clip-path="url(#tx-clip)">
        ${map.regions.map((s) => `<path class="rg${s.code === m.region ? " on" : ""}" data-region="${esc(s.code)}" fill="${esc(colour[s.code] || "#b9a878")}" d="${s.path}"/>`).join("")}
      </g>
      <path class="outline" d="${map.outline}"/>
      ${m.region ? "" : map.regions.filter((s) => s.label).map((s) => `<text class="lbl" x="${s.label[0]}" y="${s.label[1] + 9}" font-size="26">${esc(s.code)}</text>`).join("")}
      ${shown.map((p) => `<g class="pin${p.mine ? " mine" : ""}${p.i === m.pin ? " sel" : ""}" data-pin="${p.i}">
        ${p.approximate ? `<circle class="halo" cx="${p.x}" cy="${p.y}" r="${r * 3.2}"/>` : ""}
        <circle cx="${p.x}" cy="${p.y}" r="${p.mine ? r : r * 0.8}"/></g>`).join("")}
    </svg>
    <svg class="compass" viewBox="0 0 40 40"><circle cx="20" cy="22" r="13" fill="none" stroke="#2b2620"/><path d="M20 9l4 13h-8z" fill="#2b2620"/><path d="M20 35l-4-13h8z" fill="none" stroke="#2b2620"/><text x="20" y="7" font-size="8" text-anchor="middle" font-family="monospace">N</text></svg>
    ${colour.outside_land ? `<button class="gulf-btn${m.region === "outside_land" ? " on" : ""}" data-region="outside_land">Gulf waters</button>` : ""}`;
  zoomTo(box.querySelector("svg.tx"), view);
  box.querySelectorAll("[data-region]").forEach((el) => el.addEventListener("click", () => pickRegion(el.dataset.region)));
  box.querySelectorAll(".pin").forEach((el) => el.addEventListener("click", () => openPin(Number(el.dataset.pin))));

  const pinsIn = (code) => map.pins.filter((p) => p.region === code).length;
  $("map-regions").innerHTML = regionTabsHtml(m.regions, m.region, (reg) => pinsIn(reg.code) || "");
  wireStrip("map-regions", "region", (code) => { if (code) pickRegion(code); else { m.region = null; m.pin = null; renderMap(); } });

  const mine = shown.filter((p) => p.mine).length;
  $("map-region-name").textContent = info ? info.name : "All of Texas";
  $("map-region-blurb").textContent = (info ? info.blurb + ". " : "Tap a region to see the photos taken there. ") +
    (shown.length ? `${shown.length} photo${shown.length > 1 ? "s" : ""} pinned, ${mine} of them yours.` : "No photos pinned here yet.");

  $("map-list").innerHTML = shown.map((p) => `
    <button class="entry${p.i === m.pin ? " sel" : ""}" data-pin="${p.i}">
      ${artHtml(p, { photoUrl: p.catch_id ? "/api/photos/" + p.catch_id : null })}
      <span><strong>${esc(p.common_name)}</strong><small>${shortDate(p.date)} · ${p.mine ? "your photo" : "another ranger"}${p.approximate ? " · rough area" : ""}</small></span>
      ${tierHtml(p.tier)}
    </button>`).join("");
  $("map-list").querySelectorAll(".entry").forEach((el) => el.addEventListener("click", () => openPin(Number(el.dataset.pin))));
}

// Slide the map's view from where it was to the new rectangle (about a third of a second).
function zoomTo(svg, target) {
  const from = state.map.view || target, start = Date.now();
  state.map.view = target;
  clearInterval(zoomTo.timer);
  zoomTo.timer = setInterval(() => {
    const t = Math.min(1, (Date.now() - start) / 320), ease = t * (2 - t);
    svg.setAttribute("viewBox", from.map((v, k) => v + (target[k] - v) * ease).join(" "));
    if (t === 1) clearInterval(zoomTo.timer);
  }, 16);
}

function openPin(index) {
  const m = state.map, p = m.data.pins[index];
  const region = m.regions.find((r) => r.code === p.region);
  m.pin = index;
  renderMap();
  openSheet(`
    <div class="sp-hero">
      ${artHtml(p, { photoUrl: p.catch_id ? "/api/photos/" + p.catch_id : null })}
      <div>
        <div class="num">${shortDate(p.date)}</div>
        <h3>${esc(p.common_name)}</h3>
        ${tierHtml(p.tier)}
        <p class="facts">${region ? esc(region.name) : "Texas"}<br>${p.mine ? "Your photo" : "Logged by another ranger"}</p>
      </div>
    </div>
    ${p.approximate ? '<p class="note shield">Protected species. This pin only marks a rough area about 25 km across, never the exact spot.</p>' : ""}
    <div class="row">
      <button class="btn" id="pin-species">Open in the Dex</button>
      <button class="btn primary" id="pin-close">Back to the map</button>
    </div>`, { onClose: () => { m.pin = null; if (state.tab === "map") renderMap(); } });
  $("pin-close").addEventListener("click", closeSheet);
  $("pin-species").addEventListener("click", () => { closeSheet(); openSpecies(p.species_id); });
}

/* ---------- tab 4: profile ---------- */

async function loadProfile() {
  const [profile, status] = await Promise.all([api("/api/profile"), api("/api/status")]);
  if (profile.ok) renderProfile(profile.data, status.data);
}

function renderProfile(p, status) {
  const lvl = p.level, s = p.stats;
  const percent = Math.round(100 * lvl.xp_into_level / lvl.xp_for_level);
  $("profile-body").innerHTML = `
    <div class="owner">
      <div class="seal">${ink(p.user.avatar)}</div>
      <div>
        <small>This journal belongs to</small>
        <h2>${esc(p.user.display_name)}</h2>
        <p>@${esc(p.user.username)} · since ${shortDate(p.user.created_at)}</p>
      </div>
    </div>
    <div class="rank">
      <div class="line"><span>Level ${lvl.level}</span><b>${esc(lvl.title)}</b></div>
      <div class="meter"><i style="width:${percent}%"></i></div>
      <small>${lvl.xp} XP · ${lvl.xp_to_next} more to Level ${lvl.level + 1}</small>
    </div>
    <p class="sec">Tally</p>
    <table class="ledger">
      <tr><td>Species found</td><td>${s.species} <small>of ${s.species_total}</small></td></tr>
      <tr><td>Photos logged</td><td>${s.catches}</td></tr>
      <tr><td>Regions explored</td><td>${s.regions} <small>of ${s.regions_total}</small></td></tr>
      <tr><td>Rarest find</td><td>${s.rarest ? esc(s.rarest.common_name) : "none yet"}</td></tr>
    </table>
    <p class="sec">By kind of animal</p>
    ${p.groups.map((g) => `<div class="gp">${ink(g.icon)}
      <div>${esc(g.label)}<div class="meter"><i style="width:${100 * g.caught / Math.max(1, g.total)}%"></i></div></div>
      <span>${g.caught}/${g.total}</span></div>`).join("")}
    <p class="sec">Stamps · ${p.badges.filter((b) => b.earned).length} of ${p.badges.length}</p>
    <div class="badges">${p.badges.map((b) => `<button class="badge${b.earned ? " earned" : ""}" data-hint="${esc(b.name + ": " + b.hint)}">
      <i>${ink(b.icon)}</i><span>${esc(b.name)}</span></button>`).join("")}</div>
    <p class="sec">Latest entries</p>
    ${p.recent.length ? `<div class="recent">${p.recent.map((c) => `<div class="rc">
      <div class="art photo"><img src="/api/photos/${c.catch_id}" alt="" loading="lazy"></div>
      <strong>${esc(c.common_name)}</strong><small>${shortDate(c.caught_at)} · +${c.xp} XP</small></div>`).join("")}</div>`
      : '<p class="hand muted">Nothing yet. Take your first photo on the Catch tab.</p>'}
    <div class="foot">
      <p class="foot-note">${status.fake_id ? "ID engine: demo mode (guesses are random). Start the app with --bioclip for real identification." : "ID engine: BioCLIP 2 with the local-species boost."}
        ${status.demo_data ? " Species data: demo set (illustrative regions and rarity)." : ""}</p>
      <div class="row" style="margin-top:0"><button class="btn" id="edit-profile">Edit name and seal</button><button class="btn danger" id="logout">Log out</button></div>
    </div>`;
  $("profile-body").querySelectorAll(".badge").forEach((b) => b.addEventListener("click", () => toast(b.dataset.hint)));
  $("logout").addEventListener("click", async () => { await api("/api/logout", { method: "POST" }); showAuth(); });
  $("edit-profile").addEventListener("click", () => editProfile(p));
}

function editProfile(p) {
  let avatar = p.user.avatar;
  openSheet(`
    <h3 class="sheet-title">Name and seal</h3>
    <p class="sheet-sub">How the inside cover of your journal reads.</p>
    <label>This journal belongs to<input id="edit-name" maxlength="30" value="${esc(p.user.display_name)}"></label>
    <p class="sec">Seal</p>
    <div class="avatars">${p.avatars.map((a) => `<button class="${a === avatar ? "on" : ""}" data-avatar="${esc(a)}">${ink(a)}</button>`).join("")}</div>
    <div class="row"><button class="btn primary" id="edit-save">Save</button></div>`);
  $("sheet").querySelectorAll(".avatars button").forEach((b) => b.addEventListener("click", () => {
    avatar = b.dataset.avatar;
    $("sheet").querySelectorAll(".avatars button").forEach((x) => x.classList.toggle("on", x === b));
  }));
  $("edit-save").addEventListener("click", async () => {
    const result = await api("/api/profile", { json: { display_name: $("edit-name").value, avatar } });
    if (!result.ok) return toast(result.data.error || "Couldn't save.");
    closeSheet();
    loadProfile();
  });
}

/* ---------- start ---------- */

(async function boot() {
  const status = (await api("/api/status")).data;
  if (status.logged_in) enterApp(); else showAuth();
})();
