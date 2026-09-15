let pyGame = null;

function showError(err) {
    const box = document.getElementById("error-box");
    box.style.display = "block";
    box.textContent = "Fehler:\n" + err;
    document.getElementById("loading").style.display = "none";
}

function getDepth() {
    // Returns null if the field isn't in the DOM at all (only the
    // Location view has a #depth field) - callers must NOT send that
    // as "0" to handle_action, or depth would silently get reset
    // every time an action fires from a different view.
    const el = document.getElementById("depth");
    if (!el) return null;
    if (el.value === "") return 0;
    const n = parseInt(el.value, 10);
    return Number.isNaN(n) ? 0 : n;
}

function getDepthArg() {
    const d = getDepth();
    return d === null ? null : String(d);
}

function getLevel() {
    const el = document.getElementById("level");
    if (!el || el.value === "") return null;
    return el.value;
}

function getCheckbox(id) {
    // Same idea as getDepth(): null if the checkbox isn't currently
    // in the DOM (only the Location view has these), so other views'
    // actions never accidentally reset the stored preference.
    const el = document.getElementById(id);
    return el ? el.checked : null;
}

function getIntFieldArg(id) {
    // The Encounter DC / Treasure DC fields now live per-view
    // (Location/Encounter/Treasure - not shown at all in Crawling
    // Mode), so unlike getDepth()'s single view this covers three -
    // same null-safety either way: null means "don't touch it".
    const el = document.getElementById(id);
    if (!el || el.value === "") return null;
    const n = parseInt(el.value, 10);
    return Number.isNaN(n) ? null : String(n);
}

function getSelectField(id) {
    // Same idea as getDepth()/getCheckbox(): null if the dropdown
    // isn't currently in the DOM (only the Location view has the
    // Location/Detail pickers), so other views' actions never
    // accidentally reset the stored choice. "" (present but set to
    // "Random") is returned as-is, distinct from null.
    const el = document.getElementById(id);
    return el ? el.value : null;
}

function renderApp() {
    const html = pyGame.render_page();
    document.getElementById("app").innerHTML = html;
}

async function dispatch(action, view, roomId, entryId, lightSource = null) {
    try {
        pyGame.handle_action(
            action,
            getDepthArg(),
            getLevel(),
            view,
            getCheckbox("roll-treasure"),
            getCheckbox("roll-encounter"),
            getCheckbox("encounter-roll-treasure"),
            getIntFieldArg("encounter-dc"),
            getIntFieldArg("treasure-dc"),
            getSelectField("location-select"),
            getSelectField("detail-select"),
            getSelectField("monster-select"),
            getSelectField("quality-select"),
            roomId == null ? null : String(roomId),
            entryId == null ? null : String(entryId),
            getCheckbox("smash-amphoras"),
            getIntFieldArg("default-encounter-dc"),
            getIntFieldArg("default-treasure-dc"),
            getCheckbox("show-roll-details"),
            getCheckbox("show-treasure-quality"),
            getIntFieldArg("round-length-minutes"),
            getCheckbox("track-torch"),
            getCheckbox("track-lantern"),
            getIntFieldArg("torch-burn-minutes"),
            getIntFieldArg("lantern-burn-minutes"),
            lightSource == null ? null : String(lightSource)
        );
        renderApp();
    } catch (err) {
        showError(err);
    }
}

async function runAction(action) {
    return dispatch(action, null, null);
}

async function onLevelChange() {
    return dispatch(null, null, null);
}

async function onSettingsChange() {
    // Same idea as onLevelChange(): a settings checkbox has no
    // "generate/roll" button of its own to piggyback a re-render on,
    // so it triggers one directly - the point of a display toggle
    // like "Show Roll Details" is to see its effect immediately, not
    // wait for some unrelated next action.
    return dispatch(null, null, null);
}

async function switchView(view) {
    return dispatch("switch_view", view, null);
}

async function enterRoom(roomId) {
    return dispatch("enter_room", null, roomId);
}

async function viewRoom(roomId) {
    return dispatch("view_room", null, roomId);
}

async function toggleConnection(roomId) {
    return dispatch("toggle_connection", null, roomId);
}

async function ransackRoom(roomId) {
    return dispatch("ransack_room", null, roomId);
}

async function openSafe(roomId) {
    return dispatch("open_safe", null, roomId);
}

async function refuelLight(source) {
    // "Light Torch" / "Refuel Lantern" - unlike removeMonsterGroup/
    // removeTreasureItem (which reuse the roomId/entryId slots for
    // their own unrelated ids), this has its own dedicated
    // lightSource param instead, since a light source isn't a room
    // or an entry at all - roomId/entryId stay null here.
    return dispatch("refuel_light", null, null, null, source);
}

async function removeMonsterGroup(roomId, groupId) {
    return dispatch("remove_monster_group", null, roomId, groupId);
}

async function removeTreasureItem(roomId, itemId) {
    return dispatch("remove_treasure_item", null, roomId, itemId);
}

async function useFireplace() {
    const el = document.getElementById("fireplace-select");
    const roomId = el ? el.value : null;
    return dispatch("use_fireplace", null, roomId || null);
}

function toggleSidebar() {
    // The toggle button now lives in the static page header (outside
    // #app), so it's clickable even before Pyodide has finished
    // loading and rendered the sidebar itself - guard against that.
    const sidebar = document.getElementById("sidebar");
    const backdrop = document.getElementById("sidebar-backdrop");
    if (!sidebar || !backdrop) return;
    sidebar.classList.toggle("open");
    backdrop.classList.toggle("visible");
}

function closeSidebar() {
    const sidebar = document.getElementById("sidebar");
    const backdrop = document.getElementById("sidebar-backdrop");
    if (!sidebar) return;
    sidebar.classList.remove("open");
    if (backdrop) backdrop.classList.remove("visible");
}

/**
 * Loads one of our Python source files.
 *
 * Two ways this can be satisfied, so the exact same app.js works both
 * during development and in the bundled single-file build:
 *
 *   1. Bundled build (dist/depthcrawl_pyodide.html): build.py has
 *      inlined the file's content into a "text/python" script
 *      element with a matching id, right in the page. We just read
 *      its textContent - no network request, works fine from a
 *      plain file:// URL.
 *
 *   2. Dev mode (src/index.html served via a local static server):
 *      that inline element doesn't exist, so we fall back to
 *      fetching the .py file directly. This requires the page to be
 *      served over http(s):// (browsers block fetch() of local files
 *      from a file:// page), e.g. via `python3 -m http.server` in
 *      `src/`.
 */
async function loadPythonSource(inlineId, filename) {
    const inlineEl = document.getElementById(inlineId);
    if (inlineEl && inlineEl.textContent.trim().length > 0) {
        return inlineEl.textContent;
    }

    const response = await fetch(filename);
    if (!response.ok) {
        throw new Error(
            `Could not load ${filename} (HTTP ${response.status}). ` +
            "If you opened this file directly (file://), serve the " +
            "'src' folder via a local static server instead, e.g.:\n" +
            "  python3 -m http.server\n" +
            "...or run build.py to create a self-contained dist file."
        );
    }
    return await response.text();
}

async function main() {
    try {
        const pyodide = await loadPyodide();

        // Pure-Python "markdown" package for rendering the location /
        // detail descriptions (same library the Flask version used).
        await pyodide.loadPackage("micropip");
        const micropip = pyodide.pyimport("micropip");
        await micropip.install("markdown");

        const dataSource = await loadPythonSource("py-data", "data.py");
        const gameSource = await loadPythonSource("py-game", "game.py");

        pyodide.FS.writeFile("/data.py", dataSource);
        pyodide.FS.writeFile("/game.py", gameSource);

        pyodide.runPython("import sys; sys.path.insert(0, '/')");

        pyGame = pyodide.pyimport("game");

        renderApp();
        document.getElementById("loading").style.display = "none";
        document.getElementById("app").style.display = "block";
    } catch (err) {
        showError(err);
    }
}

main();
