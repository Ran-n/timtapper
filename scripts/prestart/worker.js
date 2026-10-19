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
self.fletOptions = () => (FLET_OPTIONS);
self.loadPyodideWith = async function (options) {
    const pyodideModule = await import(self.pyodideUrl);
//FLET_LOAD_BODY
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

