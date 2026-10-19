self.pyodideUrl = null;
self.appPackageUrl = null;
self.micropipIncludePre = false;
self.pythonModuleName = null;
self.documentUrl = null;
self.initialized = false;
self.flet_js = {}; // namespace for Python global functions

// Flipped to true right before `runpy.run_module` runs the user app.
// Until then, stdout/stderr is bootstrap diagnostics ("Downloading app
// archive", micropip install logs, etc.) — those go to the dev console
// rather than the user-visible Console pane.
self.userAppRunning = false;
self.flet_js.userAppStarting = function () {
    self.userAppRunning = true;
};
self.sendPythonOutput = function (text, isStderr) {
    // No bridge yet, or not in user-code mode — surface in dev console.
    // The boot script registers `flet_js.send_python_output` after the
    // user-app deps are installed (msgpack typically rides in via flet);
    // if msgpack isn't available it stays unset and prints fall through
    // to the dev console silently.
    if (!self.userAppRunning || !(self.flet_js && self.flet_js.send_python_output)) {
        if (isStderr) {
            console.error(text);
        } else {
            console.log(text);
        }
        return;
    }
    // Pyodide invokes stdout/stderr hooks with the GIL released, so
    // calling back into Python synchronously throws NoGilError. Defer
    // to a microtask — by the time it runs, the GIL state is normal.
    queueMicrotask(function () {
        self.flet_js.send_python_output(text, isStderr);
    });
};

// timtapper (scripts/build_web.py puts this into flet's python-worker.js): load Pyodide and unpack the app's archive
// as soon as the page starts the worker, and start Python from a snapshot of it when there is one.
//
// Starting Python and importing the app takes about 3 s of CPU on every visit. So after a start without a snapshot,
// the worker imports the app's module, keeps a snapshot of Python's memory in Cache Storage, and boots on as usual;
// the next visit restores that in a tenth of a second, the app's libraries already imported. Only the files are not
// in it (Pyodide keeps those outside the memory), so the archive is still unpacked. A snapshot is kept for one build
// (its key, from the page) and one Pyodide (which checks its own build id); anything going wrong with one drops it,
// and Python starts afresh.
const SNAPSHOTS = "timtapper-python";
const MODULE_NAME = /^[A-Za-z_][A-Za-z0-9_.]*$/;

self.restored = false;
self.forSnapshot = false; // loaded to be snapshotted: without flet's output functions until it is

// flet's options for loadPyodide (its stdout and stderr), and Pyodide loaded with `options` over them
self.fletOptions = () => ({
            stdout: (text) => self.sendPythonOutput(text, false),
            stderr: (text) => self.sendPythonOutput(text, true),
        });
self.loadPyodideWith = async function (options) {
    const pyodideModule = await import(self.pyodideUrl);
        const loadPyodide = pyodideModule.loadPyodide || self.loadPyodide;
    return await loadPyodide({ ...self.fletOptions(), ...options });
};

// A snapshot can't hold the JS functions Python's output goes to: Python made for one starts without them, and gets
// flet's once the snapshot is taken (or isn't)
self.attachOutput = function (pyodide) {
    const { stdout, stderr } = self.fletOptions();
    if (stdout) pyodide.setStdout({ batched: stdout });
    if (stderr) pyodide.setStderr({ batched: stderr });
};

// Pyodide restores a snapshot into the module's default-sized memory, too small for the app's: grow it first
self.grownModule = async function (bytes) {
    const runtime = new URL("pyodide.asm.mjs", new URL(self.pyodideUrl, self.location)).href;
    const create = (await import(runtime)).default;
    return async (settings) => {
        const module = await create(settings);
        while (module.HEAP8.length < bytes) {
            if (!module._malloc(4 << 20)) {
                throw new Error("couldn't grow Python's memory to fit its snapshot");
            }
        }
        return module;
    };
};

self.snapshotRequest = () => new Request(`python-snapshot?key=${encodeURIComponent(self.snapshotKey)}`);

self.savedSnapshot = async function () {
    if (!self.snapshotKey || !("caches" in self)) return null;
    try {
        const saved = await (await caches.open(SNAPSHOTS)).match(self.snapshotRequest());
        return saved ? new Uint8Array(await saved.arrayBuffer()) : null;
    } catch (error) {
        console.error("timtapper: couldn't read Python's snapshot, starting it afresh:", error);
        return null;
    }
};

self.dropSnapshots = async function () {
    try {
        await caches.delete(SNAPSHOTS);
    } catch (error) {
        console.error("timtapper: couldn't drop Python's snapshot:", error);
    }
};

// import the app's module (not run: the boot script runs it), then keep a snapshot of Python as it is now
self.saveSnapshot = async function (pyodide) {
    if (!self.snapshotKey || !("caches" in self) || !MODULE_NAME.test(self.pythonModuleName)) return;
    let snapshot;
    try {
        await pyodide.runPythonAsync(
            `import sys\nsys.path.insert(0, "__pypackages__")\nimport ${self.pythonModuleName}`
        );
        snapshot = pyodide.makeMemorySnapshot();
    } catch (error) {
        console.error("timtapper: couldn't make Python's snapshot:", error);
        return;
    }
    // stored meanwhile: the boot goes on
    (async () => {
        try {
            const cache = await caches.open(SNAPSHOTS);
            for (const old of await cache.keys()) await cache.delete(old);
            await cache.put(self.snapshotRequest(), new Response(snapshot));
            console.log(`timtapper: saved Python's snapshot (${(snapshot.length / 1e6).toFixed(1)} MB)`);
        } catch (error) {
            console.error("timtapper: couldn't save Python's snapshot:", error);
        }
    })();
};

self.startPyodide = function () {
    self.pyodideReady ??= (async () => {
        const snapshot = await self.savedSnapshot();
        if (snapshot) {
            try {
                const createPyodideModule = await self.grownModule(snapshot.length);
                const pyodide = await self.loadPyodideWith({ _loadSnapshot: snapshot, createPyodideModule });
                self.restored = true;
                console.log("timtapper: Python restored from its snapshot");
                return pyodide;
            } catch (error) {
                console.error("timtapper: Python's snapshot didn't restore, starting it afresh:", error);
                await self.dropSnapshots();
            }
        }
        if (!self.snapshotKey) return await self.loadPyodideWith({});
        self.forSnapshot = true;
        return await self.loadPyodideWith({ _makeSnapshot: true, stdout: undefined, stderr: undefined });
    })();
    return self.pyodideReady;
};

// resolves to the archive's URL once it's unpacked, or to null if that failed: the boot script then fetches it itself
self.prestart = function () {
    const url = self.appPackageUrl;
    self.appUnpacked = (async () => {
        let pyodide;
        try {
            let response;
            [pyodide, response] = await Promise.all([self.startPyodide(), fetch(url)]);
            if (!response.ok) {
                throw new Error(`HTTP ${response.status} ${url}`);
            }
            pyodide.unpackArchive(await response.arrayBuffer(), "zip");
        } catch (error) {
            console.error("timtapper: couldn't unpack the app ahead, fetching it again:", error);
            if (pyodide && self.forSnapshot) self.attachOutput(pyodide);
            return null;
        }
        if (self.forSnapshot) {
            await self.saveSnapshot(pyodide);
            self.attachOutput(pyodide);
        }
        return url;
    })();
};

self.initPyodide = async function () {
    try {
        // Module-worker load path. `importScripts` only exists in classic
        // workers — Pyodide >= 0.29 actively refuses to load there ("Classic
        // web workers are not supported"). We're a module worker, so the
        // runtime ships as `pyodide.mjs` and exposes `loadPyodide` via ESM
        // exports. The CDN/jsdelivr fallback URL set by patch_index.py also
        // points at the .mjs variant.
        self.pyodide = await self.startPyodide();
        if (self.appUnpacked) flet_js.appUnpackedFrom = await self.appUnpacked;
        self.pyodide.registerJsModule("flet_js", flet_js);
        self.pyodide.globals.set("app_package_url", self.appPackageUrl);
        self.pyodide.globals.set("python_module_name", self.pythonModuleName);
        self.pyodide.globals.set("micropip_include_pre", self.micropipIncludePre);
        flet_js.documentUrl = documentUrl;
        await self.pyodide.runPythonAsync(`
        import flet_js, os, runpy, sys, traceback
        from pyodide.http import pyfetch

        py_args = flet_js.args.to_py() if flet_js.args else None

        if "app_package_url" in py_args:
            app_package_url = py_args["app_package_url"]

        if "python_module_name" in py_args:
            python_module_name = py_args["python_module_name"]

        if python_module_name is None:
            python_module_name = "main"

        if "micropip_include_pre" in py_args:
            micropip_include_pre = py_args["micropip_include_pre"]

        if micropip_include_pre is None:
            micropip_include_pre = False

        print("python_module_name:", python_module_name)
        print("micropip_include_pre:", micropip_include_pre)

        if "script" not in py_args and getattr(flet_js, "appUnpackedFrom", None) == app_package_url:
            print("App archive unpacked ahead")
        elif "script" not in py_args:
            print("Downloading app archive")
            response = await pyfetch(app_package_url)
            # Fail with a readable error on a non-2xx response.
            # Without this check the error body (JSON/HTML from the
            # server) lands in unpack_archive and surfaces as a
            # cryptic "... is not a zip file" ReadError.
            if not response.ok:
                _err_body = ""
                try:
                    _err_body = (await response.text())[:200].strip()
                except Exception:
                    pass
                raise RuntimeError(
                    f"Failed to download app package: "
                    f"HTTP {response.status} {app_package_url}"
                    + (f" — {_err_body}" if _err_body else "")
                )
            # Pick format from the URL's path extension. Pyodide's
            # filename-based sniff trips over query strings like
            # ?v=42. We only support zip and tar.gz (matching what
            # our server and "flet publish" emit).
            from urllib.parse import urlparse
            _archive_path = urlparse(app_package_url).path.lower()
            if _archive_path.endswith(".zip"):
                _archive_format = "zip"
            elif _archive_path.endswith((".tar.gz", ".tgz")):
                _archive_format = "gztar"
            else:
                raise ValueError(
                    f"Unsupported app package URL: {app_package_url} "
                    "(expected .zip or .tar.gz)"
                )
            await response.unpack_archive(format=_archive_format)
        else:
            print("Saving script to a file")
            with open(f"{python_module_name}.py", "w") as f:
                f.write(py_args["script"]);

        pkgs_path = "__pypackages__"
        if os.path.exists(pkgs_path):
            print(f"Adding {pkgs_path} to sys.path")
            sys.path.insert(0, pkgs_path)

        async def ensure_micropip():
            try:
                import micropip
            except ImportError:
                import pyodide_js
                await pyodide_js.loadPackage("micropip")
                import micropip
            return micropip

        if os.path.exists("requirements.txt"):
            with open("requirements.txt", "r") as f:
                deps = [
                    line
                    for req in f
                    if (line := req.strip()) and not line.startswith("#")
                ]
                if deps:
                    micropip = await ensure_micropip()
                    print("Loading requirements.txt:", deps)
                    await micropip.install(deps, pre=micropip_include_pre)

        if os.path.exists("pyproject.toml"):
            import tomllib
            with open("pyproject.toml", "rb") as f:
                pyproject = tomllib.load(f)
            project_deps = list(
                pyproject.get("project", {}).get("dependencies", []) or []
            )
            web_deps = list(
                pyproject.get("tool", {})
                .get("flet", {})
                .get("web", {})
                .get("dependencies", [])
                or []
            )
            # [tool.flet.web].dependencies overrides [project].dependencies
            # by package name — install in order so the web-specific specs
            # win through micropip's last-writer-wins dedupe.
            pyproject_deps = project_deps + web_deps
            if pyproject_deps:
                micropip = await ensure_micropip()
                print("Loading pyproject.toml deps:", pyproject_deps)
                await micropip.install(pyproject_deps, pre=micropip_include_pre)

        if "dependencies" in py_args:
            micropip = await ensure_micropip()
            await micropip.install(py_args["dependencies"], pre=micropip_include_pre)

        # Install the python_output bridge. msgpack normally rides in
        # with the user's flet dependency, but apps without a flet dep
        # (or without a pyproject.toml at all) would otherwise leave the
        # bridge unregistered and their prints stranded in the dev
        # console. Pyodide ships msgpack as a prebuilt package, so we
        # load it explicitly when it isn't already importable.
        try:
            import msgpack as _msgpack
        except ImportError:
            import pyodide_js
            await pyodide_js.loadPackage("msgpack")
            import msgpack as _msgpack

        def _send_python_output(text, is_stderr):
            # Frame exactly like PyodideConnection.send_message: a 0x00 type
            # byte (0x00 = MsgPack Flet protocol frame, 0x01 = raw DataChannel
            # frame) in front of the packed [action, body]. Without the prefix
            # the Dart side reads msgpack's leading 0x92 as an unknown packet
            # type and silently drops the line. bytes([0]) avoids a literal
            # NUL escape inside this JS template string.
            flet_js.receive_callback(
                bytes([0])
                + _msgpack.packb(
                    [7, {"text": text, "is_stderr": bool(is_stderr)}]
                )
            )

        flet_js.send_python_output = _send_python_output

        # Flip the worker into "user code" mode so stdout/stderr starts
        # flowing to the host page's Console pane instead of dev console.
        flet_js.userAppStarting()

        # Execute app. Treat a clean SystemExit (exit() / exit(0)) as
        # normal termination so the no-UI path below kicks in instead
        # of surfacing a Pyodide traceback. Non-zero codes propagate as
        # Script errors.
        try:
            runpy.run_module(python_module_name, run_name="__main__")
        except SystemExit as _exit:
            if _exit.code not in (None, 0):
                raise
      `);
        // `start_connection` is registered by `PyodideConnection.__init__`,
        // which only runs when the user app calls `ft.run(...)`. If the
        // script finished without it (e.g. a print-only test program),
        // surface a friendly message instead of a cryptic TypeError.
        // The `__flet_no_ui__:` sentinel lets host pages render a
        // neutral message rather than a Script error panel.
        if (typeof self.flet_js.start_connection !== "function") {
            self.postMessage(
                "__flet_no_ui__:Script finished without starting a Flet UI.\n" +
                "Add ft.run(main) at the end of your script to display the app."
            );
            return;
        }
        await self.flet_js.start_connection(self.receiveCallback);
        self.postMessage("initialized");
    } catch (error) {
        self.postMessage(error.toString());
    }
};

self.receiveCallback = (message) => {
    // `message` is a Pyodide JsProxy wrapping a Python `bytes`. `toJs()`
    // gives us a fresh Uint8Array; transferring its underlying ArrayBuffer
    // to the main thread skips the structured-clone copy (~hundreds of KB
    // per matplotlib frame). Safe because the Uint8Array is freshly
    // materialized here, and the original Python `bytes` is untouched
    // (Pyodide keeps its own reference).
    const bytes = message.toJs();
    self.postMessage(bytes, [bytes.buffer]);
}
// Same channel as `receiveCallback`, exposed under `flet_js` so the
// Python python_output shim can post pre-encoded msgpack frames.
self.flet_js.receive_callback = self.receiveCallback;

self.onmessage = async (event) => {
    if (event.data && event.data.prestart) {
        self.pyodideUrl = event.data.pyodideUrl;
        self.appPackageUrl = event.data.appPackageUrl;
        self.pythonModuleName = event.data.pythonModuleName;
        self.snapshotKey = event.data.snapshotKey;
        self.prestart();
        return;
    }
    // run only once
    if (!self.initialized) {
        self.initialized = true;
        self.pyodideUrl = event.data.pyodideUrl;
        self.flet_js.args = event.data.args;
        self.documentUrl = event.data.documentUrl;
        self.appPackageUrl = event.data.appPackageUrl;
        self.micropipIncludePre = event.data.micropipIncludePre;
        self.pythonModuleName = event.data.pythonModuleName;
        await self.initPyodide();
    } else if (typeof flet_js.send === "function") {
        // message
        flet_js.send(event.data);
    } else {
        console.error(
            "Flet: dropped a message for a Python app that never started."
        );
    }
};
