/* MHS site shell: colour scheme, mobile navigation, copy buttons, docs TOC. */
(function () {
  "use strict";
  var root = document.documentElement;

  function preferredTheme() {
    var stored = null;
    try { stored = localStorage.getItem("mhs-theme"); } catch (e) { stored = null; }
    if (stored === "light" || stored === "dark") return stored;
    return window.matchMedia && window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";
  }

  function applyTheme(theme, persist) {
    root.dataset.theme = theme;
    if (persist) { try { localStorage.setItem("mhs-theme", theme); } catch (e) {} }
    var toggle = document.querySelector(".theme-toggle");
    if (toggle) toggle.setAttribute("aria-label", theme === "dark" ? "Switch to light colour scheme" : "Switch to dark colour scheme");
  }

  applyTheme(preferredTheme(), false);

  document.addEventListener("click", function (event) {
    var toggle = event.target.closest(".theme-toggle");
    if (toggle) {
      var next = root.dataset.theme === "dark" ? "light" : "dark";
      applyTheme(next, true);
      return;
    }
  });

  document.addEventListener("keydown", function (event) {
    if (event.key === "/" && !/^(INPUT|TEXTAREA|SELECT)$/.test(document.activeElement.tagName)) {
      var target = document.getElementById("registry-q") || document.getElementById("site-search") || document.getElementById("cap-q");
      if (target) { event.preventDefault(); target.focus(); }
    }
    if (event.key === "Escape") {
      var disclosure = document.querySelector(".nav-disclosure[open]");
      if (disclosure) {
        disclosure.open = false;
        var summary = disclosure.querySelector("summary");
        if (summary) { summary.focus(); summary.setAttribute("aria-expanded", "false"); }
      }
    }
  });

  /* The mobile menu is native <details>: keep ARIA and classes in sync,
     close it on an outside click, and never trap the page in an open state. */
  var disclosure = document.querySelector(".nav-disclosure");
  if (disclosure) {
    var summary = disclosure.querySelector("summary");
    var syncMenu = function () {
      var panel = disclosure.querySelector(".mobile-panel");
      if (panel) panel.classList.toggle("is-open", disclosure.open);
      if (summary) summary.setAttribute("aria-expanded", disclosure.open ? "true" : "false");
    };
    disclosure.addEventListener("toggle", syncMenu);
    syncMenu();
    document.addEventListener("click", function (event) {
      if (disclosure.open && !disclosure.contains(event.target)) {
        disclosure.open = false;
      }
    });
    disclosure.querySelectorAll(".mobile-panel a").forEach(function (link) {
      link.addEventListener("click", function () {
        disclosure.open = false;
        if (summary) summary.focus();
      });
    });
  }

  /* Add a visible permalink to headings that already carry stable ids. */
  function addHeadingAnchors() {
    document.querySelectorAll(".doc-body h2[id], .doc-body h3[id], .doc-body h4[id]").forEach(function (heading) {
      if (heading.querySelector(".heading-anchor")) return;
      var anchor = document.createElement("a");
      anchor.className = "heading-anchor";
      anchor.href = "#" + heading.id;
      anchor.setAttribute("aria-label", "Permalink to " + (heading.textContent || heading.id).trim());
      anchor.textContent = "#";
      heading.appendChild(anchor);
    });
  }

  /* Copy-to-clipboard for every code block. */
  function addCopyButtons() {
    document.querySelectorAll(".codeblock").forEach(function (block) {
      var bar = block.querySelector(".codeblock-bar");
      if (!bar || bar.querySelector(".copy-btn")) return;
      var button = document.createElement("button");
      button.type = "button";
      button.className = "copy-btn";
      button.textContent = "Copy";
      button.addEventListener("click", function () {
        var code = block.querySelector("pre");
        var text = code ? code.innerText : "";
        var done = function () { button.textContent = "Copied"; setTimeout(function () { button.textContent = "Copy"; }, 1600); };
        if (navigator.clipboard && navigator.clipboard.writeText) {
          navigator.clipboard.writeText(text).then(done, done);
        } else {
          var area = document.createElement("textarea");
          area.value = text; document.body.appendChild(area); area.select();
          try { document.execCommand("copy"); } catch (e) {}
          document.body.removeChild(area); done();
        }
      });
      bar.appendChild(button);
    });
  }

  /* Highlight the current section in a document TOC. */
  function activateToc() {
    var links = Array.from(document.querySelectorAll(".toc-list a[href^='#']"));
    if (!links.length || !("IntersectionObserver" in window)) return;
    var byId = {};
    links.forEach(function (link) { byId[link.getAttribute("href").slice(1)] = link; });
    var observer = new IntersectionObserver(function (entries) {
      entries.forEach(function (entry) {
        if (!entry.isIntersecting) return;
        links.forEach(function (link) { link.classList.remove("is-active"); });
        var link = byId[entry.target.id];
        if (link) link.classList.add("is-active");
      });
    }, { rootMargin: "-15% 0px -75% 0px", threshold: 0 });
    Object.keys(byId).forEach(function (id) {
      var section = document.getElementById(id);
      if (section) observer.observe(section);
    });
  }

  function markCurrentNav() {
    var path = location.pathname.split("/").pop() || "index.html";
    var section = location.pathname.split("/").slice(-2, -1)[0] || "";
    document.querySelectorAll(".nav-primary a").forEach(function (link) {
      var href = link.getAttribute("href") || "";
      var parts = href.replace(/^\.\.\//, "").split("/");
      var target = parts[0];
      if (target === section || (section === "" && target === "index.html") || href === path) {
        link.setAttribute("aria-current", "page");
      }
    });
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", function () { addHeadingAnchors(); addCopyButtons(); activateToc(); markCurrentNav(); });
  } else {
    addHeadingAnchors(); addCopyButtons(); activateToc(); markCurrentNav();
  }
})();
