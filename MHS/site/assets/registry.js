/* MHS registry explorer: instant search over the static index with deep-linkable filters. */
(function () {
  "use strict";
  var DATA = window.MHS_REGISTRY;
  var PAGE_SIZE = 50;
  var form = document.getElementById("registry-filters");
  var results = document.getElementById("registry-results");
  var countEl = document.getElementById("registry-count");
  var activeEl = document.getElementById("registry-active");
  var emptyEl = document.getElementById("registry-empty");
  var loadingEl = document.getElementById("registry-loading");
  var pagerEl = document.getElementById("registry-pagination");
  var filterCountEl = document.getElementById("filter-count");
  if (!form || !results || !DATA) return;

  var records = (DATA.records || []).map(function (row) {
    var item = {};
    (DATA.fields || []).forEach(function (key, index) { item[key] = row[index]; });
    item.modes = String(item.modes || "").split("+").filter(Boolean);
    item.caps = Number(item.caps) || 0;
    item.ring = Number(item.ring) || 0;
    item.stars = Number(item.stars) || 0;
    return item;
  });

  var state = { q: "", track: "", family: "", tier: "", ring: "", mode: "", license: "", sort: "relevance", page: 1 };

  function normalise(value) { return String(value == null ? "" : value).toLowerCase(); }

  function readUrl() {
    var params = new URLSearchParams(location.search);
    ["q", "track", "family", "tier", "ring", "mode", "license", "sort", "page"].forEach(function (key) {
      if (params.has(key)) state[key] = params.get(key);
    });
    state.page = Math.max(1, parseInt(state.page, 10) || 1);
    form.elements.q.value = state.q;
    ["track", "family", "tier", "ring", "mode", "license", "sort"].forEach(function (key) {
      var field = form.elements[key];
      if (field) field.value = state[key];
    });
  }

  function writeUrl() {
    var params = new URLSearchParams();
    Object.keys(state).forEach(function (key) {
      if (state[key] && !(key === "sort" && state[key] === "relevance") && !(key === "page" && state.page === 1)) {
        params.set(key, state[key]);
      }
    });
    var query = params.toString();
    history.replaceState(null, "", location.pathname + (query ? "?" + query : "") + location.hash);
  }

  function score(record, needle) {
    if (!needle) return 1;
    var haystack = normalise(record.search || [record.title, record.desc, record.owner, record.repo, record.caps + " capabilities"].join(" "));
    if (haystack.indexOf(needle) === -1) return 0;
    var title = normalise(record.title + " " + record.owner + "/" + record.repo);
    var s = 1;
    if (title.indexOf(needle) !== -1) s += 3;
    if (normalise(record.owner + "/" + record.repo).indexOf(needle) !== -1) s += 2;
    return s;
  }

  function matches(record) {
    if (state.track && record.track !== state.track) return false;
    if (state.family && record.family !== state.family) return false;
    if (state.tier && record.tier !== state.tier) return false;
    if (state.ring && String(record.ring) !== String(state.ring)) return false;
    if (state.mode && (record.modes || []).indexOf(state.mode) === -1) return false;
    if (state.license && record.license !== state.license) return false;
    return true;
  }

  function el(tag, className, text) {
    var node = document.createElement(tag);
    if (className) node.className = className;
    if (text != null) node.textContent = text;
    return node;
  }

  function badge(text, variant) { return el("span", "badge " + (variant || "badge-muted"), text); }
  function modeChip(mode) {
    var chip = el("span", "mode-chip mode-" + (mode || "none"), mode || "unknown");
    return chip;
  }

  function render() {
    var needle = normalise(state.q).trim();
    var filtered = [];
    for (var i = 0; i < records.length; i++) {
      var record = records[i];
      if (!matches(record)) continue;
      var s = score(record, needle);
      if (needle && !s) continue;
      filtered.push({ record: record, score: s });
    }
    if (state.sort === "stars") {
      filtered.sort(function (a, b) { return (Number(b.record.stars) || 0) - (Number(a.record.stars) || 0); });
    } else if (state.sort === "name") {
      filtered.sort(function (a, b) { return String(a.record.title).localeCompare(String(b.record.title)); });
    } else if (state.sort === "tier") {
      var order = { A: 0, B: 1, C: 2, D: 3, X: 4 };
      filtered.sort(function (a, b) { return (order[a.record.tier] || 9) - (order[b.record.tier] || 9) || String(a.record.title).localeCompare(String(b.record.title)); });
    } else if (state.sort === "ring") {
      filtered.sort(function (a, b) { return (a.record.ring || 9) - (b.record.ring || 9) || String(a.record.title).localeCompare(String(b.record.title)); });
    } else {
      filtered.sort(function (a, b) { return b.score - a.score || (Number(b.record.stars) || 0) - (Number(a.record.stars) || 0); });
    }

    var total = filtered.length;
    var pages = Math.max(1, Math.ceil(total / PAGE_SIZE));
    state.page = Math.min(Math.max(1, state.page), pages);
    var start = (state.page - 1) * PAGE_SIZE;
    var slice = filtered.slice(start, start + PAGE_SIZE);

    results.innerHTML = "";
    var fragment = document.createDocumentFragment();
    slice.forEach(function (entry) {
      var record = entry.record;
      var li = el("li", "result-card");
      var top = el("div", "result-card-top");
      var title = el("h3", "result-title");
      var link = document.createElement("a");
      link.href = "repo/" + record.slug + ".html";
      link.textContent = record.title || (record.owner + "/" + record.repo);
      title.appendChild(link);
      top.appendChild(title);
      top.appendChild(el("span", "result-owner", record.owner + "/" + record.repo));
      li.appendChild(top);

      var meta = el("div", "result-meta");
      meta.appendChild(badge("tier " + record.tier, record.tier === "A" ? "badge-good" : record.tier === "X" ? "badge-bad" : "badge-muted"));
      meta.appendChild(badge("ring " + record.ring, "badge-info"));
      meta.appendChild(badge(record.family || "unclassified"));
      meta.appendChild(badge((record.evidence || "unknown") + " evidence", record.evidence === "runtime_tested" ? "badge-good" : record.evidence === "agent_read" ? "badge-accent" : "badge-muted"));
      (record.modes || []).forEach(function (mode) { meta.appendChild(modeChip(mode)); });
      if (record.license) meta.appendChild(badge(record.license));
      li.appendChild(meta);

      if (record.desc) li.appendChild(el("p", "result-desc", record.desc));

      var foot = el("div", "result-foot");
      if (record.caps > 0) {
        foot.appendChild(el("span", "cap-chip", record.caps + " capability claim" + (record.caps === 1 ? "" : "s")));
      } else {
        foot.appendChild(el("span", "badge badge-muted", "no capability claim"));
      }
      if (record.adapter && record.adapter !== "none") {
        foot.appendChild(el("span", "badge badge-muted", "adapter " + record.adapter));
      }
      li.appendChild(foot);
      fragment.appendChild(li);
    });
    results.appendChild(fragment);

    countEl.textContent = total.toLocaleString() + " record" + (total === 1 ? "" : "s") + (state.q ? " for “" + state.q + "”" : "");
    emptyEl.hidden = total !== 0;
    loadingEl.hidden = true;
    results.hidden = total === 0;
    renderActive();
    renderPager(total, pages);
    if (filterCountEl) filterCountEl.textContent = total.toLocaleString();
  }

  function renderActive() {
    activeEl.innerHTML = "";
    var filters = { track: "track", family: "family", tier: "tier", ring: "ring", mode: "mode", license: "licence" };
    Object.keys(filters).forEach(function (key) {
      if (!state[key]) return;
      var chip = el("span", "active-chip", filters[key] + ": " + state[key]);
      var remove = el("button", "", "×");
      remove.type = "button";
      remove.setAttribute("aria-label", "Remove " + filters[key] + " filter");
      remove.addEventListener("click", function () {
        state[key] = "";
        var field = form.elements[key];
        if (field) field.value = "";
        state.page = 1; render(); writeUrl();
      });
      chip.appendChild(remove);
      activeEl.appendChild(chip);
    });
    if (state.q) {
      var chip = el("span", "active-chip", "search: " + state.q);
      var removeSearch = el("button", "", "×");
      removeSearch.type = "button";
      removeSearch.setAttribute("aria-label", "Clear search");
      removeSearch.addEventListener("click", function () { state.q = ""; form.elements.q.value = ""; state.page = 1; render(); writeUrl(); });
      chip.appendChild(removeSearch);
      activeEl.appendChild(chip);
    }
  }

  function pageList(current, pages) {
    if (pages <= 9) return Array.from({ length: pages }, function (_, i) { return i + 1; });
    var set = [1];
    for (var i = current - 2; i <= current + 2; i++) if (i > 1 && i < pages) set.push(i);
    set.push(pages);
    var out = [];
    for (var j = 0; j < set.length; j++) {
      if (j > 0 && set[j] - set[j - 1] > 1) out.push("…");
      out.push(set[j]);
    }
    return out;
  }

  function renderPager(total, pages) {
    pagerEl.innerHTML = "";
    pagerEl.hidden = total <= PAGE_SIZE;
    if (total <= PAGE_SIZE) return;
    pageList(state.page, pages).forEach(function (item) {
      if (item === "…") { pagerEl.appendChild(el("span", "is-gap", "…")); return; }
      var button = el("button", item === state.page ? "is-current" : "", String(item));
      button.type = "button";
      button.setAttribute("aria-label", "Page " + item);
      if (item === state.page) button.setAttribute("aria-current", "page");
      button.addEventListener("click", function () {
        state.page = item; render(); writeUrl();
        document.getElementById("results-heading").scrollIntoView({ block: "start" });
      });
      pagerEl.appendChild(button);
    });
  }

  function onChange() {
    state.q = form.elements.q.value || "";
    ["track", "family", "tier", "ring", "mode", "license", "sort"].forEach(function (key) {
      if (form.elements[key]) state[key] = form.elements[key].value;
    });
    state.page = 1;
    render(); writeUrl();
  }

  form.addEventListener("input", function (event) {
    if (event.target.name === "q") { state.q = event.target.value; state.page = 1; render(); writeUrl(); }
  });
  form.addEventListener("change", onChange);
  form.addEventListener("reset", function (event) {
    event.preventDefault();
    state = { q: "", track: "", family: "", tier: "", ring: "", mode: "", license: "", sort: "relevance", page: 1 };
    form.reset();
    render(); writeUrl();
  });
  var emptyReset = document.getElementById("registry-empty-reset");
  if (emptyReset) emptyReset.addEventListener("click", function () { form.dispatchEvent(new Event("reset")); });

  readUrl();
  render();
})();
