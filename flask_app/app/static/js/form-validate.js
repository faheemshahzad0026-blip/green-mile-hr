/**
 * Live AJAX + HTML5 validation for all form inputs.
 */
(function () {
  if (window.__gmFormValidate) return;
  window.__gmFormValidate = true;

  var VALIDATE_URL = "/auth/validate-field";
  var timers = new WeakMap();

  function csrfToken() {
    var meta = document.querySelector('meta[name="csrf-token"]');
    if (meta && meta.content) return meta.content;
    var input = document.querySelector('input[name="csrf_token"]');
    return input ? input.value : "";
  }

  function fieldLabel(el) {
    var wrap = el.closest("label");
    if (wrap) {
      var named = wrap.querySelector(".field-label");
      if (named) return (named.textContent || "").replace(/\*/g, "").trim();
      var clone = wrap.cloneNode(true);
      clone.querySelectorAll("input,select,textarea,button,small,.field-error").forEach(function (n) {
        n.remove();
      });
      return (clone.textContent || "").replace(/\*/g, "").trim();
    }
    return el.name || "This field";
  }

  function ensureErrorEl(el) {
    var host = el.closest("label") || el.parentElement;
    if (!host) return null;
    var err = host.querySelector(".field-error");
    if (!err) {
      err = document.createElement("span");
      err.className = "field-error";
      err.setAttribute("aria-live", "polite");
      host.appendChild(err);
    }
    return err;
  }

  function setState(el, ok, message) {
    var err = ensureErrorEl(el);
    el.classList.toggle("is-invalid", !ok);
    el.classList.toggle("is-valid", ok && !!(el.value || "").trim());
    el.setAttribute("aria-invalid", ok ? "false" : "true");
    if (err) {
      err.textContent = ok ? "" : message || "Invalid value.";
      err.hidden = ok;
    }
    return ok;
  }

  function localValidate(el) {
    var value = (el.value || "").trim();
    var type = (el.getAttribute("type") || el.tagName.toLowerCase()).toLowerCase();
    var label = fieldLabel(el);

    if (
      el.disabled ||
      el.readOnly ||
      type === "hidden" ||
      type === "file" ||
      type === "checkbox" ||
      type === "radio" ||
      type === "submit" ||
      type === "button"
    ) {
      return { ok: true, message: "", skipAjax: true };
    }

    if (el.required && !value) {
      return {
        ok: false,
        message: label ? label + " is required." : "This field is required.",
        skipAjax: true,
      };
    }
    if (!value) return { ok: true, message: "", skipAjax: true };

    if (typeof el.checkValidity === "function" && !el.checkValidity()) {
      if (el.validity.tooShort) {
        return { ok: false, message: "Must be at least " + el.minLength + " characters.", skipAjax: true };
      }
      if (el.validity.tooLong) {
        return { ok: false, message: "Must be at most " + el.maxLength + " characters.", skipAjax: true };
      }
      if (el.validity.typeMismatch && type === "email") {
        return { ok: false, message: "Enter a valid email, e.g. name@email.com.", skipAjax: true };
      }
      if (el.validity.patternMismatch) {
        return { ok: false, message: "Format is not valid.", skipAjax: true };
      }
      if (el.validity.rangeUnderflow || el.validity.rangeOverflow) {
        return { ok: false, message: "Number is out of range.", skipAjax: true };
      }
      return { ok: false, message: el.validationMessage || "Invalid value.", skipAjax: true };
    }

    if (type === "email" && !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(value)) {
      return { ok: false, message: "Enter a valid email, e.g. name@email.com.", skipAjax: true };
    }

    if ((el.name === "confirm" || el.name === "password_confirm") && el.form) {
      var pass = el.form.querySelector('[name="password"], [name="admin_password"]');
      if (pass && pass.value && pass.value !== el.value) {
        return { ok: false, message: "Passwords do not match.", skipAjax: true };
      }
    }

    return { ok: true, message: "", skipAjax: false };
  }

  function ajaxValidate(el) {
    var name = el.name || "";
    if (!name) return Promise.resolve(true);
    var ajaxFields = {
      username: 1,
      admin_username: 1,
      email: 1,
      company_email: 1,
      password: 1,
      admin_password: 1,
      confirm: 1,
      password_confirm: 1,
      pin: 1,
      employee_code: 1,
      phone: 1,
      company_phone: 1,
      name: 1,
      full_name: 1,
      basic: 1,
      amount: 1,
    };
    if (!ajaxFields[name] && el.type !== "email" && el.type !== "number") {
      setState(el, true, "");
      return Promise.resolve(true);
    }

    var payload = {
      field: name,
      value: el.value || "",
      required: el.required ? "1" : "0",
      type: el.type || "",
    };
    if ((name === "confirm" || name === "password_confirm") && el.form) {
      var pass = el.form.querySelector('[name="password"], [name="admin_password"]');
      if (pass) payload.other = pass.value || "";
    }

    return fetch(VALIDATE_URL, {
      method: "POST",
      credentials: "same-origin",
      headers: {
        "Content-Type": "application/json",
        Accept: "application/json",
        "X-CSRFToken": csrfToken(),
        "X-Requested-With": "XMLHttpRequest",
      },
      body: JSON.stringify(payload),
    })
      .then(function (r) {
        return r.json();
      })
      .then(function (data) {
        return setState(el, !!data.ok, data.message || "");
      })
      .catch(function () {
        setState(el, true, "");
        return true;
      });
  }

  function validateOne(el) {
    var local = localValidate(el);
    if (!local.ok) {
      setState(el, false, local.message);
      return Promise.resolve(false);
    }
    if (local.skipAjax) {
      setState(el, true, "");
      return Promise.resolve(true);
    }
    return ajaxValidate(el);
  }

  function scheduleValidate(el) {
    var prev = timers.get(el);
    if (prev) clearTimeout(prev);
    timers.set(
      el,
      setTimeout(function () {
        validateOne(el);
      }, 350)
    );
  }

  function fieldsIn(form) {
    return Array.prototype.slice.call(form.querySelectorAll("input, select, textarea")).filter(function (el) {
      var t = (el.type || "").toLowerCase();
      return !el.disabled && t !== "hidden" && t !== "submit" && t !== "button" && t !== "image" && t !== "reset";
    });
  }

  function validateForm(form) {
    var list = fieldsIn(form);
    return Promise.all(
      list.map(function (el) {
        return validateOne(el);
      })
    ).then(function (results) {
      var ok = results.every(Boolean);
      if (!ok) {
        var bad = form.querySelector(".is-invalid");
        if (bad) bad.focus();
      }
      return ok;
    });
  }

  document.addEventListener(
    "blur",
    function (e) {
      var el = e.target;
      if (!el || !el.matches) return;
      if (!el.matches("input, select, textarea")) return;
      if (!el.closest("form")) return;
      validateOne(el);
    },
    true
  );

  document.addEventListener("input", function (e) {
    var el = e.target;
    if (!el || !el.matches) return;
    if (!el.matches("input, textarea, select")) return;
    if (!el.closest("form")) return;
    scheduleValidate(el);
  });

  document.addEventListener(
    "change",
    function (e) {
      var el = e.target;
      if (!el || !el.matches) return;
      if (!el.matches("select, input")) return;
      if (!el.closest("form")) return;
      validateOne(el);
    },
    true
  );

  // Capture submit → validate → re-submit so soft-nav / login can continue
  document.addEventListener(
    "submit",
    function (e) {
      var form = e.target;
      if (!(form instanceof HTMLFormElement)) return;
      if (form.dataset.noValidateAjax === "1") return;
      if (form.dataset.gmValidated === "1") {
        form.dataset.gmValidated = "0";
        return;
      }
      e.preventDefault();
      e.stopPropagation();
      validateForm(form).then(function (ok) {
        if (!ok) return;
        form.dataset.gmValidated = "1";
        if (typeof form.requestSubmit === "function") form.requestSubmit();
        else HTMLFormElement.prototype.submit.call(form);
      });
    },
    true
  );

  window.gmValidateForm = validateForm;
  window.gmValidateField = validateOne;
})();
