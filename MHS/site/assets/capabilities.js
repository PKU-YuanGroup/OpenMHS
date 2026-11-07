/* MHS capability browser: instant filtering plus an accessible schema viewer.
   Data comes from the static, generated window.MHS_CAPABILITIES payload. */
(function () {
  "use strict";

  var input = document.getElementById("cap-q");
  var count = document.getElementById("cap-count");
  var cards = Array.prototype.slice.call(document.querySelectorAll(".cap-card"));
  var groups = Array.prototype.slice.call(document.querySelectorAll(".cap-group"));
  var verbButtons = Array.prototype.slice.call(document.querySelectorAll(".filter-btn[data-verb]"));
  var clearBtn = document.getElementById("cap-clear");
  var empty = document.getElementById("cap-empty");
  var dialog = document.getElementById("cap-dialog");
  var closeBtn = document.getElementById("cap-dialog-close");
  var dialogId = document.getElementById("cap-dialog-id");
  var dialogTitle = document.getElementById("cap-dialog-title");
  var dialogSummary = document.getElementById("cap-dialog-summary");
  var dialogBadges = document.getElementById("cap-dialog-badges");
  var dialogMeta = document.getElementById("cap-dialog-meta");
  var dialogExtras = document.getElementById("cap-dialog-extras");
  var schemaCode = document.getElementById("cap-schema-code");
  var tabs = Array.prototype.slice.call(document.querySelectorAll(".schema-tab"));
  var copyBtn = document.querySelector(".schema-copy");
  var data = (window.MHS_CAPABILITIES && window.MHS_CAPABILITIES.capabilities) || [];
  var byId = {};
  var activeVerb = "";
  var activeItem = null;
  var activeTab = "input";
  var trigger = null;

  data.forEach(function (item) { byId[item._slug || item.capability_id] = item; });

  function setText(node, text) {
    if (node) node.textContent = text == null ? "" : String(text);
  }

  function el(tag, className, text) {
    var node = document.createElement(tag);
    if (className) node.className = className;
    if (text != null) node.textContent = text;
    return node;
  }

  function badge(text, variant) {
    return el("span", "badge badge-" + (variant || "muted"), text);
  }

  function apply() {
    var needle = ((input && input.value) || "").toLowerCase().trim();
    var visible = 0;
    cards.forEach(function (card) {
      var haystack = (card.getAttribute("data-search") || card.textContent || "").toLowerCase();
      var verb = card.getAttribute("data-verb") || "";
      var match = (!needle || haystack.indexOf(needle) !== -1) && (!activeVerb || verb === activeVerb);
      card.hidden = !match;
      if (match) visible += 1;
    });
    groups.forEach(function (group) {
      var any = Array.prototype.some.call(group.querySelectorAll(".cap-card"), function (card) {
        return !card.hidden;
      });
      group.hidden = !any;
    });
    if (count) {
      count.textContent = activeVerb && visible === cards.length
        ? cards.length + " " + activeVerb + " classes"
        : visible + " of " + cards.length + " capability classes";
    }
    if (empty) empty.hidden = visible !== 0;
    verbButtons.forEach(function (button) {
      var on = (button.getAttribute("data-verb") || "") === activeVerb;
      button.classList.toggle("is-active", on);
      button.setAttribute("aria-pressed", on ? "true" : "false");
    });
  }

  function classDocument(item) {
    return {
      capability_id: item.capability_id,
      title: item.title,
      verb: item.verb,
      status: item.status,
      since: item.since,
      domain: item.domain,
      resource_kinds: item.resource_kinds,
      modes: item.modes,
      summary: item.summary,
      tags: item.tags,
      units: item.units,
      effects: item.effects,
      hazards: item.hazards,
      determinism: item.determinism,
      concurrency: item.concurrency,
      risk_class: item.risk_class,
      limits: item.limits,
      constraints: item.constraints,
      notes: item.notes
    };
  }

  function currentSchema() {
    if (!activeItem) return {};
    if (activeTab === "output") return activeItem.output_schema || {};
    if (activeTab === "class") return classDocument(activeItem);
    return activeItem.input_schema || {};
  }

  function renderSchema() {
    setText(schemaCode, JSON.stringify(currentSchema(), null, 2));
    tabs.forEach(function (tab) {
      var on = tab.getAttribute("data-schema") === activeTab;
      tab.classList.toggle("is-active", on);
      tab.setAttribute("aria-selected", on ? "true" : "false");
      tab.setAttribute("tabindex", on ? "0" : "-1");
    });
  }

  function metaRow(label, value) {
    var wrap = el("div", "dialog-meta-row");
    wrap.appendChild(el("dt", "", label));
    var dd = el("dd");
    if (value && value.nodeType) dd.appendChild(value);
    else dd.textContent = value == null || value === "" ? "—" : String(value);
    wrap.appendChild(dd);
    return wrap;
  }

  function fillDialog(item) {
    activeItem = item;
    setText(dialogId, item.capability_id);
    setText(dialogTitle, item._title || item.title);
    setText(dialogSummary, item._summary || item.summary || "");
    dialogBadges.innerHTML = "";
    dialogBadges.appendChild(badge(item._verb || item.verb, "info"));
    dialogBadges.appendChild(badge(item._risk || item.risk_class, "muted"));
    dialogBadges.appendChild(badge(item.status || "active", "good"));
    (item._modes || item.modes || []).forEach(function (mode) {
      dialogBadges.appendChild(el("span", "mode-chip mode-" + mode, mode));
    });

    dialogMeta.innerHTML = "";
    dialogMeta.appendChild(metaRow("Domain", item.domain));
    dialogMeta.appendChild(metaRow("Resource kinds", (item.resource_kinds || []).join(", ")));
    dialogMeta.appendChild(metaRow("Since", item.since));
    dialogMeta.appendChild(metaRow("Determinism", item.determinism));
    dialogMeta.appendChild(metaRow("Concurrency", item.concurrency));
    var unitKeys = Object.keys(item.units || {});
    dialogMeta.appendChild(metaRow("Units", unitKeys.length
      ? unitKeys.map(function (key) { return key + ": " + item.units[key]; }).join(", ")
      : "dimensionless / not declared"));

    dialogExtras.innerHTML = "";
    var tags = item._tags || item.tags || [];
    if (tags.length) {
      var tagWrap = el("div", "dialog-tags");
      tags.forEach(function (tag) { tagWrap.appendChild(el("span", "pill", tag)); });
      dialogExtras.appendChild(tagWrap);
    }
    if ((item.effects || []).length || (item.hazards || []).length) {
      var facts = el("dl", "dialog-facts");
      facts.appendChild(metaRow("Effects", (item.effects || []).join(", ")));
      facts.appendChild(metaRow("Hazards", (item.hazards || []).join(", ")));
      facts.appendChild(metaRow("Constraints", item.constraints
        ? Object.keys(item.constraints).map(function (key) { return key + ": " + item.constraints[key]; }).join(" · ")
        : "—"));
      dialogExtras.appendChild(facts);
    }
    if (item.notes) dialogExtras.appendChild(el("p", "dialog-note", item.notes));
    activeTab = "input";
    renderSchema();
  }

  function openDialog(item, opener) {
    if (!dialog || !item) return;
    trigger = opener || null;
    fillDialog(item);
    try {
      if (!dialog.open) dialog.showModal();
    } catch (err) {
      dialog.setAttribute("open", "");
    }
    if (history.replaceState) {
      history.replaceState(null, "", location.pathname + location.search + "#" + item.capability_id);
    }
    if (closeBtn) closeBtn.focus();
  }

  function closeDialog() {
    if (!dialog || !dialog.open) return;
    try { dialog.close(); } catch (err) { dialog.removeAttribute("open"); }
    if (history.replaceState) {
      history.replaceState(null, "", location.pathname + location.search);
    }
    if (trigger && trigger.focus) trigger.focus();
  }

  /* Filtering */
  if (input) input.addEventListener("input", apply);
  verbButtons.forEach(function (button) {
    button.addEventListener("click", function () {
      activeVerb = button.getAttribute("data-verb") || "";
      apply();
    });
  });
  if (clearBtn) clearBtn.addEventListener("click", function () {
    activeVerb = "";
    if (input) input.value = "";
    apply();
    if (input) input.focus();
  });

  /* Open the viewer from a card; the static hash is a deep link. */
  cards.forEach(function (card) {
    card.addEventListener("click", function (event) {
      var id = card.getAttribute("data-cap");
      if (!byId[id]) return;
      event.preventDefault();
      openDialog(byId[id], card);
    });
  });

  if (dialog) {
    dialog.addEventListener("click", function (event) {
      if (event.target === dialog) closeDialog();
    });
    dialog.addEventListener("close", function () {
      if (history.replaceState) history.replaceState(null, "", location.pathname + location.search);
    });
    dialog.addEventListener("keydown", function (event) {
      if (event.key === "Escape") { event.preventDefault(); closeDialog(); }
    });
  }
  if (closeBtn) closeBtn.addEventListener("click", closeDialog);

  tabs.forEach(function (tab) {
    tab.addEventListener("click", function () {
      activeTab = tab.getAttribute("data-schema") || "input";
      renderSchema();
    });
    tab.addEventListener("keydown", function (event) {
      var index = tabs.indexOf(tab);
      var next = null;
      if (event.key === "ArrowRight") next = tabs[(index + 1) % tabs.length];
      if (event.key === "ArrowLeft") next = tabs[(index - 1 + tabs.length) % tabs.length];
      if (event.key === "Home") next = tabs[0];
      if (event.key === "End") next = tabs[tabs.length - 1];
      if (!next) return;
      event.preventDefault();
      next.focus();
      activeTab = next.getAttribute("data-schema") || "input";
      renderSchema();
    });
  });

  if (copyBtn) {
    copyBtn.addEventListener("click", function () {
      var text = schemaCode ? schemaCode.textContent : "";
      var done = function () {
        copyBtn.textContent = "Copied";
        window.setTimeout(function () { copyBtn.textContent = "Copy"; }, 1600);
      };
      if (navigator.clipboard && navigator.clipboard.writeText) {
        navigator.clipboard.writeText(text).then(done, done);
      } else {
        var area = document.createElement("textarea");
        area.value = text;
        document.body.appendChild(area);
        area.select();
        try { document.execCommand("copy"); } catch (err) { /* clipboard unavailable */ }
        document.body.removeChild(area);
        done();
      }
    });
  }

  apply();

  /* Deep link: #cap.* opens the matching class once the page is ready. */
  var hashId = (location.hash || "").replace(/^#/, "");
  if (hashId && byId[hashId] && dialog) {
    var opener = document.querySelector('.cap-card[data-cap="' + hashId.replace(/"/g, "") + '"]');
    openDialog(byId[hashId], opener);
  }
})();
