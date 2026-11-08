/* OpenMHS device market: instant search and filters over the static market index, and install tabs on package pages.
   Copy buttons are handled by app.js (any .copy-cmd[data-copy]). Without JavaScript the pages show every install
   option stacked and the category pages list every package. */
(function () {
  "use strict";

  function el(tag, className, text) {
    var node = document.createElement(tag);
    if (className) node.className = className;
    if (text != null) node.textContent = text;
    return node;
  }

  /* Text with `code spans` -> text and <code> nodes. */
  function appendInline(parent, text) {
    String(text || "").split("`").forEach(function (part, index) {
      if (!part) return;
      parent.appendChild(index % 2 ? el("code", "", part) : document.createTextNode(part));
    });
  }

  /* ---------------------------------------------------------------- install tabs (package pages) */
  function initTabs() {
    Array.prototype.forEach.call(document.querySelectorAll("[data-install-tabs]"), function (box) {
      var panels = Array.prototype.slice.call(box.querySelectorAll(".install-panel"));
      if (panels.length < 2) return;
      var list = el("div", "install-tablist");
      list.setAttribute("role", "tablist");
      list.setAttribute("aria-label", "Install options");
      var tabs = panels.map(function (panel, index) {
        var title = panel.querySelector(".install-panel-title");
        var tab = el("button", "install-tab", title ? title.textContent : "Option " + (index + 1));
        tab.type = "button";
        tab.id = panel.id + "-tab";
        tab.setAttribute("role", "tab");
        tab.setAttribute("aria-controls", panel.id);
        panel.setAttribute("role", "tabpanel");
        panel.setAttribute("aria-labelledby", tab.id);
        list.appendChild(tab);
        return tab;
      });
      function select(index, focus) {
        tabs.forEach(function (tab, i) {
          var on = i === index;
          tab.setAttribute("aria-selected", on ? "true" : "false");
          tab.tabIndex = on ? 0 : -1;
          panels[i].hidden = !on;
        });
        if (focus) tabs[index].focus();
      }
      list.addEventListener("click", function (event) {
        var tab = event.target.closest(".install-tab");
        if (tab) select(tabs.indexOf(tab), false);
      });
      list.addEventListener("keydown", function (event) {
        var current = tabs.indexOf(document.activeElement);
        if (current === -1) return;
        var next = null;
        if (event.key === "ArrowRight") next = (current + 1) % tabs.length;
        else if (event.key === "ArrowLeft") next = (current - 1 + tabs.length) % tabs.length;
        else if (event.key === "Home") next = 0;
        else if (event.key === "End") next = tabs.length - 1;
        if (next !== null) { event.preventDefault(); select(next, true); }
      });
      box.insertBefore(list, box.firstChild);
      box.classList.add("is-tabbed");
      function fromHash() {
        var wanted = location.hash.slice(1);
        for (var i = 0; i < panels.length; i++) if (panels[i].id === wanted) return i;
        return -1;
      }
      var start = fromHash();
      select(start === -1 ? 0 : start, false);
      window.addEventListener("hashchange", function () {
        var index = fromHash();
        if (index !== -1) select(index, false);
      });
    });
  }

  /* ---------------------------------------------------------------- explorer (market index) */
  function initExplorer() {
    var DATA = window.MHS_MARKET;
    var PAGE_SIZE = 48;
    var form = document.getElementById("market-filters");
    var layout = document.getElementById("market-layout");
    var results = document.getElementById("market-results");
    var countEl = document.getElementById("market-count");
    var activeEl = document.getElementById("market-active");
    var emptyEl = document.getElementById("market-empty");
    var pagerEl = document.getElementById("market-pagination");
    if (!form || !results || !DATA || !DATA.rows) return;

    var FILTERS = ["category", "track", "mode", "risk", "topic"];
    var LABELS = { category: "category", track: "track", mode: "mode", risk: "risk", topic: "topic" };
    var records = DATA.rows.map(function (row) {
      var item = {};
      (DATA.fields || []).forEach(function (key, index) { item[key] = row[index]; });
      item.stars = Number(item.stars) || 0;
      item.hay = [item.id, item.name, item.category, item.topic, item.search, item.excerpt].join(" ").toLowerCase();
      item.title = (item.name + " " + item.id).toLowerCase();
      return item;
    });

    function blank() { return { q: "", category: "", track: "", mode: "", risk: "", topic: "", sort: "relevance", page: 1 }; }
    var state = blank();

    function readUrl() {
      var params = new URLSearchParams(location.search);
      Object.keys(state).forEach(function (key) { if (params.has(key)) state[key] = params.get(key); });
      state.page = Math.max(1, parseInt(state.page, 10) || 1);
      syncForm();
    }

    function syncForm() {
      form.elements.q.value = state.q;
      ["category", "track", "mode", "risk", "sort"].forEach(function (key) {
        var field = form.elements[key];
        if (field) field.value = state[key];
      });
    }

    function writeUrl() {
      var params = new URLSearchParams();
      Object.keys(state).forEach(function (key) {
        var value = state[key];
        if (!value || (key === "sort" && value === "relevance") || (key === "page" && value === 1)) return;
        params.set(key, value);
      });
      var query = params.toString();
      history.replaceState(null, "", location.pathname + (query ? "?" + query : "") + location.hash);
    }

    function score(record, words) {
      if (!words.length) return 1;
      for (var i = 0; i < words.length; i++) if (record.hay.indexOf(words[i]) === -1) return 0;
      var s = 1;
      words.forEach(function (word) { if (record.title.indexOf(word) !== -1) s += 2; });
      if (record.name.toLowerCase().indexOf(words.join(" ")) !== -1) s += 3;
      return s;
    }

    function matches(record) {
      for (var i = 0; i < FILTERS.length; i++) {
        var key = FILTERS[i];
        if (state[key] && record[key] !== state[key]) return false;
      }
      return true;
    }

    function badge(text, tone) { return el("span", "badge badge-" + (tone || "muted"), text); }

    function card(record) {
      var li = el("li", "market-card");
      var title = el("h3", "market-card-title");
      var link = el("a", "", record.name);
      link.href = record.id + "/index.html";
      title.appendChild(link);
      li.appendChild(title);
      li.appendChild(el("p", "market-card-cat", record.topic && record.mode === "simulated" ? record.category + " · " + record.topic : record.category));
      var meta = el("div", "market-card-meta");
      if (record.mode) meta.appendChild(el("span", "mode-chip mode-" + record.mode, record.mode));
      if (record.risk) meta.appendChild(badge("Risk " + record.risk, { R0: "good", R1: "info", R2: "warn", R3: "bad" }[record.risk] || "muted"));
      if (record.license) meta.appendChild(badge(record.license, "muted"));
      li.appendChild(meta);
      var desc = el("p", "market-card-desc");
      appendInline(desc, record.excerpt);
      li.appendChild(desc);
      var command = "openai4s lab add " + record.id;
      var box = el("div", "market-cmd");
      box.appendChild(el("code", "", command));
      var copy = el("button", "copy-btn copy-cmd", "Copy");
      copy.type = "button";
      copy.setAttribute("data-copy", command);
      copy.setAttribute("aria-label", "Copy the install command");
      box.appendChild(copy);
      li.appendChild(box);
      return li;
    }

    function render() {
      var words = state.q.toLowerCase().split(/\s+/).filter(Boolean);
      var found = [];
      records.forEach(function (record) {
        if (!matches(record)) return;
        var s = score(record, words);
        if (s) found.push({ record: record, score: s });
      });
      var byName = function (a, b) { return a.record.name.localeCompare(b.record.name); };
      if (state.sort === "name") found.sort(byName);
      else if (state.sort === "stars") found.sort(function (a, b) { return b.record.stars - a.record.stars || byName(a, b); });
      else found.sort(function (a, b) { return b.score - a.score || b.record.stars - a.record.stars || byName(a, b); });

      var total = found.length;
      var pages = Math.max(1, Math.ceil(total / PAGE_SIZE));
      state.page = Math.min(Math.max(1, state.page), pages);
      var start = (state.page - 1) * PAGE_SIZE;
      results.innerHTML = "";
      var fragment = document.createDocumentFragment();
      found.slice(start, start + PAGE_SIZE).forEach(function (item) { fragment.appendChild(card(item.record)); });
      results.appendChild(fragment);

      var range = total > PAGE_SIZE ? " · showing " + (start + 1).toLocaleString() + "–" + Math.min(total, start + PAGE_SIZE).toLocaleString() : "";
      countEl.textContent = total.toLocaleString() + " of " + records.length.toLocaleString() + " packages" + (state.q ? " for “" + state.q + "”" : "") + range;
      emptyEl.hidden = total !== 0;
      results.hidden = total === 0;
      renderActive();
      renderPager(total, pages);
    }

    function chip(label, onRemove) {
      var node = el("span", "active-chip", label);
      var remove = el("button", "", "×");
      remove.type = "button";
      remove.setAttribute("aria-label", "Remove " + label);
      remove.addEventListener("click", onRemove);
      node.appendChild(remove);
      return node;
    }

    function renderActive() {
      activeEl.innerHTML = "";
      FILTERS.forEach(function (key) {
        if (!state[key]) return;
        activeEl.appendChild(chip(LABELS[key] + ": " + state[key], function () {
          state[key] = ""; state.page = 1; syncForm(); render(); writeUrl();
        }));
      });
      if (state.q) {
        activeEl.appendChild(chip("search: " + state.q, function () {
          state.q = ""; state.page = 1; syncForm(); render(); writeUrl();
        }));
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
          document.getElementById("browse-heading").scrollIntoView({ block: "start" });
        });
        pagerEl.appendChild(button);
      });
    }

    form.addEventListener("input", function (event) {
      if (event.target.name !== "q") return;
      state.q = event.target.value; state.page = 1; render(); writeUrl();
    });
    form.addEventListener("change", function (event) {
      if (event.target.name === "q") return;
      ["category", "track", "mode", "risk", "sort"].forEach(function (key) {
        if (form.elements[key]) state[key] = form.elements[key].value;
      });
      state.page = 1; render(); writeUrl();
    });
    form.addEventListener("submit", function (event) { event.preventDefault(); });
    form.addEventListener("reset", function (event) {
      event.preventDefault();
      state = blank(); syncForm(); render(); writeUrl();
    });
    var emptyReset = document.getElementById("market-empty-reset");
    if (emptyReset) emptyReset.addEventListener("click", function () { form.dispatchEvent(new Event("reset", { cancelable: true })); });

    form.hidden = false;
    if (layout) layout.classList.add("is-live");
    readUrl();
    /* On a phone the filters fold away under the search box unless a link already set one. */
    var refine = document.getElementById("market-refine");
    var narrow = window.matchMedia && window.matchMedia("(max-width: 980px)").matches;
    if (refine && narrow && !FILTERS.some(function (key) { return state[key]; }) && state.sort === "relevance") refine.open = false;
    render();
  }

  function init() { initTabs(); initExplorer(); }
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", init);
  else init();
})();
