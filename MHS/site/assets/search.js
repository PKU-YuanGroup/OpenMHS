/* MHS site search. The index is a generated static payload, loaded on first use. */
(function () {
  "use strict";

  var form = document.getElementById("site-search-form");
  var input = document.getElementById("site-search");
  var results = document.getElementById("search-results");
  var countEl = document.getElementById("search-count");
  var emptyEl = document.getElementById("search-empty");
  var suggestions = document.getElementById("search-suggestions");
  var typeButtons = Array.prototype.slice.call(document.querySelectorAll(".filter-btn[data-type]"));
  if (!form || !input || !results) return;

  var entries = [];
  var loaded = false;
  var loading = false;
  var failed = false;
  var activeType = "";
  var loadPromise = null;
  var typeMap = {
    spec: "Specification",
    capability: "Capability",
    family: "Family",
    market: "Market",
    site: "Site"
  };

  function setCount(text) {
    if (countEl) countEl.textContent = text;
  }

  function normalise(value) { return String(value == null ? "" : value).toLowerCase(); }

  function ingest(data, resolve) {
    loading = false;
    entries = (data || []).map(function (row) {
      return { title: row[0], url: row[1], section: row[2], snippet: row[3] || "" };
    });
    loaded = true;
    if (!input.value.trim()) setCount(entries.length.toLocaleString() + " indexed sections");
    resolve(entries);
  }

  function loadIndex() {
    if (loaded) return Promise.resolve(entries);
    if (loadPromise) return loadPromise;
    loading = true;
    setCount("Loading the search index…");
    loadPromise = new Promise(function (resolve, reject) {
      var finished = false;
      function ok(data) { if (!finished) { finished = true; ingest(data, resolve); } }
      function fallback() {
        var script = document.createElement("script");
        script.src = "../assets/search-index.js";
        script.async = true;
        script.onload = function () { ok(window.MHS_SEARCH || []); };
        script.onerror = function () {
          if (finished) return;
          finished = true;
          loading = false;
          failed = true;
          loadPromise = null;
          reject(new Error("search index could not be loaded"));
        };
        document.head.appendChild(script);
      }
      // JSON is preferred so the index is a real data artefact; the script
      // wrapper is the file:// fallback (fetch is blocked by file origins).
      if (location.protocol === "file:" || !window.fetch) {
        fallback();
        return;
      }
      fetch("../assets/search-index.json", { cache: "force-cache" })
        .then(function (response) {
          if (!response.ok) throw new Error("HTTP " + response.status);
          return response.json();
        })
        .then(ok, fallback);
    });
    return loadPromise;
  }

  function matchesType(entry) {
    if (!activeType) return true;
    return entry.section === typeMap[activeType];
  }

  function score(entry, terms) {
    var title = normalise(entry.title);
    var haystack = normalise(title + " " + entry.section + " " + entry.snippet);
    for (var i = 0; i < terms.length; i++) {
      if (haystack.indexOf(terms[i]) === -1) return 0;
    }
    var value = 1;
    if (title === terms.join(" ")) value += 4;
    else if (title.indexOf(terms.join(" ")) === 0) value += 3;
    else if (title.indexOf(terms[0]) !== -1) value += 2;
    if (entry.section === "Specification") value += 1;
    return value;
  }

  function appendHighlighted(parent, text, terms) {
    var lower = text.toLowerCase();
    var ranges = [];
    terms.forEach(function (term) {
      if (!term) return;
      var index = lower.indexOf(term);
      while (index !== -1) {
        ranges.push([index, index + term.length]);
        index = lower.indexOf(term, index + term.length);
      }
    });
    ranges.sort(function (a, b) { return a[0] - b[0]; });
    var merged = [];
    ranges.forEach(function (range) {
      var last = merged[merged.length - 1];
      if (last && range[0] <= last[1]) last[1] = Math.max(last[1], range[1]);
      else merged.push(range.slice());
    });
    var cursor = 0;
    merged.forEach(function (range) {
      if (range[0] > cursor) parent.appendChild(document.createTextNode(text.slice(cursor, range[0])));
      var mark = document.createElement("mark");
      mark.textContent = text.slice(range[0], range[1]);
      parent.appendChild(mark);
      cursor = range[1];
    });
    if (cursor < text.length) parent.appendChild(document.createTextNode(text.slice(cursor)));
  }

  function writeUrl(query) {
    if (!history.replaceState) return;
    var params = new URLSearchParams(location.search);
    if (query) params.set("q", query);
    else params.delete("q");
    var suffix = params.toString();
    history.replaceState(null, "", location.pathname + (suffix ? "?" + suffix : ""));
  }

  function render(query) {
    var raw = String(query || "").trim();
    var terms = normalise(raw).split(/\s+/).filter(Boolean);
    results.innerHTML = "";
    if (!raw) {
      if (suggestions) suggestions.hidden = false;
      if (emptyEl) emptyEl.hidden = true;
      if (loaded) setCount(entries.length.toLocaleString() + " indexed sections");
      return;
    }
    if (suggestions) suggestions.hidden = true;
    if (!loaded) {
      if (failed) {
        setCount("The search index could not be loaded. Use the registry download or the specification index.");
        if (emptyEl) emptyEl.hidden = false;
        return;
      }
      loadIndex().then(function () { render(raw); }, function () { render(raw); });
      return;
    }
    var matches = [];
    entries.forEach(function (entry) {
      if (!matchesType(entry)) return;
      var value = score(entry, terms);
      if (value) matches.push({ entry: entry, score: value });
    });
    matches.sort(function (a, b) {
      return b.score - a.score || a.entry.title.localeCompare(b.entry.title);
    });
    var fragment = document.createDocumentFragment();
    matches.slice(0, 80).forEach(function (match) {
      var li = document.createElement("li");
      li.className = "search-result";
      var badge = document.createElement("span");
      badge.className = "badge badge-muted";
      badge.textContent = match.entry.section || "Page";
      var heading = document.createElement("h2");
      var link = document.createElement("a");
      link.href = match.entry.url;
      appendHighlighted(link, match.entry.title, terms);
      heading.appendChild(link);
      li.appendChild(badge);
      li.appendChild(heading);
      if (match.entry.snippet) {
        var p = document.createElement("p");
        appendHighlighted(p, match.entry.snippet, terms);
        li.appendChild(p);
      }
      fragment.appendChild(li);
    });
    results.appendChild(fragment);
    var suffix = matches.length === 1 ? "result" : "results";
    setCount(matches.length.toLocaleString() + " " + suffix + " for “" + raw + "”" + (activeType ? " in " + typeMap[activeType] : ""));
    if (emptyEl) emptyEl.hidden = matches.length > 0;
    results.hidden = matches.length === 0;
  }

  typeButtons.forEach(function (button) {
    button.addEventListener("click", function () {
      activeType = button.getAttribute("data-type") || "";
      typeButtons.forEach(function (other) {
        var on = other === button;
        other.classList.toggle("is-active", on);
        other.setAttribute("aria-pressed", on ? "true" : "false");
      });
      if (!loaded && input.value.trim()) loadIndex().then(function () { render(input.value); }, function () { render(input.value); });
      else render(input.value);
    });
  });

  form.addEventListener("submit", function (event) {
    event.preventDefault();
    writeUrl(input.value.trim());
    render(input.value);
  });
  input.addEventListener("input", function () {
    writeUrl(input.value.trim());
    render(input.value);
  });
  input.addEventListener("focus", function () {
    if (!loaded) loadIndex().then(function () { if (input.value.trim()) render(input.value); }, function () {});
  }, { once: true });

  var params = new URLSearchParams(location.search);
  if (params.has("q")) {
    input.value = params.get("q");
    loadIndex().then(function () { render(input.value); }, function () { render(input.value); });
  }
  typeButtons.forEach(function (button) {
    var on = (button.getAttribute("data-type") || "") === activeType;
    button.setAttribute("aria-pressed", on ? "true" : "false");
  });
})();
