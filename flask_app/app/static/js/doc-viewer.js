/**
 * Document preview (eye) + image adjust (zoom / crop pan / rotate / flip)
 * for document upload/edit file fields.
 *
 * Preview: DocViewer.preview({ url, title, isImage })
 * File field host: <div data-doc-file data-name="file">…</div>
 */
(function () {
  const STAGE_W = 360;
  const STAGE_H = 260;
  const OUT_W = 1200;
  const MIN_ZOOM = 0.35;
  const MAX_ZOOM = 4;

  let previewShell = null;
  let editShell = null;
  let activeHost = null;
  let sourceImg = null;
  let state = { zoom: 1, rot: 0, flipH: 1, flipV: 1, x: 0, y: 0 };
  let drag = null;

  function clamp(n, a, b) {
    return Math.max(a, Math.min(b, n));
  }

  function ensurePreview() {
    if (previewShell) return previewShell;
    previewShell = document.createElement("div");
    previewShell.className = "modal-backdrop doc-preview-backdrop";
    previewShell.hidden = true;
    previewShell.innerHTML = `
      <div class="modal doc-preview-modal" role="dialog" aria-modal="true" aria-labelledby="docPreviewTitle">
        <div class="modal-head">
          <div>
            <div class="eyebrow">DOCUMENT</div>
            <h2 id="docPreviewTitle">Preview</h2>
            <p data-doc-preview-meta></p>
          </div>
          <button type="button" class="icon" data-doc-preview-close aria-label="Close">✕</button>
        </div>
        <div class="form-body doc-preview-body">
          <img data-doc-preview-img alt="Document" hidden>
          <iframe data-doc-preview-pdf title="Document PDF" hidden></iframe>
          <div class="doc-preview-empty" data-doc-preview-empty hidden>No file to show</div>
        </div>
        <div class="modal-foot">
          <a class="secondary" data-doc-preview-open href="#" target="_blank" rel="noopener">Open in new tab</a>
          <button type="button" class="primary" data-doc-preview-close>Close</button>
        </div>
      </div>`;
    document.body.appendChild(previewShell);
    previewShell.addEventListener("click", (e) => {
      if (e.target === previewShell || e.target.closest("[data-doc-preview-close]")) closePreview();
    });
    document.addEventListener("keydown", (e) => {
      if (e.key === "Escape" && previewShell && !previewShell.hidden) {
        e.stopPropagation();
        closePreview();
      }
    });
    return previewShell;
  }

  function closePreview() {
    if (!previewShell) return;
    previewShell.hidden = true;
    const img = previewShell.querySelector("[data-doc-preview-img]");
    const pdf = previewShell.querySelector("[data-doc-preview-pdf]");
    if (img) {
      img.hidden = true;
      img.removeAttribute("src");
    }
    if (pdf) {
      pdf.hidden = true;
      pdf.removeAttribute("src");
    }
    if (!document.querySelector(".modal-backdrop:not([hidden])")) {
      document.body.style.overflow = "";
    }
  }

  function preview(opts) {
    opts = opts || {};
    const url = opts.url || "";
    const title = opts.title || "Document";
    ensurePreview();
    previewShell.querySelector("#docPreviewTitle").textContent = title;
    const meta = previewShell.querySelector("[data-doc-preview-meta]");
    if (meta) meta.textContent = opts.meta || "View only";
    const img = previewShell.querySelector("[data-doc-preview-img]");
    const pdf = previewShell.querySelector("[data-doc-preview-pdf]");
    const empty = previewShell.querySelector("[data-doc-preview-empty]");
    const openLink = previewShell.querySelector("[data-doc-preview-open]");
    img.hidden = true;
    pdf.hidden = true;
    empty.hidden = true;
    if (!url) {
      empty.hidden = false;
      openLink.hidden = true;
    } else {
      openLink.hidden = false;
      openLink.href = url;
      const lower = String(url).toLowerCase().split("?")[0];
      const isPdf = opts.isPdf || lower.endsWith(".pdf");
      const isImage =
        opts.isImage ||
        /\.(png|jpe?g|webp|gif|bmp)$/i.test(lower) ||
        String(url).indexOf("blob:") === 0;
      if (isPdf) {
        pdf.src = url;
        pdf.hidden = false;
      } else if (isImage || !isPdf) {
        img.src = url;
        img.hidden = false;
      } else {
        empty.hidden = false;
      }
    }
    previewShell.hidden = false;
    document.body.style.overflow = "hidden";
  }

  function ensureEdit() {
    if (editShell) return editShell;
    editShell = document.createElement("div");
    editShell.className = "modal-backdrop doc-edit-backdrop";
    editShell.hidden = true;
    editShell.innerHTML = `
      <div class="modal logo-editor-modal doc-edit-modal" role="dialog" aria-modal="true" aria-labelledby="docEditTitle">
        <div class="modal-head">
          <div>
            <div class="eyebrow">DOCUMENT IMAGE</div>
            <h2 id="docEditTitle">Adjust document</h2>
            <p>Drag to crop · zoom, rotate and flip before saving.</p>
          </div>
          <button type="button" class="icon" data-doc-edit-close aria-label="Close">✕</button>
        </div>
        <div class="form-body logo-editor-body">
          <div class="logo-editor-stage-wrap">
            <div class="logo-editor-stage doc-edit-stage" data-doc-stage>
              <img data-doc-img alt="" draggable="false">
              <div class="logo-editor-frame doc-edit-frame" aria-hidden="true"></div>
            </div>
          </div>
          <div class="logo-editor-toolbar">
            <button type="button" class="secondary logo-tool" data-act="zoom-out" title="Zoom out">−</button>
            <input type="range" min="35" max="400" value="100" data-doc-zoom aria-label="Zoom">
            <button type="button" class="secondary logo-tool" data-act="zoom-in" title="Zoom in">+</button>
            <button type="button" class="secondary logo-tool" data-act="rot-left" title="Rotate left">↺</button>
            <button type="button" class="secondary logo-tool" data-act="rot-right" title="Rotate right">↻</button>
            <button type="button" class="secondary logo-tool" data-act="flip-h" title="Flip horizontal">⇋</button>
            <button type="button" class="secondary logo-tool" data-act="flip-v" title="Flip vertical">⇅</button>
            <button type="button" class="secondary logo-tool" data-act="reset" title="Reset">Reset</button>
          </div>
        </div>
        <div class="modal-foot">
          <button type="button" class="secondary" data-doc-edit-close>Cancel</button>
          <button type="button" class="primary" data-doc-edit-apply>Use this image</button>
        </div>
      </div>`;
    document.body.appendChild(editShell);
    editShell.addEventListener("click", (e) => {
      if (e.target === editShell || e.target.closest("[data-doc-edit-close]")) closeEdit(true);
    });
    editShell.querySelector("[data-doc-edit-apply]").addEventListener("click", applyEdit);
    editShell.querySelectorAll("[data-act]").forEach((btn) => {
      btn.addEventListener("click", () => runAction(btn.getAttribute("data-act")));
    });
    const zoom = editShell.querySelector("[data-doc-zoom]");
    zoom.addEventListener("input", () => {
      state.zoom = Number(zoom.value) / 100;
      paint();
    });
    const stage = editShell.querySelector("[data-doc-stage]");
    stage.addEventListener("pointerdown", onPointerDown);
    window.addEventListener("pointermove", onPointerMove);
    window.addEventListener("pointerup", onPointerUp);
    stage.addEventListener(
      "wheel",
      (e) => {
        if (!sourceImg) return;
        e.preventDefault();
        state.zoom = clamp(state.zoom * (e.deltaY < 0 ? 1.08 : 0.92), MIN_ZOOM, MAX_ZOOM);
        syncZoom();
        paint();
      },
      { passive: false }
    );
    document.addEventListener("keydown", (e) => {
      if (e.key === "Escape" && editShell && !editShell.hidden) {
        e.stopPropagation();
        closeEdit(true);
      }
    });
    return editShell;
  }

  function syncZoom() {
    const el = editShell && editShell.querySelector("[data-doc-zoom]");
    if (el) el.value = String(Math.round(state.zoom * 100));
  }

  function fitDefaults(img) {
    const base = Math.min(STAGE_W / img.naturalWidth, STAGE_H / img.naturalHeight);
    state = {
      zoom: clamp(base * 1.05, MIN_ZOOM, MAX_ZOOM),
      rot: 0,
      flipH: 1,
      flipV: 1,
      x: 0,
      y: 0,
    };
    syncZoom();
  }

  function paint() {
    if (!editShell || !sourceImg) return;
    const img = editShell.querySelector("[data-doc-img]");
    if (!img) return;
    img.hidden = false;
    img.src = sourceImg.src;
    img.style.display = "block";
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
    editShell.querySelector("[data-doc-stage]").setPointerCapture(e.pointerId);
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

  function openEdit(host, url) {
    ensureEdit();
    activeHost = host;
    // Ensure editor sits above any open form modal
    editShell.style.zIndex = "5000";
    editShell.hidden = false;
    document.body.style.overflow = "hidden";
    const stageImg = editShell.querySelector("[data-doc-img]");
    if (stageImg) {
      stageImg.removeAttribute("hidden");
      stageImg.style.opacity = "0.35";
    }
    const img = new Image();
    img.onload = () => {
      sourceImg = img;
      fitDefaults(img);
      paint();
      if (stageImg) stageImg.style.opacity = "1";
    };
    img.onerror = () => {
      window.alert("Could not load that image.");
      closeEdit(true);
    };
    img.src = url;
  }

  function closeEdit(cancelled) {
    const host = activeHost;
    if (!editShell) return;
    editShell.hidden = true;
    sourceImg = null;
    activeHost = null;
    // Keep selected image visible in the form preview if user cancels adjust
    if (cancelled && host) {
      const pending = host._docObjectUrl || host.getAttribute("data-current") || "";
      if (pending) setFilePreview(host, pending, !!host._docObjectUrl);
    }
    if (!document.querySelector(".modal-backdrop:not([hidden])")) {
      document.body.style.overflow = "";
    }
  }

  function applyEdit() {
    if (!activeHost || !sourceImg) return;
    const host = activeHost;
    const canvas = document.createElement("canvas");
    const scale = OUT_W / STAGE_W;
    canvas.width = OUT_W;
    canvas.height = Math.round(STAGE_H * scale);
    const ctx = canvas.getContext("2d");
    ctx.fillStyle = "#ffffff";
    ctx.fillRect(0, 0, canvas.width, canvas.height);
    ctx.save();
    ctx.translate(canvas.width / 2, canvas.height / 2);
    ctx.translate(state.x * scale, state.y * scale);
    ctx.rotate((state.rot * Math.PI) / 180);
    ctx.scale(state.zoom * scale * state.flipH, state.zoom * scale * state.flipV);
    ctx.drawImage(sourceImg, -sourceImg.naturalWidth / 2, -sourceImg.naturalHeight / 2);
    ctx.restore();
    canvas.toBlob(
      (blob) => {
        if (!blob || !host) return;
        const file = new File([blob], "document.jpg", { type: "image/jpeg" });
        const input = host.querySelector('input[type="file"]');
        if (input) {
          host.dataset.skipEditor = "1";
          const dt = new DataTransfer();
          dt.items.add(file);
          input.files = dt.files;
        }
        if (host._docObjectUrl) {
          try {
            URL.revokeObjectURL(host._docObjectUrl);
          } catch (e) {}
        }
        const previewUrl = URL.createObjectURL(blob);
        host._docObjectUrl = previewUrl;
        host.dataset.edited = "1";
        setFilePreview(host, previewUrl, true);
        closeEdit(false);
      },
      "image/jpeg",
      0.9
    );
  }

  function setFilePreview(host, url, edited) {
    if (!host) return;
    const thumb = host.querySelector("[data-doc-thumb]");
    const empty = host.querySelector("[data-doc-empty]");
    const editBtn = host.querySelector("[data-doc-adjust]");
    const clearBtn = host.querySelector("[data-doc-clear]");
    if (thumb) {
      if (url) {
        thumb.removeAttribute("hidden");
        thumb.hidden = false;
        thumb.src = url;
        thumb.style.display = "block";
      } else {
        thumb.hidden = true;
        thumb.removeAttribute("src");
        thumb.style.display = "none";
      }
    }
    if (empty) {
      empty.hidden = !!url;
      if (!url) empty.textContent = "PDF or image · optional adjust for photos";
    }
    if (editBtn) editBtn.hidden = !url;
    if (clearBtn) clearBtn.hidden = !url && !edited;
  }

  function clearFile(host) {
    const input = host.querySelector('input[type="file"]');
    if (input) {
      input.value = "";
      try {
        input.files = new DataTransfer().files;
      } catch (e) {}
    }
    if (host._docObjectUrl) {
      try {
        URL.revokeObjectURL(host._docObjectUrl);
      } catch (e) {}
      host._docObjectUrl = "";
    }
    host.dataset.edited = "";
    const current = host.getAttribute("data-current") || "";
    if (current && /\.(png|jpe?g|webp|gif)$/i.test(current)) setFilePreview(host, current, false);
    else setFilePreview(host, "", false);
  }

  function enhanceFileHost(host) {
    if (host.dataset.docReady) return;
    host.dataset.docReady = "1";
    let input = host.querySelector('input[type="file"]');
    if (!input) {
      input = document.createElement("input");
      input.type = "file";
      input.name = host.getAttribute("data-name") || "file";
      host.prepend(input);
    }
    input.accept = ".pdf,.png,.jpg,.jpeg,.webp,.gif,application/pdf,image/*";
    input.hidden = true;
    if (!host.querySelector(".doc-file-ui")) {
      const ui = document.createElement("div");
      ui.className = "doc-file-ui";
      ui.innerHTML = `
        <div class="doc-file-preview">
          <img data-doc-thumb alt="Preview" hidden>
          <div class="doc-file-empty" data-doc-empty>PDF or image · optional adjust for photos</div>
        </div>
        <div class="doc-file-btns">
          <button type="button" class="secondary" data-doc-pick>Choose file</button>
          <button type="button" class="secondary" data-doc-adjust hidden>Adjust image</button>
          <button type="button" class="text-btn" data-doc-clear hidden>Clear</button>
        </div>`;
      host.appendChild(ui);
    }
    const current = host.getAttribute("data-current") || "";
    if (current && /\.(png|jpe?g|webp|gif)$/i.test(current)) setFilePreview(host, current, false);

    host.querySelector("[data-doc-pick]").addEventListener("click", () => input.click());
    host.querySelector("[data-doc-adjust]").addEventListener("click", () => {
      const thumb = host.querySelector("[data-doc-thumb]");
      const src = (thumb && !thumb.hidden && thumb.src) || host.getAttribute("data-current");
      if (src) openEdit(host, src);
    });
    host.querySelector("[data-doc-clear]").addEventListener("click", () => clearFile(host));
    input.addEventListener("change", () => {
      const file = input.files && input.files[0];
      if (!file) return;
      if (host.dataset.skipEditor === "1") {
        host.dataset.skipEditor = "";
        return;
      }
      const isImage =
        /^image\//.test(file.type || "") ||
        /\.(png|jpe?g|webp|gif|bmp)$/i.test(file.name || "");
      if (host._docObjectUrl) {
        try {
          URL.revokeObjectURL(host._docObjectUrl);
        } catch (e) {}
        host._docObjectUrl = "";
      }
      if (isImage) {
        const url = URL.createObjectURL(file);
        host._docObjectUrl = url;
        // Show preview immediately, then open adjust editor on top
        setFilePreview(host, url, true);
        openEdit(host, url);
      } else {
        setFilePreview(host, "", false);
        const empty = host.querySelector("[data-doc-empty]");
        if (empty) {
          empty.hidden = false;
          empty.textContent = (file.name || "PDF selected") + " · ready to save";
        }
        const editBtn = host.querySelector("[data-doc-adjust]");
        const clearBtn = host.querySelector("[data-doc-clear]");
        if (editBtn) editBtn.hidden = true;
        if (clearBtn) clearBtn.hidden = false;
      }
    });
  }

  function init(root) {
    (root || document).querySelectorAll("[data-doc-file]").forEach(enhanceFileHost);
  }

  document.addEventListener("click", (e) => {
    const btn = e.target.closest("[data-doc-preview]");
    if (!btn) return;
    e.preventDefault();
    preview({
      url: btn.getAttribute("data-url") || btn.getAttribute("href") || "",
      title: btn.getAttribute("data-title") || "Document",
      meta: btn.getAttribute("data-meta") || "",
      isPdf: btn.getAttribute("data-pdf") === "1",
      isImage: btn.getAttribute("data-image") === "1",
    });
  });

  window.DocViewer = { preview, init, openEdit };
  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", () => init());
  } else {
    init();
  }
})();
