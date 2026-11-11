/* TexDex front end. Plain JavaScript, no framework: each tab has a "load"
   function that asks the server for JSON and a "render" function that turns
   it into HTML. All game rules live on the server; this file only draws. */
"use strict";

const $ = (id) => document.getElementById(id);
const TIER_LABEL = { common: "Common", uncommon: "Uncommon", rare: "Rare", very_rare: "Very Rare" };
const SEASONS = [["spring", "Sp"], ["summer", "Su"], ["fall", "Fa"], ["winter", "Wi"]];
const ERROR_ICON = { blurry: "🌫️", too_far: "🔭", too_dark: "🌑", too_bright: "☀️", not_clear: "🕵️",
  not_a_photo: "📄", duplicate: "♻️", too_small: "🔍", too_big: "🐘" };

const state = {
  status: {}, tab: "camera", stream: null, coords: null, busy: false,
  dex: { region: null, group: null }, map: null, lastPhotoUrl: null, authMode: "signup",
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
  toast.timer = setTimeout(() => el.classList.add("hidden"), 2600);
}

const RAY_SVG = '<svg viewBox="0 0 100 100"><path fill="#8fb8e8" d="M50 6 94 44 60 60 52 96 48 96 40 60 6 44z"/></svg>';
const iconHtml = (icon) => (icon === "ray" ? RAY_SVG : esc(icon));

// The picture box for a species: the user's photo if caught, else a silhouette.
function artHtml(sp, { photoUrl = null, silhouette = true } = {}) {
  if (photoUrl) return `<div class="art"><img src="${esc(photoUrl)}" alt="" loading="lazy"></div>`;
  return `<div class="art"><span class="sil"${silhouette ? "" : ' style="filter:none;opacity:1"'}>${iconHtml(sp.icon)}</span>${
    silhouette ? '<span class="q">?</span>' : ""}</div>`;
}

const shortDate = (iso) => new Date(iso).toLocaleDateString(undefined, { month: "short", day: "numeric", year: "numeric" });
const dexNumber = (n) => "#" + String(n).padStart(3, "0");

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
  $("auth-submit").textContent = state.authMode === "login" ? "Log in" : "Start exploring";
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
  state.map = null;
  switchTab("camera");
}

/* ---------- tabs ---------- */

function switchTab(name) {
  state.tab = name;
  for (const tab of ["camera", "dex", "profile"]) {
    $("tab-" + tab).classList.toggle("hidden", tab !== name);
  }
  document.querySelectorAll("#tabbar button").forEach((b) => b.classList.toggle("on", b.dataset.tab === name));
  // The camera only runs while its tab is showing (saves battery).
  if (name === "camera") startCamera(); else stopCamera();
  if (name === "dex") loadDex();
  if (name === "profile") loadProfile();
}
document.querySelectorAll("#tabbar button").forEach((b) => b.addEventListener("click", () => switchTab(b.dataset.tab)));

/* ---------- tab 1: camera ---------- */

async function startCamera() {
  watchLocation();
  if (state.stream || state.busy) return;
  if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) return cameraFallback(
    "This browser can't open a camera here. Phones only allow the camera on a secure (https) page.");
  try {
    // facingMode "environment" = the rear camera. "ideal" means: use it if
    // the device has one, otherwise any camera (a laptop webcam, say).
    state.stream = await navigator.mediaDevices.getUserMedia({
      audio: false, video: { facingMode: { ideal: "environment" }, width: { ideal: 1920 }, height: { ideal: 1080 } } });
  } catch (error) {
    return cameraFallback(error.name === "NotAllowedError"
      ? "Camera access is turned off for this page. Allow it in your browser settings, or add a photo from your files."
      : "We couldn't find a camera on this device. You can still add a photo from your files.");
  }
  if (state.tab !== "camera") return stopCamera();
  $("cam").srcObject = state.stream;
  $("cam-fallback").classList.add("hidden");
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
  ["reticle", "cam-hint", "shutter", "btn-zoom"].forEach((id) => $(id).classList.add("hidden"));
}

// Zoom button: only shown when the phone's camera reports that it can zoom.
function setupZoom() {
  const track = state.stream.getVideoTracks()[0];
  const caps = track.getCapabilities ? track.getCapabilities() : {};
  const button = $("btn-zoom");
  if (!caps.zoom) { button.classList.add("hidden"); return; }
  const steps = [1, 2, 3].filter((z) => z >= caps.zoom.min && z <= caps.zoom.max);
  let index = 0;
  button.classList.remove("hidden");
  button.textContent = "1×";
  button.onclick = () => {
    index = (index + 1) % steps.length;
    track.applyConstraints({ advanced: [{ zoom: steps[index] }] });
    button.textContent = steps[index] + "×";
  };
}

function watchLocation() {
  if (watchLocation.started || !navigator.geolocation) {
    if (!navigator.geolocation) $("loc-chip").textContent = "📍 No location";
    return;
  }
  watchLocation.started = true;
  navigator.geolocation.watchPosition(async (position) => {
    state.coords = { lat: position.coords.latitude, lon: position.coords.longitude };
    const result = await api(`/api/region?lat=${state.coords.lat}&lon=${state.coords.lon}`);
    const region = result.data.region;
    $("loc-chip").textContent = region ? "📍 " + region.name : "📍 Outside Texas";
  }, () => {
    state.coords = null;
    $("loc-chip").textContent = "📍 Location off";
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
$("btn-upload").addEventListener("click", () => $("file-input").click());
$("fallback-upload").addEventListener("click", () => $("file-input").click());
$("file-input").addEventListener("change", (event) => {
  const file = event.target.files[0];
  event.target.value = "";
  if (file) sendPhoto(file);
});

const SCAN_FACTS = ["Comparing against Texas species", "Checking what lives here this month",
  "Looking at shape, pattern and colour", "Weighing the three best matches"];

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
  let fact = 0;
  $("scan-fact").textContent = status.model_ready ? SCAN_FACTS[0]
    : "Waking up the ID model. The first photo can take about a minute.";
  const ticker = setInterval(() => {
    if (status.model_ready) $("scan-fact").textContent = SCAN_FACTS[++fact % SCAN_FACTS.length];
  }, 1800);

  const form = new FormData();
  form.append("photo", blob, "photo.jpg");
  if (state.coords) { form.append("lat", state.coords.lat); form.append("lon", state.coords.lon); }
  let result;
  try {
    result = await api("/api/identify", { method: "POST", body: form });
  } catch (e) {
    result = { ok: false, data: { error: { code: "offline", title: "No connection",
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
    error = { code: "", title: "That didn't work", message: error || "Something went wrong on our side.",
      tip: "Please try again." };
  }
  openSheet(`
    <div class="err-icon">${ERROR_ICON[error.code] || "🤔"}</div>
    <h3 class="sheet-title" style="text-align:center">${esc(error.title)}</h3>
    <p class="sheet-sub" style="text-align:center">${esc(error.message)}</p>
    <div class="tipbox"><span>💡</span><span>${esc(error.tip)}</span></div>
    <button class="btn primary big" id="err-retry">Try again</button>`, { onClose: resetCamera });
  $("err-retry").addEventListener("click", closeSheet);
}

function guessHtml(guess, top) {
  const percent = Math.round(guess.confidence * 100);
  return `<button class="guess${top ? " top" : ""}" data-tier="${esc(guess.tier)}" data-species="${esc(guess.species_id)}">
    ${artHtml(guess, { silhouette: false })}
    <div class="info">
      <strong>${esc(guess.common_name)}</strong>
      <em>${esc(guess.scientific_name)}</em>
      <div class="match"><span class="gem">${TIER_LABEL[guess.tier] || ""}</span>
        <div class="bar"><i style="width:${percent}%"></i></div><span>${percent}% match</span></div>
    </div></button>`;
}

function showGuesses(data) {
  const [top, ...others] = data.guesses;
  const where = data.region ? ` in the ${esc(data.region.name)}` : "";
  openSheet(`
    <h3 class="sheet-title">Is this your animal?</h3>
    <p class="sheet-sub">Our best match${where}. Tap the one you photographed.</p>
    ${guessHtml(top, true)}
    ${others.length ? '<p class="sec">Or maybe</p>' + others.map((g) => guessHtml(g, false)).join("") : ""}
    <button class="btn ghost big" id="none-btn">None of these. Retake</button>`, { onClose: resetCamera });
  $("none-btn").addEventListener("click", closeSheet);
  $("sheet").querySelectorAll(".guess").forEach((button) => button.addEventListener("click", async () => {
    const result = await api("/api/catches", { json: { pending_id: data.pending_id, species_id: button.dataset.species } });
    openSheet.onClose = null;  // don't restart the camera underneath the celebration
    closeSheet();
    if (result.ok) showReveal(result.data);
    else { toast(result.data.error || "That catch didn't save."); resetCamera(); }
  }));
}

/* ---------- the celebration after a catch ---------- */

function showReveal(r) {
  const sp = r.species;
  const el = $("reveal");
  el.dataset.tier = sp.tier;
  const lvl = r.level;
  const percent = Math.round(100 * lvl.xp_into_level / lvl.xp_for_level);
  el.innerHTML = `
    <div class="rays"></div>
    <div class="stamp">${r.is_new_species ? "NEW SPECIES!" : "CAUGHT AGAIN"}</div>
    <div class="trophy">
      ${artHtml(sp, { photoUrl: state.lastPhotoUrl })}
      <div class="num">${dexNumber(sp.number)} · ${esc(sp.group_label)}</div>
      <h3>${esc(sp.common_name)}</h3>
      <em>${esc(sp.scientific_name)}</em>
      <span class="gem">${TIER_LABEL[sp.tier] || ""}</span>
    </div>
    <div class="xp-pop">+${r.xp} XP</div>
    <div class="rv-level">
      <small><span>${r.leveled_up ? "⬆️ Level up! " : ""}Level ${lvl.level} · ${esc(lvl.title)}</span><span>${lvl.xp_to_next} XP to go</span></small>
      <div class="bar"><i id="rv-bar"></i></div>
    </div>
    <div class="rv-extra">
      ${r.new_badges.length ? `<div class="earned-row">${r.new_badges.map((b) => `<span class="chip">${esc(b.icon)} ${esc(b.name)}</span>`).join("")}</div>` : ""}
      ${sp.venomous ? '<div class="notice warn">⚠️ <b>Venomous.</b> Admire it from a distance. Never touch, corner or pick it up.</div>' : ""}
      ${r.location_blurred ? '<div class="notice shield">🛡️ <b>Protected species.</b> To keep it safe, we only saved a rough area, not the exact spot.</div>' : ""}
      ${r.region ? `<p class="status-line">Caught in the ${esc(r.region.name)} · ${r.species_count} species in your Dex</p>` : `<p class="status-line">${r.species_count} species in your Dex</p>`}
    </div>
    <div class="row">
      <button class="btn" id="rv-dex">Open Dex</button>
      <button class="btn primary" id="rv-more">Keep exploring</button>
    </div>`;
  el.classList.remove("hidden");
  setTimeout(() => { $("rv-bar").style.width = percent + "%"; }, 1000);
  if (r.is_new_species) confetti(el);
  const done = (tab) => { el.classList.add("hidden"); el.innerHTML = ""; state.busy = false;
    $("frozen").classList.add("hidden"); $("shutter").disabled = false; state.map = null; switchTab(tab); };
  $("rv-dex").addEventListener("click", () => done("dex"));
  $("rv-more").addEventListener("click", () => done("camera"));
}

function confetti(parent) {
  const colours = ["#ffb23e", "#ff7a3d", "#35d6b4", "#5aa2ff", "#f6f1e7", "#ff5d8f"];
  for (let i = 0; i < 44; i++) {
    const piece = document.createElement("i");
    piece.className = "confetti";
    piece.style.left = Math.random() * 100 + "%";
    piece.style.background = colours[i % colours.length];
    piece.style.animationDuration = 1.8 + Math.random() * 1.8 + "s";
    piece.style.animationDelay = Math.random() * 0.6 + "s";
    parent.appendChild(piece);
  }
}

/* ---------- tab 2: the Dex ---------- */

async function loadDex() {
  const query = new URLSearchParams();
  if (state.dex.region) query.set("region", state.dex.region);
  if (state.dex.group) query.set("group", state.dex.group);
  const [dex, status] = await Promise.all([api("/api/dex?" + query), api("/api/status")]);
  if (!dex.ok) return;
  $("demo-note").classList.toggle("hidden", !status.data.demo_data);
  if (!state.map) state.map = (await api("/api/map")).data;
  renderDex(dex.data);
}

function setFilter(kind, value) {
  // Tapping the filter that is already on turns it off again.
  state.dex[kind] = state.dex[kind] === value ? null : value;
  loadDex();
}

function renderDex(data) {
  const d = state.dex;
  $("dex-ring").style.setProperty("--p", 100 * data.caught / Math.max(1, data.total));
  $("dex-ring-text").innerHTML = `${data.caught}<br>/${data.total}`;
  $("dex-sub").textContent = `${data.caught} of ${data.total} species discovered`;

  // Caption next to the map: the selected region, or all of Texas.
  const region = data.regions.find((r) => r.code === d.region);
  const shownTotal = region ? region.total : data.entries.length;
  const shownCaught = region ? region.caught : data.entries.filter((e) => e.caught).length;
  $("region-name").textContent = region ? region.name : "All of Texas";
  $("region-blurb").textContent = region ? region.blurb : "Tap a region on the map, or pick one below.";
  $("region-bar").style.width = (100 * shownCaught / Math.max(1, shownTotal)) + "%";
  $("region-count").textContent = `${shownCaught} / ${shownTotal} found here`;

  renderMap(data.regions);

  $("region-tabs").innerHTML =
    `<button class="tab${d.region ? "" : " on"}" data-region="">⭐ All Texas</button>` +
    data.regions.map((r) => `<button class="tab${r.code === d.region ? " on" : ""}" data-region="${esc(r.code)}" style="--c:${esc(r.color)}">
      <i class="sw"></i>${esc(r.name)} <small>${r.caught}/${r.total}</small></button>`).join("");
  $("region-tabs").querySelectorAll(".tab").forEach((b) => b.addEventListener("click", () => {
    if (b.dataset.region) setFilter("region", b.dataset.region); else { d.region = null; loadDex(); }
  }));
  const selected = $("region-tabs").querySelector(".tab.on");
  if (selected) selected.scrollIntoView({ block: "nearest", inline: "center" });

  $("group-tabs").innerHTML =
    `<button class="tab${d.group ? "" : " on"}" data-group="">All</button>` +
    data.groups.map((g) => `<button class="tab${g.key === d.group ? " on" : ""}" data-group="${esc(g.key)}">
      ${esc(g.icon)} ${esc(g.label)} <small>${g.caught}/${g.total}</small></button>`).join("");
  $("group-tabs").querySelectorAll(".tab").forEach((b) => b.addEventListener("click", () => {
    if (b.dataset.group) setFilter("group", b.dataset.group); else { d.group = null; loadDex(); }
  }));

  $("dex-grid").innerHTML = data.entries.length ? data.entries.map((e, i) => `
    <button class="card${e.caught ? " caught" : ""}" data-tier="${esc(e.tier)}" data-species="${esc(e.species_id)}" style="animation-delay:${Math.min(i, 18) * 22}ms">
      <span class="num">${dexNumber(e.number)}</span><i class="pip"></i>
      ${artHtml(e, { photoUrl: e.caught ? "/api/photos/" + e.photo_id : null })}
      <span class="nm">${esc(e.common_name)}</span>
    </button>`).join("")
    : '<p class="empty">No animals match these filters.<br>Try another region or group.</p>';
  $("dex-grid").querySelectorAll(".card").forEach((c) => c.addEventListener("click", () => openSpecies(c.dataset.species)));
}

function renderMap(regions) {
  const map = state.map, box = $("texas-map");
  if (!map || !map.available) {
    box.innerHTML = '<p class="map-empty">The Texas map appears once the ecoregion shapes are downloaded (python -m data_engine.fetch_ecoregions).</p>';
    return;
  }
  const colour = Object.fromEntries(regions.map((r) => [r.code, r.color]));
  const selected = state.dex.region;
  // clip-path cuts every region off at the Texas outline, because the EPA
  // shapes carry on into neighbouring states.
  box.innerHTML = `
    <svg viewBox="-8 -8 ${map.width + 16} ${map.height + 16}" class="${selected ? "" : "none"}">
      <defs><clipPath id="tx-clip"><path d="${map.outline}"/></clipPath></defs>
      <g clip-path="url(#tx-clip)">
        ${map.regions.map((r) => `<path class="rg${r.code === selected ? " on" : ""}" data-region="${esc(r.code)}" fill="${esc(colour[r.code] || "#8a8fa8")}" d="${r.path}"/>`).join("")}
      </g>
      <path class="outline" d="${map.outline}"/>
      ${map.dots.map((p) => `<circle class="dot${p.mine ? " mine" : ""}" cx="${p.x}" cy="${p.y}" r="${p.mine ? 13 : 9}"/>`).join("")}
    </svg>
    ${colour.outside_land ? `<button class="chip gulf${selected === "outside_land" ? " on" : ""}" data-region="outside_land">🌊 Gulf</button>` : ""}`;
  box.querySelectorAll("[data-region]").forEach((el) => el.addEventListener("click", () => setFilter("region", el.dataset.region)));
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
    <div class="sp-hero" data-tier="${esc(sp.tier)}">
      ${artHtml(sp, { photoUrl: caught ? "/api/photos/" + sp.catches[0].catch_id : null })}
      <div>
        <div class="num">${dexNumber(sp.number)}</div>
        <h3>${esc(sp.common_name)}</h3>
        <em>${esc(sp.scientific_name)}</em>
        <div class="tags">
          <span class="tag">${esc(sp.group_label)}</span><span class="tag">${esc(sp.family)}</span>
          ${sp.venomous ? '<span class="tag warn">⚠️ Venomous</span>' : ""}
          ${sp.protected ? '<span class="tag shield">🛡️ Protected</span>' : ""}
        </div>
      </div>
    </div>
    ${sp.venomous ? '<div class="notice warn">⚠️ Keep your distance. Never touch, corner or pick up this animal.</div>' : ""}
    ${sp.protected ? '<div class="notice shield">🛡️ Protected in Texas. Its catch locations are blurred to a rough area.</div>' : ""}
    <div class="notice" style="background:var(--card)">${caught
      ? `📸 Caught <b>${sp.catches.length}</b> time${sp.catches.length > 1 ? "s" : ""}. First on ${shortDate(sp.catches[sp.catches.length - 1].caught_at)}.`
      : "👀 Not caught yet. Check the regions and seasons below to know where to look."}</div>
    <p class="sec">Where and when it lives</p>
    ${where || '<p class="muted">No region records yet.</p>'}
    <div class="legend">${Object.keys(TIER_LABEL).map((t) => `<span class="gem" data-tier="${t}">${TIER_LABEL[t]}</span>`).join("")}</div>
    <button class="btn big" style="margin-top:18px" id="sp-close">Close</button>`);
  $("sp-close").addEventListener("click", closeSheet);
}

/* ---------- tab 3: profile ---------- */

async function loadProfile() {
  const [profile, status] = await Promise.all([api("/api/profile"), api("/api/status")]);
  if (profile.ok) renderProfile(profile.data, status.data);
}

function renderProfile(p, status) {
  const lvl = p.level, s = p.stats;
  const percent = Math.round(100 * lvl.xp_into_level / lvl.xp_for_level);
  $("profile-body").innerHTML = `
    <div class="hero-card">
      <button class="chip edit-btn" id="edit-profile">✏️ Edit</button>
      <div class="avatar-ring" style="--p:${percent}"><span>${esc(p.user.avatar)}</span><b class="lvl">Level ${lvl.level}</b></div>
      <h2>${esc(p.user.display_name)}</h2>
      <div class="title">${esc(lvl.title)}</div>
      <div class="handle">@${esc(p.user.username)} · exploring since ${shortDate(p.user.created_at)}</div>
      <div class="xp"><div class="bar"><i style="width:${percent}%"></i></div>
        <small><span>${lvl.xp} XP</span><span>${lvl.xp_to_next} XP to Level ${lvl.level + 1}</span></small></div>
    </div>
    <div class="stats">
      <div class="stat"><b>${s.species}<small> / ${s.species_total}</small></b><span>Species discovered</span></div>
      <div class="stat"><b>${s.catches}</b><span>Total catches</span></div>
      <div class="stat"><b>${s.regions}<small> / ${s.regions_total}</small></b><span>Regions explored</span></div>
      <div class="stat" ${s.rarest ? `data-tier="${esc(s.rarest.tier)}"` : ""}><b style="font-size:17px;line-height:1.25">${s.rarest ? esc(s.rarest.common_name) : "Nothing yet"}</b>
        <span>${s.rarest ? `<span class="gem">${TIER_LABEL[s.rarest.tier]}</span> rarest find` : "Rarest find"}</span></div>
    </div>
    <p class="sec">Dex progress</p>
    ${p.groups.map((g) => `<div class="gp"><span style="font-size:20px">${esc(g.icon)}</span>
      <div>${esc(g.label)}<div class="bar"><i style="width:${100 * g.caught / Math.max(1, g.total)}%"></i></div></div>
      <span class="muted">${g.caught}/${g.total}</span></div>`).join("")}
    <p class="sec">Badges · ${p.badges.filter((b) => b.earned).length} of ${p.badges.length}</p>
    <div class="badges">${p.badges.map((b) => `<button class="badge${b.earned ? " earned" : ""}" data-hint="${esc(b.name + ": " + b.hint)}">
      <i>${esc(b.icon)}</i><span>${esc(b.name)}</span></button>`).join("")}</div>
    <p class="sec">Recent catches</p>
    ${p.recent.length ? `<div class="recent">${p.recent.map((c) => `<div class="rc" data-tier="${esc(c.tier)}">
      <div class="art"><img src="/api/photos/${c.catch_id}" alt="" loading="lazy"></div>
      <strong>${esc(c.common_name)}</strong><small>${shortDate(c.caught_at)} · +${c.xp} XP</small></div>`).join("")}</div>`
      : '<p class="muted" style="font-size:14px">No catches yet. Head to the Catch tab and photograph your first animal.</p>'}
    <div class="foot">
      <p class="status-line">${status.fake_id ? "ID engine: demo mode (guesses are random). Start with --bioclip for real identification." : "ID engine: BioCLIP 2 with the local-species boost."}
        ${status.demo_data ? "<br>Species data: demo set (illustrative regions and rarity)." : ""}</p>
      <button class="btn danger" id="logout">Log out</button>
    </div>`;
  $("profile-body").querySelectorAll(".badge").forEach((b) => b.addEventListener("click", () => toast(b.dataset.hint)));
  $("logout").addEventListener("click", async () => { await api("/api/logout", { method: "POST" }); showAuth(); });
  $("edit-profile").addEventListener("click", () => editProfile(p));
}

function editProfile(p) {
  let avatar = p.user.avatar;
  openSheet(`
    <h3 class="sheet-title">Edit profile</h3>
    <p class="sheet-sub">Pick the name and badge other rangers will see.</p>
    <label>Ranger name<input id="edit-name" maxlength="30" value="${esc(p.user.display_name)}"></label>
    <p class="sec">Avatar</p>
    <div class="avatars">${p.avatars.map((a) => `<button class="${a === avatar ? "on" : ""}" data-avatar="${esc(a)}">${esc(a)}</button>`).join("")}</div>
    <button class="btn primary big" id="edit-save">Save</button>`);
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
  state.status = status;
  if (status.logged_in) enterApp(); else showAuth();
})();
