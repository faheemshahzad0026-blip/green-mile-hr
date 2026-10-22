/**
 * In-app agency logo editor: pick, pan/crop, zoom, rotate, flip.
 * Bind with <div class="logo-editor" data-logo-editor data-current="optional-url">
 *   <input type="file" name="logo" class="logo-editor-input" accept="image/*" hidden>
 * </div>
 */
(function () {
  const STAGE = 280;
  const OUTPUT = 400;
  const MIN_ZOOM = 0.4;
  const MAX_ZOOM = 4;

  let shell = null;
  let active = null;
  let sourceImg = null;
  let state = { zoom: 1, rot: 0, flipH: 1, flipV: 1, x: 0, y: 0 };
  let drag = null;

  function ensureShell() {
    if (shell) return shell;
    shell = document.createElement("div");
    shell.className = "modal-backdrop logo-editor-backdrop";
    shell.hidden = true;
    shell.innerHTML = `
      <div class="modal logo-editor-modal" role="dialog" aria-modal="true" aria-labelledby="logoEditorTitle">
        <div class="modal-head">
          <div>
            <div class="eyebrow">LOGO</div>
            <h2 id="logoEditorTitle">Adjust logo</h2>
            <p>Drag to crop · zoom, rotate and flip before saving.</p>
          </div>
          <button type="button" class="icon" data-logo-close aria-label="Close">✕</button>
        </div>
        <div class="form-body logo-editor-body">
          <div class="logo-editor-stage-wrap">
            <div class="logo-editor-stage" data-logo-stage>
              <img data-logo-img alt="" draggable="false">
              <div class="logo-editor-frame" aria-hidden="true"></div>
            </div>
          </div>
          <div class="logo-editor-toolbar">
            <button type="button" class="secondary logo-tool" data-act="zoom-out" title="Zoom out">−</button>
            <input type="range" min="40" max="400" value="100" data-logo-zoom aria-label="Zoom">
            <button type="button" class="secondary logo-tool" data-act="zoom-in" title="Zoom in">+</button>
            <button type="button" class="secondary logo-tool" data-act="rot-left" title="Rotate left">↺</button>
            <button type="button" class="secondary logo-tool" data-act="rot-right" title="Rotate right">↻</button>
            <button type="button" class="secondary logo-tool" data-act="flip-h" title="Flip horizontal">⇋</button>
            <button type="button" class="secondary logo-tool" data-act="flip-v" title="Flip vertical">⇅</button>
            <button type="button" class="secondary logo-tool" data-act="reset" title="Reset">Reset</button>
          </div>
          <p class="logo-editor-hint">Square crop is used for the sidebar logo and favicon.</p>
        </div>
        <div class="modal-foot">
          <button type="button" class="secondary" data-logo-close>Cancel</button>
          <button type="button" class="primary" data-logo-apply>Use this logo</button>
        </div>
      </div>`;
    document.body.appendChild(shell);

    shell.addEventListener("click", (e) => {
      if (e.target === shell || e.target.closest("[data-logo-close]")) closeEditor(true);
    });
    shell.querySelector("[data-logo-apply]").addEventListener("click", applyEditor);
    document.addEventListener("keydown", (e) => {
      if (e.key === "Escape" && shell && !shell.hidden) {
        e.stopPropagation();
        closeEditor(true);
      }
    });
    shell.querySelectorAll("[data-act]").forEach((btn) => {
      btn.addEventListener("click", () => runAction(btn.getAttribute("data-act")));
    });
    const zoom = shell.querySelector("[data-logo-zoom]");
    zoom.addEventListener("input", () => {
      state.zoom = Number(zoom.value) / 100;
      paint();
    });

    const stage = shell.querySelector("[data-logo-stage]");
    stage.addEventListener("pointerdown", onPointerDown);
    window.addEventListener("pointermove", onPointerMove);
    window.addEventListener("pointerup", onPointerUp);
    stage.addEventListener(
      "wheel",
      (e) => {
        if (!sourceImg) return;
        e.preventDefault();
        const next = state.zoom * (e.deltaY < 0 ? 1.08 : 0.92);
        state.zoom = clamp(next, MIN_ZOOM, MAX_ZOOM);
        syncZoom();
        paint();
      },
      { passive: false }
    );
    return shell;
  }

  function clamp(n, a, b) {
    return Math.max(a, Math.min(b, n));
  }

  function syncZoom() {
    const el = shell && shell.querySelector("[data-logo-zoom]");
    if (el) el.value = String(Math.round(state.zoom * 100));
  }

  function fitDefaults(img) {
    const base = Math.min(STAGE / img.naturalWidth, STAGE / img.naturalHeight);
    state = {
      zoom: clamp(base * 1.15, MIN_ZOOM, MAX_ZOOM),
      rot: 0,
      flipH: 1,
      flipV: 1,
      x: 0,
      y: 0,
    };
    syncZoom();
  }

  function paint() {
    if (!shell || !sourceImg) return;
    const img = shell.querySelector("[data-logo-img]");
    img.src = sourceImg.src;
    img.style.width = sourceImg.naturalWidth + "px";
    img.style.height = sourceImg.naturalHeight + "px";
    img.style.transform =
      `translate(-50%, -50%) translate(${state.x}px, ${state.y}px) ` +
      `rotate(${state.rot}deg) scale(${state.zoom * state.flipH}, ${state.zoom * state.flipV})`;
  }

  function runAction(act) {
    if (!sourceImg) return;
    if (act === "zoom-in") state.zoom = clamp(state.zoom * 1.12, MIN_ZOOM, MAX_ZOOM);
    if (act === "zoom-out") state.zoom = clamp(state.zoom / 1.12, MIN_ZOOM, MAX_ZOOM);
    if (act === "rot-left") state.rot = (state.rot - 90) % 360;
    if (act === "rot-right") state.rot = (state.rot + 90) % 360;
    if (act === "flip-h") state.flipH *= -1;
    if (act === "flip-v") state.flipV *= -1;
    if (act === "reset") fitDefaults(sourceImg);
    syncZoom();
    paint();
  }

  function onPointerDown(e) {
    if (!sourceImg || e.button !== 0) return;
    const stage = shell.querySelector("[data-logo-stage]");
    stage.setPointerCapture(e.pointerId);
    drag = { px: e.clientX, py: e.clientY, ox: state.x, oy: state.y };
  }

  function onPointerMove(e) {
    if (!drag) return;
    state.x = drag.ox + (e.clientX - drag.px);
    state.y = drag.oy + (e.clientY - drag.py);
    paint();
  }

  function onPointerUp() {
    drag = null;
  }

  function openEditor(host, url) {
    ensureShell();
    active = host;
    const img = new Image();
    img.onload = () => {
      sourceImg = img;
      fitDefaults(img);
      paint();
      shell.hidden = false;
      document.body.style.overflow = "hidden";
    };
    img.onerror = () => {
      window.alert("Could not load that image.");
      active = null;
    };
    img.src = url;
  }

  function closeEditor(cancelled) {
    if (!shell) return;
    const host = active;
    shell.hidden = true;
    sourceImg = null;
    active = null;
    if (cancelled && host && host.dataset.picking === "1") {
      host.dataset.picking = "";
      const input = host.querySelector(".logo-editor-input, input[type=file]");
      if (host._logoFile && input) {
        host.dataset.skipEditor = "1";
        const dt = new DataTransfer();
        dt.items.add(host._logoFile);
        input.files = dt.files;
        const thumb = host.querySelector("[data-logo-thumb]");
        setPreview(host, (thumb && thumb.src) || URL.createObjectURL(host._logoFile), true);
      } else {
        if (input) {
          input.value = "";
          try {
            input.files = new DataTransfer().files;
          } catch (e) {}
        }
        setPreview(host, host.getAttribute("data-current") || "", false);
      }
    }
    if (!document.querySelector(".modal-backdrop:not([hidden])")) {
      document.body.style.overflow = "";
    }
  }

  function applyEditor() {
    if (!active || !sourceImg) return;
    const canvas = document.createElement("canvas");
    canvas.width = OUTPUT;
    canvas.height = OUTPUT;
    const ctx = canvas.getContext("2d");
    const scale = OUTPUT / STAGE;
    ctx.fillStyle = "#ffffff";
    ctx.fillRect(0, 0, OUTPUT, OUTPUT);
    ctx.save();
    ctx.translate(OUTPUT / 2, OUTPUT / 2);
    ctx.translate(state.x * scale, state.y * scale);
    ctx.rotate((state.rot * Math.PI) / 180);
    ctx.scale(state.zoom * scale * state.flipH, state.zoom * scale * state.flipV);
    ctx.drawImage(sourceImg, -sourceImg.naturalWidth / 2, -sourceImg.naturalHeight / 2);
    ctx.restore();

    canvas.toBlob(
      (blob) => {
        if (!blob) return;
        const host = active;
        const file = new File([blob], "logo.png", { type: "image/png" });
        const input = host.querySelector(".logo-editor-input, input[type=file]");
        if (input) {
          host.dataset.skipEditor = "1";
          const dt = new DataTransfer();
          dt.items.add(file);
          input.files = dt.files;
          input.dispatchEvent(new Event("change", { bubbles: true }));
        }
        host._logoFile = file;
        const preview = URL.createObjectURL(blob);
        setPreview(host, preview, true);
        host.dataset.edited = "1";
        host.dataset.picking = "";
        closeEditor();
      },
      "image/png",
      0.92
    );
  }

  function setPreview(host, url, edited) {
    const thumb = host.querySelector("[data-logo-thumb]");
    const empty = host.querySelector("[data-logo-empty]");
    const editBtn = host.querySelector("[data-logo-edit]");
    const clearBtn = host.querySelector("[data-logo-clear]");
    if (thumb) {
      thumb.hidden = !url;
      if (url) thumb.src = url;
    }
    if (empty) empty.hidden = !!url;
    if (editBtn) editBtn.hidden = !url;
    if (clearBtn) clearBtn.hidden = !url || (!edited && !host.dataset.current);
  }

  function clearLogo(host) {
    const input = host.querySelector(".logo-editor-input, input[type=file]");
    if (input) {
      input.value = "";
      try {
        const dt = new DataTransfer();
        input.files = dt.files;
      } catch (e) {}
    }
    host.dataset.edited = "";
    const current = host.getAttribute("data-current");
    if (current) setPreview(host, current, false);
    else setPreview(host, "", false);
  }

  function enhance(host) {
    if (host.dataset.logoReady) return;
    host.dataset.logoReady = "1";

    let input = host.querySelector("input[type=file]");
    if (!input) {
      input = document.createElement("input");
      input.type = "file";
      input.name = host.getAttribute("data-name") || "logo";
      input.accept = ".png,.jpg,.jpeg,.webp,.gif,image/png,image/jpeg,image/webp,image/gif";
      host.prepend(input);
    }
    input.classList.add("logo-editor-input");
    input.hidden = true;
    input.accept =
      input.accept ||
      ".png,.jpg,.jpeg,.webp,.gif,image/png,image/jpeg,image/webp,image/gif";

    if (!host.querySelector(".logo-editor-ui")) {
      const ui = document.createElement("div");
      ui.className = "logo-editor-ui";
      ui.innerHTML = `
        <div class="logo-editor-preview">
          <img data-logo-thumb alt="Logo preview" hidden>
          <div class="logo-editor-empty" data-logo-empty>No logo selected</div>
        </div>
        <div class="logo-editor-btns">
          <button type="button" class="secondary" data-logo-pick>Choose image</button>
          <button type="button" class="secondary" data-logo-edit hidden>Adjust</button>
          <button type="button" class="text-btn" data-logo-clear hidden>Clear</button>
        </div>
        <small class="admin-login-note">PNG, JPG, WEBP or GIF · crop, flip, rotate and zoom in the editor.</small>`;
      host.appendChild(ui);
    }

    const current = host.getAttribute("data-current");
    if (current) setPreview(host, current, false);

    host.querySelector("[data-logo-pick]").addEventListener("click", () => input.click());
    host.querySelector("[data-logo-edit]").addEventListener("click", () => {
      const thumb = host.querySelector("[data-logo-thumb]");
      const src = (thumb && !thumb.hidden && thumb.src) || host.getAttribute("data-current");
      if (src) openEditor(host, src);
    });
    host.querySelector("[data-logo-clear]").addEventListener("click", () => clearLogo(host));

    input.addEventListener("change", () => {
      const file = input.files && input.files[0];
      if (!file) return;
      if (host.dataset.skipEditor === "1") {
        host.dataset.skipEditor = "";
        return;
      }
      host.dataset.picking = "1";
      const url = URL.createObjectURL(file);
      openEditor(host, url);
    });
  }

  function init(root) {
    (root || document).querySelectorAll("[data-logo-editor]").forEach(enhance);
  }

  window.LogoEditor = { init, open: openEditor };
  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", () => init());
  } else {
    init();
  }
})();
