// timtapper: start the Python worker with the page, not once Flutter has started (scripts/build_web.py puts this into
// flet's python.js), so Pyodide loads and the app's archive unpacks while Flutter does; jsConnect below takes this
// worker over. The snapshot key names this build's Python archive: a snapshot of Python made from another one is
// never restored (scripts/prestart/worker.js).
let _prestarted = new Worker("python-worker.js", { type: "module" });
_prestarted.postMessage({
    prestart: true,
    pyodideUrl: flet.pyodideUrl || "pyodide/pyodide.mjs",
    appPackageUrl: flet.appPackageUrl,
    pythonModuleName: flet.pythonModuleName || "main",
    snapshotKey: "__SNAPSHOT_KEY__"
});
