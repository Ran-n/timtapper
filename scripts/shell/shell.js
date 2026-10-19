// The web shell: paints a read-only copy of the app's screens the moment the page opens, while Pyodide and the app
// start behind it, then fades out when the app says it's on screen. The copy is what the app saved on the last
// visit (ui/shell.py, kept in IndexedDB), or, on a first visit, the empty app built with the site.
//
// Moving around works in the copy itself: the tabs, opening an event, going back. A tap that needs the app (an edit,
// "New event") shows "Opening…", and the address is set so the app opens on that screen. The address only changes
// through history.replaceState, so the browser's history holds no screen the copy merely showed.
//
// scripts/build_web.py writes window.TIMTAPPER_SHELL before this script: the IndexedDB names, the ready channel, the
// codepoint of every icon the app uses, and the first-visit copies.
(() => {
  "use strict";
  const config = window.TIMTAPPER_SHELL;
  // ?noshell: the page as it was before the shell, to tell whether a browser's trouble comes from it
  if (!config || new URLSearchParams(location.search).has("noshell")) return;
  const READY_FADE_DELAY = 250; // ms after "ready": Flutter paints the app's first frame meanwhile
  const LOAD_TIMEOUT = 400; // ms to wait for the saved copy before showing the first-visit one

  const root = document.createElement("div");
  root.id = "tt-shell";
  document.body.prepend(root);
  const dark = window.matchMedia && window.matchMedia("(prefers-color-scheme: dark)").matches;
  let doc = null;
  let route = "/events";
  let pendingRoute = null; // what the app should open once ready, when the copy can't show it itself
  let gone = false;

  // ---- colors and sizes -------------------------------------------------
  function color(value) {
    if (typeof value !== "string") return null;
    const [token, opacity] = value.split(",");
    let hex = token.startsWith("#") ? token : (doc.colors[token.toLowerCase().replace(/_/g, "")] || token);
    if (opacity === undefined || !hex.startsWith("#")) return hex;
    hex = hex.slice(1);
    if (hex.length === 8) hex = hex.slice(2);
    const n = parseInt(hex, 16);
    return `rgba(${(n >> 16) & 255},${(n >> 8) & 255},${n & 255},${parseFloat(opacity)})`;
  }
  const px = (v) => (v === "inf" ? "100%" : typeof v === "number" ? `${v}px` : null);
  function edges(p) {
    if (p == null) return null;
    if (typeof p === "number") return `${p}px`;
    return `${p.top || 0}px ${p.right || 0}px ${p.bottom || 0}px ${p.left || 0}px`;
  }
  function radius(r) {
    if (r == null) return null;
    if (typeof r === "number") return `${r}px`;
    return `${r.top_left || 0}px ${r.top_right || 0}px ${r.bottom_right || 0}px ${r.bottom_left || 0}px`;
  }
  function borderSide(side) {
    if (!side) return null;
    return `${side.width ?? 1}px solid ${color(side.color) || "var(--outline)"}`;
  }
  const FONTS = { PoppinsSemiBold: "tt-semi", PoppinsExtraBold: "tt-heavy" };
  const ALIGN = { start: "flex-start", end: "flex-end", center: "center", spaceBetween: "space-between",
    spaceAround: "space-around", spaceEvenly: "space-evenly", stretch: "stretch", baseline: "baseline" };
  const axis = (a) => (a <= -0.5 ? "flex-start" : a >= 0.5 ? "flex-end" : "center");

  // ---- building blocks --------------------------------------------------
  function el(tag, cls, style) {
    const e = document.createElement(tag);
    if (cls) e.className = cls;
    if (style) for (const [k, v] of Object.entries(style)) if (v != null && v !== "") e.style[k] = v;
    return e;
  }
  function icon(data, size, col) {
    const name = data && (data.icon || data);
    const cp = config.icons[name];
    const e = el("span", "tt-ic", { fontSize: px(size || 24), width: px(size || 24), height: px(size || 24),
      color: col || null });
    if (cp) e.textContent = String.fromCodePoint(cp);
    return e;
  }
  function text(value, cls) {
    const e = el("span", cls);
    e.textContent = value;
    return e;
  }
  function imageSrc(src) {
    if (src && typeof src === "object" && src.img) {
      const data = doc.images[src.img];
      return data ? `data:image/webp;base64,${data}` : null;
    }
    return typeof src === "string" ? src : null;
  }
  function content(c) {
    // a button's content: a control, or plain text
    if (c == null) return null;
    return typeof c === "string" ? text(c) : render(c);
  }
  function flexChild(e, node, parentDir) {
    if (node.expand) {
      e.style.flex = `${node.expand === true ? 1 : node.expand} 1 0`;
      if (parentDir === "row") e.style.minWidth = "0";
    }
    return e;
  }
  function mark(e, node) {
    if (node.nav) {
      e.dataset.nav = node.nav;
      e.classList.add("tt-tap");
    } else if (node.tap) {
      e.dataset.tap = "1";
      e.classList.add("tt-tap");
    }
    if (node.visible === false) e.style.display = "none";
    return e;
  }

  // ---- controls ---------------------------------------------------------
  const R = {};
  function render(node, parentDir) {
    if (!node || typeof node !== "object") return el("span");
    const f = R[node.t] || R.Unknown;
    const e = f(node);
    return mark(flexChild(e, node, parentDir), node);
  }
  function children(e, nodes, dir) {
    for (const n of nodes || []) e.appendChild(render(n, dir));
    return e;
  }
  R.Unknown = (n) => (n.content ? render(n.content) : el("span"));
  R.Column = (n) => {
    const e = el("div", "tt-col", {
      gap: px(n.spacing ?? 10),
      justifyContent: ALIGN[n.alignment] || null,
      alignItems: ALIGN[n.horizontal_alignment || "start"],
      // stretching its children, a column is as wide as it may be (Flutter gives them its full width)
      width: n.horizontal_alignment === "stretch" ? "100%" : null,
    });
    return children(e, n.controls, "col");
  };
  R.Row = (n) => {
    const e = el("div", "tt-row", {
      gap: n.wrap ? `${n.run_spacing ?? 10}px ${n.spacing ?? 10}px` : px(n.spacing ?? 10),
      justifyContent: ALIGN[n.alignment] || null,
      alignItems: ALIGN[n.vertical_alignment || "center"],
      flexWrap: n.wrap ? "wrap" : null,
      display: n.tight ? "inline-flex" : null,
      width: n.tight ? null : "100%",
    });
    return children(e, n.controls, "row");
  };
  R.ResponsiveRow = (n) => {
    const spacing = n.spacing ?? 10;
    const e = el("div", "tt-row", { flexWrap: "wrap", gap: `${n.run_spacing ?? 10}px ${spacing}px`, width: "100%" });
    for (const c of n.controls || []) {
      const span = typeof c.col === "number" ? c.col : (c.col && (c.col.xs ?? c.col.sm)) || 12;
      const child = render(c, "row");
      child.style.flex = "none";
      child.style.width = `calc(${(span / 12) * 100}% - ${spacing * (1 - span / 12)}px)`;
      e.appendChild(child);
    }
    return e;
  };
  R.Stack = (n) => {
    const e = el("div", null, { position: "relative", width: px(n.width), height: px(n.height) });
    for (const c of n.controls || []) {
      const child = render(c);
      const positioned = ["left", "top", "right", "bottom"].some((k) => c[k] != null);
      if (positioned) {
        child.style.position = "absolute";
        for (const k of ["left", "top", "right", "bottom"]) if (c[k] != null) child.style[k] = `${c[k]}px`;
      }
      e.appendChild(child);
    }
    return e;
  };
  R.Container = (n) => {
    const e = el("div", null, {
      width: px(n.width),
      height: px(n.height),
      padding: edges(n.padding),
      margin: edges(n.margin),
      background: n.gradient ? gradient(n.gradient) : color(n.bgcolor),
      borderRadius: radius(n.border_radius),
      overflow: n.clip_behavior && n.clip_behavior !== "none" ? "hidden" : null,
      flex: "none",
    });
    if (n.border) {
      for (const side of ["top", "right", "bottom", "left"]) {
        const b = n.border[side];
        if (b) e.style[`border${side[0].toUpperCase()}${side.slice(1)}`] = borderSide(b);
      }
    }
    if (n.alignment) {
      Object.assign(e.style, { display: "flex", justifyContent: axis(n.alignment.x ?? 0),
        alignItems: axis(n.alignment.y ?? 0) });
      if (n.width == null) e.style.width = "100%";
    }
    if (n.content) {
      const child = render(n.content);
      if (!n.alignment && n.width == null && child.classList.contains("tt-row")) child.style.width = "100%";
      // a sized box (or one pinned to both edges of a stack) gives its column or row that size, as Flutter's
      // tight constraints do
      const flex = /tt-(col|row)/.test(child.className);
      if (flex && (n.height != null || (n.top != null && n.bottom != null))) child.style.height = "100%";
      if (flex && (n.width != null || (n.left != null && n.right != null))) child.style.width = "100%";
      e.appendChild(child);
    }
    if (n.expand && !n.content) e.style.alignSelf = "stretch";
    return e;
  };
  function gradient(g) {
    const stops = (g.colors || []).map((c, i) => `${color(c)}${g.stops ? ` ${g.stops[i] * 100}%` : ""}`);
    const vertical = (g.begin?.y ?? -1) !== (g.end?.y ?? 1) && (g.begin?.x ?? 0) === (g.end?.x ?? 0);
    return `linear-gradient(${vertical ? "180deg" : "90deg"}, ${stops.join(", ")})`;
  }
  R.Text = (n) => {
    const style = n.style || {};
    const family = n.font_family || style.font_family;
    const e = el("span", `tt-text ${FONTS[family] || ""}`, {
      fontSize: px(n.size ?? style.size),
      color: color(n.color ?? style.color),
      letterSpacing: px(style.letter_spacing),
      textAlign: n.text_align || null,
      whiteSpace: n.no_wrap ? "nowrap" : null,
    });
    if (n.max_lines) Object.assign(e.style, { display: "-webkit-box", webkitLineClamp: n.max_lines,
      webkitBoxOrient: "vertical", overflow: "hidden" });
    if (n.overflow === "ellipsis") Object.assign(e.style, { overflow: "hidden", textOverflow: "ellipsis" });
    e.textContent = n.value ?? "";
    return e;
  };
  R.Icon = (n) => icon(n.icon, n.size, color(n.color));
  R.Image = (n) => {
    const src = imageSrc(n.src);
    const box = el("div", null, { width: px(n.width), height: px(n.height), flex: "none", display: "flex",
      alignItems: "center", justifyContent: "center", overflow: "hidden" });
    const fallback = n.error_content ? render(n.error_content) : null;
    if (!src) {
      if (fallback) box.appendChild(fallback);
      return box;
    }
    const img = el("img", null, { width: "100%", height: "100%", objectFit: n.fit === "contain" ? "contain" : "cover" });
    img.alt = "";
    img.src = src;
    if (fallback) img.onerror = () => img.replaceWith(fallback);
    box.appendChild(img);
    return box;
  };
  function field(n, valueText, trailing) {
    const lead = n.prefix_icon || n.leading_icon;
    const e = el("div", `tt-field${n.dense ? " tt-dense" : ""}${lead ? " tt-lead" : ""}`, { width: px(n.width) });
    if (lead) {
      const box = el("span", "tt-field-lead");
      box.appendChild(lead.t ? render(lead) : icon(lead, 20, "var(--muted)"));
      e.appendChild(box);
    }
    const value = valueText ?? "";
    if (n.prefix && value) e.appendChild(render(n.prefix));
    const v = el("span", "tt-field-value", { fontSize: px(n.text_size) });
    if (value) {
      v.textContent = value;
      if (n.label) e.appendChild(text(n.label, "tt-field-label"));
    } else {
      v.textContent = n.label || n.hint_text || "";
      v.classList.add("tt-field-placeholder");
    }
    e.appendChild(v);
    if (trailing) e.appendChild(trailing);
    e.dataset.tap = "1";
    e.classList.add("tt-tap");
    return e;
  }
  R.TextField = (n) => field(n, n.value);
  R.Dropdown = (n) => {
    const option = (n.options || []).find((o) => o.key === n.value) || (n.options || [])[0];
    const node = option && option.leading_icon ? { ...n, leading_icon: option.leading_icon } : n;
    const e = field(node, option ? (option.text ?? option.key) : n.value, icon("arrow_drop_down", 20, "var(--muted)"));
    e.classList.add("tt-menu");
    return e;
  };
  function button(n, look) {
    const style = n.style || {};
    const e = el("div", `tt-btn tt-semi${n.icon ? " tt-has-icon" : ""}`, {
      height: px(n.height), width: px(n.width), ...look,
    });
    if (style.color) e.style.color = color(style.color);
    if (style.side) e.style.border = borderSide(style.side);
    if (style.padding) e.style.padding = edges(style.padding);
    if (n.icon) e.appendChild(icon(n.icon, 18));
    const c = content(n.content);
    if (c) e.appendChild(c);
    e.dataset.tap = "1";
    return e;
  }
  R.FilledButton = (n) => button(n, { background: "var(--primary)", color: "var(--bg)" });
  R.FilledTonalButton = (n) => button(n, { background: "var(--secondarycontainer)", color: "var(--fg)" });
  R.OutlinedButton = (n) => button(n, { border: "1px solid var(--outline)", color: "var(--primary)" });
  R.TextButton = (n) => button(n, { color: "var(--primary)", padding: "0 12px" });
  R.Button = R.FilledTonalButton;
  R.IconButton = (n) => {
    const e = el("div", "tt-iconbtn");
    e.appendChild(n.icon && n.icon.t ? render(n.icon) : icon(n.icon, 24, color(n.icon_color) || "var(--muted)"));
    e.dataset.tap = "1";
    return e;
  };
  R.PopupMenuButton = R.IconButton;
  R.Switch = (n) => {
    const e = el("div", `tt-switch${n.value ? " tt-on" : ""}`);
    const track = el("div", "tt-track");
    track.appendChild(el("div", "tt-thumb"));
    e.appendChild(track);
    if (n.label) e.appendChild(typeof n.label === "string" ? text(n.label) : render(n.label));
    e.dataset.tap = "1";
    return e;
  };
  R.SegmentedButton = (n) => {
    const e = el("div", "tt-seg tt-semi", { width: px(n.width) });
    const selected = new Set(n.selected || []);
    for (const s of n.segments || []) {
      const on = selected.has(s.value);
      const seg = el("div", on ? "tt-on" : null);
      // a selected segment shows a check in place of its icon, unless told not to
      if (on && n.show_selected_icon !== false) seg.appendChild(icon("check", 18));
      else if (s.icon) seg.appendChild(s.icon.t ? render(s.icon) : icon(s.icon, 18));
      const label = content(s.label);
      if (label) seg.appendChild(label);
      e.appendChild(seg);
    }
    e.dataset.tap = "1";
    return e;
  };
  R.ExpansionTile = (n) => {
    const shape = n.collapsed_shape || n.shape || {};
    const e = el("div", "tt-col", {
      background: color(n.collapsed_bgcolor || n.bgcolor),
      borderRadius: px(shape.radius),
      border: borderSide(shape.side),
      padding: edges(n.tile_padding) || "0 16px",
      minHeight: "56px",
      justifyContent: "center",
      gap: "2px",
      fontSize: "16px",
    });
    const title = typeof n.title === "string" ? text(n.title) : render(n.title);
    e.appendChild(title);
    if (n.subtitle) {
      const sub = typeof n.subtitle === "string" ? text(n.subtitle) : render(n.subtitle);
      sub.style.color = sub.style.color || "var(--muted)";
      e.appendChild(sub);
    }
    e.dataset.tap = "1";
    return e;
  };
  R.ProgressBar = (n) => {
    const e = el("div", "tt-progress", { height: px(n.bar_height ?? 4), background: color(n.bgcolor) || "var(--secondarycontainer)",
      borderRadius: radius(n.border_radius), width: "100%" });
    if (n.value != null) e.appendChild(el("div", null, { width: `${Math.max(0, Math.min(1, n.value)) * 100}%`,
      background: color(n.color) || "var(--primary)", borderRadius: radius(n.border_radius) }));
    return e;
  };
  R.ProgressRing = (n) => el("span", "tt-spin", { width: px(n.width), height: px(n.height) });
  R.Divider = () => el("div", null, { height: "1px", background: "var(--outlinevariant)", width: "100%" });

  // ---- screens ----------------------------------------------------------
  function appBar(view) {
    const bar = view.appbar || {};
    const e = el("div", "tt-bar");
    const back = route.startsWith("/event/");
    if (back) {
      const b = el("div", "tt-iconbtn");
      b.appendChild(icon("arrow_back", 24));
      b.dataset.nav = "/events";
      const lead = el("div", "tt-bar-lead", { width: "56px" });
      lead.appendChild(b);
      e.appendChild(lead);
    } else if (bar.leading) {
      const lead = el("div", "tt-bar-lead", { width: px(bar.leading_width ?? 56) });
      lead.appendChild(render(bar.leading));
      e.appendChild(lead);
    }
    const title = el("div", "tt-bar-title tt-heavy");
    title.textContent = bar.title ? (bar.title.value ?? "") : "";
    e.appendChild(title);
    for (const a of bar.actions || []) e.appendChild(render(a));
    return e;
  }
  function navBar(view) {
    const nav = view.navigation_bar;
    const e = el("div", "tt-nav");
    (nav.destinations || []).forEach((d, i) => {
      const on = i === (nav.selected_index ?? 0);
      const dest = el("div", `tt-dest${on ? " tt-on" : ""}`);
      const ind = el("div", "tt-dest-ind");
      ind.appendChild(icon(on && d.selected_icon ? d.selected_icon : d.icon, 24));
      dest.appendChild(ind);
      dest.appendChild(text(d.label || "", `tt-dest-label${on ? " tt-semi" : ""}`));
      dest.dataset.nav = doc.tabs[i];
      e.appendChild(dest);
    });
    return e;
  }
  function show(next) {
    const view = doc.views[next] || doc.views["/events"];
    route = doc.views[next] ? next : "/events";
    root.replaceChildren();
    root.appendChild(appBar(view));
    const body = el("div", "tt-body", { padding: edges(view.padding ?? 10) }); // a View's default padding
    for (const c of view.controls || []) body.appendChild(render(c, "col"));
    root.appendChild(body);
    if (view.navigation_bar) root.appendChild(navBar(view));
    const fab = view.floating_action_button;
    if (fab) {
      const f = el("div", `tt-fab tt-semi${view.navigation_bar ? "" : " tt-nonav"}`);
      if (fab.icon) f.appendChild(icon(fab.icon, 24));
      const label = content(fab.content);
      if (label) f.appendChild(label);
      if (fab.nav) f.dataset.nav = fab.nav;
      root.appendChild(f);
    }
    const opening = el("div", "tt-opening");
    opening.appendChild(el("span", "tt-spin"));
    opening.appendChild(text(doc.strings.opening));
    root.appendChild(opening);
    setAddress(route);
  }
  function setAddress(r) {
    const hash = `#${r}`;
    if (location.hash !== hash) history.replaceState(history.state, "", hash);
  }
  function busy() {
    root.classList.add("tt-busy");
  }

  root.addEventListener("click", (ev) => {
    if (gone || !doc) return;
    const target = ev.target.closest("[data-nav],[data-tap]");
    if (!target) return;
    const nav = target.dataset.nav;
    if (nav && doc.views[nav]) {
      show(nav);
      return;
    }
    if (nav) {
      // a screen the copy doesn't have ("New event"): the app opens it
      pendingRoute = nav;
      setAddress(nav);
    }
    busy();
  });

  // ---- the copy to show, and handing over -------------------------------
  function theme() {
    const s = doc.scheme;
    const c = doc.colors;
    const vars = { "--bg": s.bg, "--fg": s.fg, "--muted": s.muted, "--nav": s.nav, "--indicator": s.indicator,
      "--primary": c.primary, "--outline": c.outline, "--outlinevariant": c.outlinevariant,
      "--secondarycontainer": c.secondarycontainer, "--track": c.surfacecontainerhighest };
    for (const [k, v] of Object.entries(vars)) if (v) root.style.setProperty(k, v);
    document.documentElement.style.background = s.bg;
  }
  function start(saved) {
    if (doc || gone) return;
    try {
      doc = saved ? JSON.parse(saved) : null;
    } catch (e) {
      console.warn("timtapper shell: the saved copy is not JSON; showing the first-visit one", e);
      doc = null;
    }
    if (!doc || doc.v !== config.version) doc = config.defaults[dark ? "dark" : "light"];
    theme();
    const wanted = decodeURIComponent((location.hash || "").replace(/^#/, "")) || "/events";
    if (doc.views[wanted]) {
      show(wanted);
    } else {
      show("/events");
      if (wanted !== "/events") {
        pendingRoute = wanted; // a screen only the app can open (an event made since, "New event")
        setAddress(wanted);
        busy();
      }
    }
    console.log("timtapper shell: painted", route);
  }
  function load() {
    return new Promise((resolve) => {
      let open;
      try {
        open = indexedDB.open(config.db, 1);
      } catch (e) {
        console.warn("timtapper shell: no IndexedDB", e);
        resolve(null);
        return;
      }
      open.onupgradeneeded = () => open.result.createObjectStore(config.store);
      open.onerror = () => resolve(null);
      open.onsuccess = () => {
        try {
          const get = open.result.transaction(config.store).objectStore(config.store).get(config.key);
          get.onsuccess = () => { open.result.close(); resolve(get.result ?? null); };
          get.onerror = () => { open.result.close(); resolve(null); };
        } catch (e) {
          open.result.close();
          resolve(null);
        }
      };
    });
  }
  function handOver(appRoute) {
    if (gone) return;
    gone = true;
    // the app opened where the address pointed when it started; take it to what the shell shows (or was asked for)
    const wanted = pendingRoute || route;
    if (doc && appRoute && wanted !== appRoute) {
      history.replaceState(history.state, "", `#${appRoute}`);
      location.hash = wanted; // a real change of address: the app's router follows it
    }
    setTimeout(() => {
      root.classList.add("tt-gone");
      document.documentElement.style.background = "";
      setTimeout(() => root.remove(), 300);
    }, READY_FADE_DELAY);
    console.log("timtapper shell: handed over to the app");
  }

  if ("BroadcastChannel" in window) {
    const channel = new BroadcastChannel(config.channel);
    channel.onmessage = (ev) => {
      if (ev.data && ev.data.type === config.ready) {
        channel.close();
        handOver(ev.data.route);
      }
    };
  }
  const fallback = setTimeout(() => start(null), LOAD_TIMEOUT);
  load().then((saved) => {
    clearTimeout(fallback);
    start(saved);
  });
})();
