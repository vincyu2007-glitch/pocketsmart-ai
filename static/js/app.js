/* PocketSmart AI - progressive enhancement only. Every page works without JS. */
(function () {
  "use strict";

  // --- mobile nav ---------------------------------------------------------
  var toggle = document.querySelector(".nav-toggle");
  var mobileNav = document.getElementById("mobile-nav");
  if (toggle && mobileNav) {
    toggle.addEventListener("click", function () {
      var open = toggle.getAttribute("aria-expanded") === "true";
      toggle.setAttribute("aria-expanded", String(!open));
      mobileNav.hidden = open;
    });
  }

  // --- submit loading state ----------------------------------------------
  document.querySelectorAll("form").forEach(function (form) {
    form.addEventListener("submit", function () {
      var button = form.querySelector('button[type="submit"]');
      if (!button || button.dataset.noLoading === "1") return;
      if (form.dataset.confirmBusy === "1") return;
      // Don't disable a form with a required file input the browser is about to
      // block, and never disable a submit button inside a form with invalid
      // fields (that would hide the validation message).
      if (!form.checkValidity()) return;
      button.classList.add("is-loading");
      button.setAttribute("aria-busy", "true");
      button.dataset.originalText = button.textContent;
      if (button.dataset.loadingText) button.textContent = button.dataset.loadingText;
    });
  });

  // --- destructive action confirmation ------------------------------------
  document.querySelectorAll("[data-confirm]").forEach(function (el) {
    el.addEventListener("click", function (event) {
      if (!window.confirm(el.getAttribute("data-confirm"))) event.preventDefault();
    });
  });

  // --- image picker: preview + drag & drop -------------------------------
  var input = document.getElementById("image");
  var zone = document.getElementById("dropzone");
  var preview = document.getElementById("preview");
  var img = document.getElementById("preview-img");
  var nameEl = document.getElementById("preview-name");
  var sizeEl = document.getElementById("preview-size");
  var MAX_MB = 8;

  function showFile(file) {
    if (!file) return;
    if (!/^image\//.test(file.type)) {
      alert("That file is not an image. Use JPEG, PNG, WEBP or GIF.");
      return;
    }
    if (file.size > MAX_MB * 1024 * 1024) {
      alert("That image is larger than " + MAX_MB + " MB.");
      return;
    }
    if (img.dataset.objectUrl) URL.revokeObjectURL(img.dataset.objectUrl);
    var url = URL.createObjectURL(file);
    img.dataset.objectUrl = url;
    img.src = url;
    nameEl.textContent = file.name;
    sizeEl.textContent = (file.size / 1024).toFixed(0) + " KB";
    preview.hidden = false;
  }

  if (input) {
    input.addEventListener("change", function () {
      showFile(input.files && input.files[0]);
    });
  }
  if (zone) {
    ["dragenter", "dragover"].forEach(function (type) {
      zone.addEventListener(type, function (event) {
        event.preventDefault();
        zone.classList.add("is-over");
      });
    });
    ["dragleave", "drop"].forEach(function (type) {
      zone.addEventListener(type, function (event) {
        event.preventDefault();
        zone.classList.remove("is-over");
      });
    });
    zone.addEventListener("drop", function (event) {
      var file = event.dataTransfer && event.dataTransfer.files[0];
      if (!file) return;
      if (!input.files || !input.files.length) {
        try {
          input.files = event.dataTransfer.files;
        } catch (err) {
          /* older browsers cannot assign to input.files - the click path still works */
        }
      }
      showFile(file);
    });
  }

  // --- budget quick-suggestions on the planner forms ---------------------
  document.querySelectorAll("input[name='budget']").forEach(function (budget) {
    var form = budget.closest("form");
    if (!form) return;
    var wrap = document.createElement("div");
    wrap.className = "pill-row";
    var plan = form.getAttribute("action") || "";
    var presets = plan.indexOf("party") > -1
      ? [[25000, "25k"], [75000, "75k"], [150000, "1.5L"], [400000, "4L"]]
      : plan.indexOf("jewelry") > -1
      ? [[25000, "25k"], [75000, "75k"], [150000, "1.5L"], [300000, "3L"]]
      : [[50000, "50k"], [150000, "1.5L"], [300000, "3L"], [700000, "7L"]];
    presets.forEach(function (preset) {
      var button = document.createElement("button");
      button.type = "button";
      button.className = "filter";
      button.textContent = "₹" + preset[1];
      button.addEventListener("click", function () {
        budget.value = preset[0];
        budget.dispatchEvent(new Event("input", { bubbles: true }));
      });
      wrap.appendChild(button);
    });
    var field = budget.closest(".field");
    if (field) field.appendChild(wrap);
  });
})();
