/**
 * Green Mile HR — soft navigation + centered loader (no hard reload flash).
 */
(function () {
  if (window.__gmShell) return;
  window.__gmShell = true;

  const LOADER_ID = "appLoader";
  let pending = 0;
  let busy = false;

  function ensureLoader() {
    let el = document.getElementById(LOADER_ID);
    if (el) return el;
    el = document.createElement("div");
    el.id = LOADER_ID;
    el.className = "app-loader";
    el.hidden = true;
    el.setAttribute("aria-live", "polite");
    el.setAttribute("aria-busy", "false");
    el.innerHTML =
      '<div class="app-loader-panel">' +
      '<div class="app-loader-orbit" aria-hidden="true"><span></span><span></span><span></span></div>' +
      '<p class="app-loader-text">Loading workspace</p>' +
      '<div class="app-loader-bar" aria-hidden="true"><i></i></div>' +
      "</div>";
    document.body.appendChild(el);
    return el;
  }

  function showAppLoader(message) {
    const el = ensureLoader();
    pending += 1;
    const text = el.querySelector(".app-loader-text");
    if (text) text.textContent = message || "Loading workspace";
    el.hidden = false;
    el.setAttribute("aria-busy", "true");
    document.documentElement.classList.add("gm-loading");
  }

  function hideAppLoader(force) {
    pending = force ? 0 : Math.max(0, pending - 1);
    if (pending > 0) return;
    const el = document.getElementById(LOADER_ID);
    if (!el) return;
    el.hidden = true;
    el.setAttribute("aria-busy", "false");
    document.documentElement.classList.remove("gm-loading");
    try {
      sessionStorage.removeItem("gmNav");
    } catch (_) {}
  }

  window.showAppLoader = showAppLoader;
  window.hideAppLoader = hideAppLoader;

  window.gmFetch = async function gmFetch(url, options) {
    showAppLoader((options && options.loaderMessage) || "Fetching data");
    try {
      return await fetch(url, Object.assign({ credentials: "same-origin" }, options || {}));
    } finally {
      hideAppLoader();
    }
  };

  function sameOrigin(href) {
    try {
      return new URL(href, window.location.href).origin === window.location.origin;
    } catch (_) {
      return false;
    }
  }

  function shouldSkipLink(a) {
    if (!a || !a.getAttribute("href")) return true;
    if (a.target && a.target !== "_self") return true;
    if (a.hasAttribute("download")) return true;
    if (a.dataset.fullNav === "1" || a.dataset.noSoft === "1") return true;
    const href = a.getAttribute("href") || "";
    if (href.startsWith("#") || href.startsWith("mailto:") || href.startsWith("tel:") || href.startsWith("javascript:"))
      return true;
    if (!sameOrigin(a.href)) return true;
    return false;
  }

  function shouldSkipForm(form) {
    if (!form) return true;
    if (form.target && form.target !== "_self") return true;
    if (form.dataset.fullNav === "1" || form.dataset.noSoft === "1") return true;
    if ((form.getAttribute("enctype") || "").includes("multipart")) return true;
    return false;
  }

  function isLoginForm(form) {
    if (!form) return false;
    if (form.closest(".admin-login")) return true;
    var path = (window.location.pathname || "").toLowerCase();
    return path.indexOf("/login") !== -1 || path.indexOf("employee-login") !== -1;
  }

  function markFullNav() {
    try {
      sessionStorage.setItem("gmNav", "1");
    } catch (_) {}
  }

  async function runBodyScripts(doc) {
    const nodes = Array.from(doc.body.querySelectorAll("script"));
    for (const old of nodes) {
      await new Promise((resolve) => {
        const s = document.createElement("script");
        if (old.src) {
          if (old.src.indexOf("app-shell.js") !== -1) {
            resolve();
            return;
          }
          s.src = old.src;
          s.onload = resolve;
          s.onerror = resolve;
          document.body.appendChild(s);
        } else {
          s.textContent = old.textContent;
          document.body.appendChild(s);
          resolve();
        }
      });
    }
  }

  async function softNavigate(url, { method = "GET", body = null, push = true } = {}) {
    if (busy) return;
    busy = true;
    showAppLoader(method === "POST" ? "Saving" : "Loading workspace");
    try {
      const opts = {
        method: method,
        credentials: "same-origin",
        headers: {
          Accept: "text/html",
          "X-Requested-With": "XMLHttpRequest",
          "X-Soft-Nav": "1",
        },
        redirect: "follow",
      };
      if (body) opts.body = body;

      const res = await fetch(url, opts);
      const finalUrl = res.url || url;
      const ct = (res.headers.get("content-type") || "").toLowerCase();

      if (!ct.includes("text/html")) {
        markFullNav();
        window.location.href = finalUrl;
        return;
      }

      const html = await res.text();
      const doc = new DOMParser().parseFromString(html, "text/html");

      document.title = doc.title || document.title;
      document.body.className = doc.body.className || "";

      const loader = ensureLoader();
      Array.from(document.body.childNodes).forEach(function (n) {
        if (n !== loader) n.remove();
      });

      Array.from(doc.body.childNodes).forEach(function (n) {
        if (n.nodeType === 1 && n.id === LOADER_ID) return;
        document.body.insertBefore(document.importNode(n, true), loader);
      });

      document.body.querySelectorAll("script").forEach(function (s) {
        s.remove();
      });

      await runBodyScripts(doc);

      if (push) history.pushState({ soft: 1 }, "", finalUrl);
      window.scrollTo(0, 0);
      document.dispatchEvent(new CustomEvent("gm:ready", { detail: { url: finalUrl } }));
    } catch (err) {
      console.error("Soft navigation failed, falling back", err);
      markFullNav();
      window.location.href = url;
    } finally {
      busy = false;
      hideAppLoader(true);
    }
  }

  window.softNavigate = softNavigate;

  document.addEventListener(
    "click",
    function (e) {
      if (e.defaultPrevented || e.button !== 0) return;
      if (e.metaKey || e.ctrlKey || e.shiftKey || e.altKey) return;
      const a = e.target.closest("a[href]");
      if (shouldSkipLink(a)) return;
      e.preventDefault();
      softNavigate(a.href);
    },
    true
  );

  // Bubble phase so onsubmit="return confirm(...)" can cancel first
  document.addEventListener("submit", function (e) {
    if (e.defaultPrevented) return;
    const form = e.target;
    if (!(form instanceof HTMLFormElement)) return;
    // Login pages: normal submit, never show the app loader
    if (isLoginForm(form)) return;
    if (shouldSkipForm(form)) {
      markFullNav();
      showAppLoader("Saving");
      return;
    }
    e.preventDefault();
    const action = form.getAttribute("action") || window.location.href;
    const method = (form.getAttribute("method") || "GET").toUpperCase();
    if (method === "GET") {
      const u = new URL(action, window.location.href);
      u.search = new URLSearchParams(new FormData(form)).toString();
      softNavigate(u.toString());
      return;
    }
    softNavigate(action, { method: "POST", body: new FormData(form) });
  });

  window.addEventListener("popstate", function () {
    softNavigate(window.location.href, { push: false });
  });

  function labelTextFor(el) {
    const wrap = el.closest("label");
    if (wrap) {
      const named = wrap.querySelector(".field-label, .login-eyebrow");
      if (named) {
        return (named.textContent || "").replace(/\*/g, "").replace(/\s+/g, " ").trim();
      }
      const clone = wrap.cloneNode(true);
      clone.querySelectorAll("input,select,textarea,button,small").forEach(function (n) {
        n.remove();
      });
      return (clone.textContent || "").replace(/\*/g, "").replace(/\s+/g, " ").trim();
    }
    if (el.getAttribute("aria-label")) return el.getAttribute("aria-label").trim();
    if (el.name) return el.name.replace(/[_-]+/g, " ").trim();
    return "";
  }

  var EXAMPLE_BY_NAME = {
    name: "Ahmed Khan",
    full_name: "Ahmed Khan",
    username: "ahmed.khan",
    email: "ahmed.khan@email.com",
    phone: "+971 50 123 4567",
    department: "Operations",
    designation: "Driver",
    address: "Al Quoz, Dubai",
    password: "••••••••",
    confirm: "••••••••",
    pin: "123456",
    employee_code: "EMP-1042",
    number: "C12345678",
    notes: "Additional details…",
    reason: "Family emergency",
    basic: "3500",
    q: "Search name or ID",
  };

  function exampleFor(el, label) {
    var key = (el.name || el.id || "").trim();
    if (EXAMPLE_BY_NAME[key]) return "e.g. " + EXAMPLE_BY_NAME[key];
    var type = (el.getAttribute("type") || "").toLowerCase();
    if (type === "email") return "e.g. name@email.com";
    if (type === "tel") return "e.g. +971 50 123 4567";
    if (type === "number") return "e.g. 100";
    if (type === "date") return "e.g. 15/03/2024";
    if (type === "time") return "e.g. 08:00";
    if (type === "month") return "e.g. 2026-03";
    if (type === "password") return "e.g. ••••••••";
    if (type === "search") return "e.g. search name or ID";
    if (label) return "e.g. " + label.toLowerCase();
    return "e.g. type here";
  }

  function applyPlaceholders(root) {
    const scope = root && root.querySelectorAll ? root : document;
    scope
      .querySelectorAll(
        "input:not([type=hidden]):not([type=submit]):not([type=button]):not([type=checkbox]):not([type=radio]):not([type=file]):not([type=image]), textarea"
      )
      .forEach(function (el) {
        var current = (el.getAttribute("placeholder") || "").trim();
        if (/^e\.g\./i.test(current)) return;
        if (current && !/^enter\b/i.test(current) && !/^select\b/i.test(current)) return;
        el.setAttribute("placeholder", exampleFor(el, labelTextFor(el)));
      });
    scope.querySelectorAll("select").forEach(function (sel) {
      const first = sel.querySelector("option");
      if (!first || first.value !== "") return;
      const text = (first.textContent || "").trim();
      if (/^e\.g\./i.test(text)) return;
      if (text && !/^select\b/i.test(text) && text !== "Select…" && text !== "Select...") return;
      const second = sel.querySelectorAll("option")[1];
      if (second && (second.textContent || "").trim()) {
        first.textContent = "e.g. " + second.textContent.trim();
      } else {
        const label = labelTextFor(sel);
        first.textContent = label ? "e.g. choose " + label.toLowerCase() : "e.g. choose an option";
      }
    });
  }

  window.applyPlaceholders = applyPlaceholders;

  document.addEventListener("DOMContentLoaded", function () {
    ensureLoader();
    hideAppLoader(true);
    applyPlaceholders(document);
  });
  document.addEventListener("gm:ready", function () {
    applyPlaceholders(document);
  });
})();
