// Author dashboard. Reads the data set embedded by scripts/bookctl.py (compute_stats).
(() => {
  const data = JSON.parse(document.getElementById("stats-data").textContent);
  const tooltip = document.getElementById("tooltip");
  const fmt = new Intl.NumberFormat("en-US");
  const compact = new Intl.NumberFormat("en-US", { notation: "compact", maximumFractionDigits: 1 });
  const SVG = "http://www.w3.org/2000/svg";
  let range = 30;

  const ddmm = (iso) => `${iso.slice(8, 10)}/${iso.slice(5, 7)}`;
  const ddmmyyyy = (iso) => `${ddmm(iso)}/${iso.slice(0, 4)}`;
  const sum = (rows, key) => rows.reduce((s, r) => s + (r[key] || 0), 0);

  function el(tag, attrs = {}, text) {
    const node = tag.startsWith("svg:") ? document.createElementNS(SVG, tag.slice(4)) : document.createElement(tag);
    for (const [k, v] of Object.entries(attrs)) node.setAttribute(k, v);
    if (text !== undefined) node.textContent = text;
    return node;
  }

  function slice(rangeDays) {
    return rangeDays ? data.days.slice(-rangeDays) : data.days;
  }

  // ------------------------------------------------------------ tiles
  function renderTiles() {
    const cur = slice(range);
    const prev = range ? data.days.slice(-2 * range, -range) : [];
    const period = range ? `Last ${range} days` : "All time";
    const comparable = prev.length === range;
    const tiles = [
      { label: "PDF downloads", value: sum(cur, "downloads"), prev: comparable ? sum(prev, "downloads") : null, note: period },
      data.has_views
        ? { label: "Page views", value: sum(cur, "views"), prev: comparable ? sum(prev, "views") : null, note: period }
        : { label: "Page views", value: null, note: "GoatCounter not set up yet" },
      { label: "Total downloads", value: sum(data.chapters, "downloads"), note: "Since the first release" },
      { label: "Chapters released", value: new Set(data.versions.map((v) => v.chapter)).size, note: `${data.versions.length} versions` },
    ];
    const box = document.getElementById("tiles");
    box.replaceChildren(
      ...tiles.map((t) => {
        const tile = el("div", { class: "tile" });
        tile.append(el("div", { class: "tile-label" }, t.label));
        tile.append(el("div", { class: "tile-value" }, t.value === null ? "-" : fmt.format(t.value)));
        let note = t.note;
        if (t.prev !== null && t.prev !== undefined) {
          const diff = t.value - t.prev;
          const sign = diff >= 0 ? "+" : "";
          const pct = t.prev ? ` (${sign}${Math.round((100 * diff) / t.prev)}%)` : "";
          note = `${t.note} · ${sign}${fmt.format(diff)}${pct} vs previous period`;
        }
        tile.append(el("div", { class: "tile-delta" }, note));
        return tile;
      }),
    );
  }

  // ------------------------------------------------------------ line chart
  // Axis top as 4 equal whole-number steps of 1, 2 or 5 x 10^k.
  function niceMax(v) {
    const raw = Math.max(1, v / 4);
    const pow = Math.pow(10, Math.floor(Math.log10(raw)));
    const step = [1, 2, 5, 10].map((m) => m * pow).find((s) => s >= raw);
    return 4 * Math.max(1, step);
  }

  function showTip(x, y, dateIso, value, color, label) {
    tooltip.replaceChildren();
    tooltip.append(el("strong", {}, value === null ? "No data" : fmt.format(value)));
    const row = el("div");
    const key = el("span", { class: "key" });
    key.style.background = color;
    row.append(key, document.createTextNode(`${label} · ${ddmmyyyy(dateIso)}`));
    tooltip.append(row);
    tooltip.hidden = false;
    const w = tooltip.offsetWidth;
    tooltip.style.left = `${Math.min(window.innerWidth - w - 8, x + 14)}px`;
    tooltip.style.top = `${y - 56}px`;
  }
  const hideTip = () => (tooltip.hidden = true);

  function lineChart(container, rows, key, colorVar, label, emptyText) {
    container.replaceChildren();
    const pts = rows.map((r) => ({ date: r.date, v: r[key] }));
    if (!pts.length || pts.every((p) => p.v === null)) {
      container.append(el("div", { class: "empty" }, emptyText));
      return;
    }
    const color = getComputedStyle(document.documentElement).getPropertyValue(colorVar).trim();
    const W = container.clientWidth, H = container.clientHeight;
    const m = { l: 36, r: 40, t: 12, b: 24 };
    const iw = W - m.l - m.r, ih = H - m.t - m.b;
    const max = niceMax(Math.max(...pts.map((p) => p.v || 0)));
    const x = (i) => m.l + (pts.length === 1 ? iw / 2 : (i * iw) / (pts.length - 1));
    const y = (v) => m.t + ih - (v / max) * ih;

    const svg = el("svg:svg", { viewBox: `0 0 ${W} ${H}`, role: "img", "aria-label": `${label} per day`, tabindex: "0" });
    for (let k = 0; k <= 4; k++) {
      const v = (max * k) / 4, yy = y(v);
      svg.append(el("svg:line", { x1: m.l, x2: W - m.r, y1: yy, y2: yy, class: k ? "grid-line" : "baseline" }));
      svg.append(el("svg:text", { x: m.l - 8, y: yy + 4, "text-anchor": "end", class: "tick" }, compact.format(v)));
    }
    const nTicks = Math.min(pts.length, Math.max(2, Math.floor(iw / 90)));
    for (let k = 0; k < nTicks; k++) {
      const i = Math.round((k * (pts.length - 1)) / Math.max(1, nTicks - 1));
      const anchor = k === 0 ? "start" : k === nTicks - 1 ? "end" : "middle";
      svg.append(el("svg:text", { x: x(i), y: H - 6, "text-anchor": anchor, class: "tick" }, ddmm(pts[i].date)));
    }

    // Split into runs of known values; a missing snapshot breaks the line.
    const runs = [];
    let run = [];
    pts.forEach((p, i) => {
      if (p.v === null) { if (run.length) runs.push(run); run = []; }
      else run.push(i);
    });
    if (run.length) runs.push(run);
    for (const r of runs) {
      const line = r.map((i, j) => `${j ? "L" : "M"}${x(i).toFixed(1)},${y(pts[i].v).toFixed(1)}`).join("");
      const area = `${line}L${x(r[r.length - 1]).toFixed(1)},${y(0)}L${x(r[0]).toFixed(1)},${y(0)}Z`;
      svg.append(el("svg:path", { d: area, fill: color, "fill-opacity": "0.1", stroke: "none" }));
      svg.append(el("svg:path", { d: line, fill: "none", stroke: color, "stroke-width": "2", "stroke-linejoin": "round", "stroke-linecap": "round" }));
    }

    // End marker with a value label at the line's end.
    const last = [...pts.keys()].reverse().find((i) => pts[i].v !== null);
    const surface = getComputedStyle(document.documentElement).getPropertyValue("--chart-surface").trim();
    svg.append(el("svg:circle", { cx: x(last), cy: y(pts[last].v), r: 4, fill: color, stroke: surface, "stroke-width": 2 }));
    svg.append(el("svg:text", { x: x(last) + 8, y: y(pts[last].v) + 4, class: "tick" }, compact.format(pts[last].v)));

    const hair = el("svg:line", { y1: m.t, y2: m.t + ih, class: "crosshair", visibility: "hidden" });
    const dot = el("svg:circle", { r: 4, fill: color, stroke: surface, "stroke-width": 2, visibility: "hidden" });
    svg.append(hair, dot);

    let active = last;
    function focusIndex(i, clientX, clientY) {
      active = Math.max(0, Math.min(pts.length - 1, i));
      const p = pts[active];
      hair.setAttribute("x1", x(active)); hair.setAttribute("x2", x(active));
      hair.setAttribute("visibility", "visible");
      if (p.v !== null) {
        dot.setAttribute("cx", x(active)); dot.setAttribute("cy", y(p.v)); dot.setAttribute("visibility", "visible");
      } else dot.setAttribute("visibility", "hidden");
      const box = svg.getBoundingClientRect();
      showTip(clientX ?? box.left + (x(active) / W) * box.width, clientY ?? box.top + 40, p.date, p.v, color, label);
    }
    function clear() { hair.setAttribute("visibility", "hidden"); dot.setAttribute("visibility", "hidden"); hideTip(); }
    svg.addEventListener("pointermove", (e) => {
      const box = svg.getBoundingClientRect();
      const px = ((e.clientX - box.left) / box.width) * W;
      focusIndex(Math.round(((px - m.l) / iw) * (pts.length - 1)), e.clientX, e.clientY);
    });
    svg.addEventListener("pointerleave", clear);
    svg.addEventListener("focus", () => focusIndex(active));
    svg.addEventListener("blur", clear);
    svg.addEventListener("keydown", (e) => {
      if (e.key === "ArrowLeft") { focusIndex(active - 1); e.preventDefault(); }
      if (e.key === "ArrowRight") { focusIndex(active + 1); e.preventDefault(); }
    });
    container.append(svg);
  }

  // ------------------------------------------------------------ bars and tables
  function renderChapters() {
    const box = document.getElementById("chart-chapters");
    const rows = data.chapters;
    const max = Math.max(1, ...rows.map((r) => r.downloads));
    box.replaceChildren(
      ...rows.map((r) => {
        const row = el("div", { class: "bar-row" });
        row.append(el("div", { class: "bar-name", title: r.title }, r.title));
        const track = el("div", { class: "bar-track" });
        const bar = el("div", { class: "bar" });
        bar.style.width = `${(r.downloads / max) * 85}%`;
        if (!r.downloads) bar.style.visibility = "hidden";
        track.append(bar, el("span", { class: "bar-value" }, fmt.format(r.downloads)));
        row.append(track);
        return row;
      }),
    );
  }

  function fillTable(id, rows, cells) {
    const body = document.querySelector(`#${id} tbody`);
    body.replaceChildren(
      ...rows.map((r) => {
        const tr = el("tr");
        for (const [value, cls] of cells(r)) {
          const td = el("td", cls ? { class: cls } : {});
          if (value instanceof Node) td.append(value); else td.textContent = value;
          tr.append(td);
        }
        return tr;
      }),
    );
    if (!rows.length) {
      const tr = el("tr");
      tr.append(el("td", { colspan: 4, class: "muted" }, "No data yet."));
      body.append(tr);
    }
  }

  function renderTables() {
    fillTable("table-versions", data.versions, (v) => [
      [v.title], [`v${v.version}`], [ddmmyyyy(v.published)], [fmt.format(v.downloads), "num"],
    ]);
    fillTable("table-pages", data.pages, (p) => [
      [el("code", {}, (p.event ? "event: " : "") + p.path)], [fmt.format(p.last30), "num"], [fmt.format(p.total), "num"],
    ]);
    fillTable("table-days", [...slice(range)].reverse(), (d) => [
      [ddmmyyyy(d.date)],
      [d.downloads === null ? "-" : fmt.format(d.downloads), "num"],
      [d.views === null ? "-" : fmt.format(d.views), "num"],
    ]);
  }

  function render() {
    const rows = slice(range);
    renderTiles();
    lineChart(document.getElementById("chart-downloads"), rows, "downloads", "--series-1", "Downloads", "No download snapshots yet.");
    lineChart(document.getElementById("chart-views"), rows, "views", "--series-2", "Views", data.has_views ? "No page views yet." : "GoatCounter is not set up yet (see README).");
    renderTables();
  }

  document.getElementById("dash-updated").textContent =
    `Updated ${data.generated_at}. Refreshed automatically every day.` + (data.demo ? " Sample data." : "");
  document.querySelectorAll(".range button").forEach((b) =>
    b.addEventListener("click", () => {
      range = Number(b.dataset.range);
      document.querySelectorAll(".range button").forEach((o) => o.setAttribute("aria-pressed", String(o === b)));
      render();
    }),
  );
  let resizeTimer;
  window.addEventListener("resize", () => { clearTimeout(resizeTimer); resizeTimer = setTimeout(render, 150); });
  window.matchMedia("(prefers-color-scheme: dark)").addEventListener("change", render);
  renderChapters();
  render();
})();
