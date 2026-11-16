/* TexDex front end. Plain JavaScript, no framework: each tab has a "load"
   function that asks the server for JSON and a "render" function that turns
   it into HTML. All game rules live on the server; this file only draws. */
"use strict";

const $ = (id) => document.getElementById(id);
const TABS = ["camera", "dex", "map", "profile"];
const TIER_LABEL = { common: "Common", uncommon: "Uncommon", rare: "Rare", very_rare: "Very Rare" };
const TIER_SHORT = { common: "C", uncommon: "U", rare: "R", very_rare: "VR" };
const SEASONS = [["spring", "Sp", "Spring"], ["summer", "Su", "Summer"], ["fall", "Fa", "Fall"], ["winter", "Wi", "Winter"]];

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

// The sheet is a dialog, so keyboard and screen-reader users need the same
// things a tap user gets for free: focus moves into it, Tab stays inside it,
// Escape closes it, and focus goes back to whatever opened it.
const FOCUSABLE = 'button:not([disabled]), input, [href], [tabindex]:not([tabindex="-1"])';

function openSheet(html, { onClose = null } = {}) {
  const sheet = $("sheet");
  if (sheet.classList.contains("hidden")) openSheet.opener = document.activeElement;
  sheet.innerHTML = html;
  sheet.scrollTop = 0;
  sheet.classList.remove("hidden");
  $("sheet-backdrop").classList.remove("hidden");
  openSheet.onClose = onClose;
  // Name the dialog after its first heading.
  const title = sheet.querySelector("h3");
  if (title) { title.id = "sheet-title"; sheet.setAttribute("aria-labelledby", "sheet-title"); }
  else sheet.removeAttribute("aria-labelledby");
  sheet.focus({ preventScroll: true });
}
function closeSheet() {
  $("sheet").classList.add("hidden");
  $("sheet-backdrop").classList.add("hidden");
  const callback = openSheet.onClose;
  openSheet.onClose = null;
  if (callback) callback();
  // Return focus to the opener, if it is still on screen.
  const opener = openSheet.opener;
  openSheet.opener = null;
  if (opener && opener.isConnected && opener.offsetParent !== null) opener.focus({ preventScroll: true });
}
$("sheet-backdrop").addEventListener("click", closeSheet);
$("sheet").addEventListener("keydown", (event) => {
  if (event.key === "Escape") { event.preventDefault(); closeSheet(); return; }
  if (event.key !== "Tab") return;
  const items = [...$("sheet").querySelectorAll(FOCUSABLE)].filter((el) => el.offsetParent !== null);
  if (!items.length) { event.preventDefault(); return; }
  const first = items[0], last = items[items.length - 1];
  if (event.shiftKey && (document.activeElement === first || document.activeElement === $("sheet"))) {
    event.preventDefault(); last.focus();
  } else if (!event.shiftKey && document.activeElement === last) {
    event.preventDefault(); first.focus();
  }
});

/* ---------- sign up / log in ---------- */

function showAuth() {
  stopCamera();
  $("auth").classList.remove("hidden");
  $("screens").classList.add("hidden");
  $("tabbar").classList.add("hidden");
}

// Errors go under the field they are about, so the user knows what to fix.
// Each one names the problem and the rule, never just "invalid".
function clearAuthErrors() {
  for (const field of ["username", "password"]) {
    $("err-" + field).textContent = "";
    $("f-" + field).removeAttribute("aria-invalid");
  }
  $("auth-error").textContent = "";
}
function fieldError(field, message) {
  $("err-" + field).textContent = message;
  $("f-" + field).setAttribute("aria-invalid", "true");
}

document.querySelectorAll(".seg button").forEach((button) => button.addEventListener("click", () => {
  state.authMode = button.dataset.mode;
  const signup = state.authMode === "signup";
  document.querySelectorAll(".seg button").forEach((b) => {
    b.classList.toggle("on", b === button);
    b.setAttribute("aria-pressed", String(b === button));
  });
  $("display-row").classList.toggle("hidden", !signup);
  // Returning users don't need the sign-up rules in their way.
  $("hint-username").classList.toggle("hidden", !signup);
  $("hint-password").classList.toggle("hidden", !signup);
  $("auth-submit").textContent = signup ? "Start my journal" : "Open my journal";
  clearAuthErrors();
}));

$("auth-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  clearAuthErrors();
  const username = $("f-username").value.trim(), password = $("f-password").value;
  // Catch empty fields here; the server still checks every rule.
  if (!username) fieldError("username", "Add a username.");
  if (!password) fieldError("password", "Add a password.");
  if (!username || !password) return;

  let result;
  try {
    result = await api("/api/" + state.authMode, { json: {
      username, password, display_name: $("f-display").value } });
  } catch (e) {
    $("auth-error").textContent = "We couldn't reach TexDex. Check your signal and try again.";
    return;
  }
  if (!result.ok) {
    const message = result.data.error || "That didn't work. Please try again.";
    // The server's messages start with the field they are about.
    if (/^(usernames|that username is taken)/i.test(message)) fieldError("username", message);
    else if (/^passwords/i.test(message)) fieldError("password", message);
    else $("auth-error").textContent = message;
    return;
  }
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

// Below this match score we don't pre-pick the top guess and we suggest a
// retake. The real model already refuses photos it is very unsure about (on
// the server); this catches the "it might be right" middle ground.
const LOW_MATCH = 0.5;

const TICK_SVG = '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M5 12.5 10 17 19 7"/></svg>';

// Safety marks shown on a guess *before* the user saves it, because the
// moment that matters is when they are still standing near the animal.
function flagsHtml(sp) {
  return (sp.venomous ? '<span class="flag warn">Venomous</span>' : "")
    + (sp.protected ? '<span class="flag shield">Protected</span>' : "");
}

function guessHtml(guess, top) {
  const percent = Math.round(guess.confidence * 100);
  return `<button type="button" class="guess${top ? " top" : ""}" data-species="${esc(guess.species_id)}" aria-pressed="false">
    ${artHtml(guess)}
    <div class="guess-text">
      <strong>${esc(guess.common_name)}</strong>
      <em>${esc(guess.scientific_name)}</em>
      <div class="match">${tierHtml(guess.tier)}<span>${percent}% match</span>${flagsHtml(guess)}</div>
    </div>
    <span class="pick">${TICK_SVG}</span></button>`;
}

// The guess sheet works in two steps: tap a row to choose it, then press Save.
// Saving is permanent (XP, stamps, the Dex), so a stray tap with one hand
// should only ever *select*, never save.
function showGuesses(data) {
  const [top, ...others] = data.guesses;
  const unsure = top.confidence < LOW_MATCH;
  const where = data.region ? ` in the ${esc(data.region.name)}` : "";
  const photo = state.lastPhotoUrl
    ? `<div class="sheet-photo"><div class="art photo"><img src="${esc(state.lastPhotoUrl)}" alt="Your photo"></div></div>` : "";
  openSheet(`
    <div class="sheet-head">
      <div>
        <h3 class="sheet-title">Is this what you saw?</h3>
        <p class="sheet-sub">${unsure ? "We're not sure about this one" : "The closest match"}${where}. Pick the animal in your photo, then save it.</p>
      </div>
      ${photo}
    </div>
    ${unsure ? '<p class="note tip">None of these is a strong match. A closer or clearer photo usually helps.</p>' : ""}
    ${guessHtml(top, true)}
    ${others.length ? '<p class="sec">Or possibly</p>' + others.map((g) => guessHtml(g, false)).join("") : ""}
    <div id="pick-note"></div>
    <p class="form-error" id="save-error" role="alert"></p>
    <div class="row sheet-actions">
      <button type="button" class="btn" id="none-btn">Retake</button>
      <button type="button" class="btn primary" id="save-btn" disabled>Save to my Dex</button>
    </div>`, { onClose: resetCamera });

  const rows = [...$("sheet").querySelectorAll(".guess")];
  const saveButton = $("save-btn");
  let chosen = null, saving = false;

  function choose(speciesId) {
    chosen = data.guesses.find((g) => g.species_id === speciesId) || null;
    rows.forEach((row) => {
      const on = row.dataset.species === speciesId;
      row.classList.toggle("sel", on);
      row.setAttribute("aria-pressed", String(on));
    });
    saveButton.disabled = !chosen;
    $("save-error").textContent = "";
    // Repeat the safety note next to the Save button for the chosen animal.
    $("pick-note").innerHTML = !chosen ? ""
      : chosen.venomous ? '<p class="note warn">Venomous. Keep your distance; never touch, corner or pick it up.</p>'
      : chosen.protected ? '<p class="note shield">Protected species. Its exact spot will not be saved.</p>' : "";
  }

  rows.forEach((row) => row.addEventListener("click", () => { if (!saving) choose(row.dataset.species); }));
  if (!unsure) choose(top.species_id);
  $("none-btn").addEventListener("click", () => { if (!saving) closeSheet(); });

  saveButton.addEventListener("click", async () => {
    if (!chosen || saving) return;  // guard against a double tap
    saving = true;
    saveButton.disabled = true;
    saveButton.textContent = "Saving…";
    let result;
    try {
      result = await api("/api/catches", { json: { pending_id: data.pending_id, species_id: chosen.species_id } });
    } catch (e) {
      result = { ok: false, data: { error: "We couldn't reach TexDex. Check your signal and try again." } };
    }
    if (result.ok) {
      openSheet.onClose = null;  // don't restart the camera underneath the new entry
      closeSheet();
      showReveal(result.data);
      return;
    }
    // Keep the sheet and the choice so the user can just press Save again.
    saving = false;
    saveButton.disabled = false;
    // The error says what to do next (try again, or retake if the photo expired).
    saveButton.textContent = "Save to my Dex";
    $("save-error").textContent = result.data.error || "That entry didn't save. Please try again.";
  });
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
    ${!sp.protected ? ""
      : r.location_blurred ? '<p class="note shield">Protected species. To keep it safe, only a rough area was saved, not the exact spot.</p>'
      : '<p class="note shield">Protected species. No location was saved with this entry, so it won\'t appear on the map.</p>'}
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
  // The tally above already covers the whole Dex, so this line only adds a
  // count when a filter narrows the list.
  const filtered = Boolean(d.region || d.group);
  const count = `You've found ${found} of the ${data.entries.length} shown here.`;
  $("region-blurb").textContent = region ? `${region.blurb}. ${count}`
    : filtered ? count : "Tap any animal to see where and when it lives.";

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
    : '<p class="empty">No animals match this region and group. Try All animals, or another region.</p>';
  $("dex-grid").querySelectorAll(".card").forEach((c) => c.addEventListener("click", () => openSpecies(c.dataset.species)));
}

async function openSpecies(speciesId) {
  const result = await api("/api/species/" + encodeURIComponent(speciesId));
  if (!result.ok) return;
  const sp = result.data, caught = sp.catches.length > 0;
  // Each season cell shows the tier as letters (C, U, R, VR) as well as its
  // ink colour, so it reads without colour vision and without a hover
  // tooltip (phones have no hover). A dash means no records that season.
  const cell = ([key, , name]) => (tier) => tier
    ? `<i data-tier="${esc(tier)}" role="img" aria-label="${name}: ${TIER_LABEL[tier]}">${TIER_SHORT[tier]}</i>`
    : `<i role="img" aria-label="${name}: no records">–</i>`;
  const where = sp.regions.map((r) => `
    <div class="where" style="--c:${esc(r.color)}"><i class="sw"></i><span>${esc(r.name)}</span>
      <div class="seasons">${SEASONS.map((s) => cell(s)(r.seasons[s[0]])).join("")}</div>
    </div>`).join("");
  const seasonHead = `<div class="where where-head" aria-hidden="true"><i class="sw"></i><span></span>
    <div class="seasons">${SEASONS.map(([, short]) => `<i>${short}</i>`).join("")}</div></div>`;
  const seasonKey = `<p class="season-key">${Object.keys(TIER_LABEL).map((t) =>
    `<span><i data-tier="${t}" aria-hidden="true">${TIER_SHORT[t]}</i>${TIER_LABEL[t]}</span>`).join("")}
    <span><i aria-hidden="true">–</i>No records</span></p>`;
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
    ${where ? seasonKey + seasonHead + where : '<p class="muted">No region records yet.</p>'}
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
    // Setup steps for developers live in the README, not on screen.
    box.innerHTML = '<p class="map-empty">The map isn\'t ready yet. Your photos are still saved and will appear here once it is.</p>';
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
    <svg viewBox="${(m.view || view).join(" ")}" class="tx${m.region ? " zoomed" : ""}" aria-hidden="true" focusable="false">
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
    <svg class="compass" viewBox="0 0 40 40" aria-hidden="true"><circle cx="20" cy="22" r="13" fill="none" stroke="#2b2620"/><path d="M20 9l4 13h-8z" fill="#2b2620"/><path d="M20 35l-4-13h8z" fill="none" stroke="#2b2620"/><text x="20" y="7" font-size="8" text-anchor="middle" font-family="monospace">N</text></svg>
    ${colour.outside_land ? `<button class="gulf-btn${m.region === "outside_land" ? " on" : ""}" data-region="outside_land">Gulf waters</button>` : ""}`;
  // The drawing is hidden from screen readers and skipped by Tab: the region
  // strip above and the photo list below are the same choices as real buttons.
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
      <tr><td>Regions explored${s.catches && !s.regions ? '<br><small>Only photos with a location count</small>' : ""}</td><td>${s.regions} <small>of ${s.regions_total}</small></td></tr>
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
      <p class="foot-note">${status.fake_id ? "Demo mode: the guesses are random, not a real identification." : "Identification: BioCLIP 2, boosted by what lives in your region this month."}
        ${status.demo_data ? " Regions and rarity are illustrative until the real sighting data is in." : ""}</p>
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

// Without this check a failed first request would leave every screen hidden:
// a blank page with nothing to tap.
async function boot() {
  $("boot-error").classList.add("hidden");
  let result;
  try { result = await api("/api/status"); } catch (e) { result = null; }
  if (!result || !result.ok) {
    $("boot-error").classList.remove("hidden");
    $("boot-retry").focus();
    return;
  }
  if (result.data.logged_in) enterApp(); else showAuth();
}
$("boot-retry").addEventListener("click", boot);
boot();
