/* Automated extraction, and the review step that stands between a model's
   silence and an accusation.

   The hazard, stated once so nobody removes this by accident: a vision model
   returns null for a declaration it could not read. The officer ticks "I have
   examined the physical package" -- because they are about to, and the box is
   right there. Without review, that null becomes a recorded FAIL against a
   named packer on the strength of what a model failed to see.

   So: every machine-filled field is marked, every blank is marked explicitly
   (an empty box is indistinguishable from a field nobody looked at), and the
   coverage checkbox stays disabled until each of the six has been edited or
   confirmed. The server refuses the same combination independently; this is
   the explanation, not the guard.

   Vanilla, no library, nothing fetched at page load. */
(function () {
  "use strict";
  var btn = document.getElementById("extract-btn");
  var status = document.getElementById("extract-status");
  var fileInput = document.getElementById("image");
  var coverage = document.getElementById("operator_examined_package");
  var gate = document.getElementById("coverage-gate");
  var modelField = document.getElementById("vision_model");
  if (!btn || !fileInput || !modelField) { return; }

  var keys = [];
  var nodes = document.querySelectorAll(".decl-field");
  for (var i = 0; i < nodes.length; i++) { keys.push(nodes[i].dataset.key); }

  function el(k, suffix) { return document.getElementById(k + suffix); }

  function usedVision() { return !!modelField.value; }

  function isReviewed(k) { return el(k, "__reviewed").value === "1"; }

  function markReviewed(k) {
    el(k, "__reviewed").value = "1";
    var mark = el(k, "__mark");
    mark.textContent = "confirmed by you";
    mark.className = "decl-mark reviewed";
    mark.hidden = false;
    var c = el(k, "__confirm");
    if (c) { c.hidden = true; }
    refreshGate();
  }

  /* A field the officer edits loses the machine mark: that edit is the signal
     that a human stands behind the value. */
  function wire(k) {
    var input = document.getElementById(k);
    input.addEventListener("input", function () { markReviewed(k); });
    var c = el(k, "__confirm");
    if (c) { c.addEventListener("click", function () { markReviewed(k); }); }
  }
  for (var j = 0; j < keys.length; j++) { wire(keys[j]); }

  function showMachine(k, value, confirmed) {
    var input = document.getElementById(k);
    var mark = el(k, "__mark");
    var confirm = el(k, "__confirm");
    input.value = value === null ? "" : value;
    el(k, "__machine").value = value === null ? "" : value;
    el(k, "__reviewed").value = "";
    el(k, "__ocr").value = confirmed === true ? "1"
                         : (confirmed === false ? "0" : "");
    if (value === null) {
      /* NOT an empty box. An empty box is indistinguishable from a field
         nobody looked at, which is the entire problem. */
      mark.textContent = "not found in image";
      mark.className = "decl-mark absent";
    } else if (confirmed === false) {
      /* The value exists but no OCR engine on this image saw it. That is
         consistent with an invented value AND with OCR simply being worse than
         the model on glossy or curved packaging, which is the normal condition
         of these packets. It is NOT evidence the model lied and must never be
         labelled as such. The declaration layer downgrades it to
         CANNOT_DETERMINE; the officer confirms it on the package. */
      mark.textContent = "reported by the model but not found by OCR — "
        + "confirm on the package";
      mark.className = "decl-mark unconfirmed";
    } else {
      mark.textContent = "read from image — unconfirmed";
      mark.className = "decl-mark machine";
    }
    mark.hidden = false;
    input.classList.add("machine-filled");
    if (confirm) { confirm.hidden = false; }
  }

  function refreshGate() {
    if (!coverage) { return; }
    if (!usedVision()) { coverage.disabled = false; gate.hidden = true; return; }
    var pending = 0;
    for (var i = 0; i < keys.length; i++) { if (!isReviewed(keys[i])) { pending++; } }
    if (pending > 0) {
      coverage.checked = false;
      coverage.disabled = true;
      gate.hidden = false;
    } else {
      coverage.disabled = false;
      gate.hidden = true;
    }
  }

  btn.addEventListener("click", function () {
    if (!fileInput.files || !fileInput.files.length) {
      status.textContent = "Choose an image first.";
      return;
    }
    var body = new FormData();
    body.append("image", fileInput.files[0]);
    btn.disabled = true;
    btn.textContent = "Reading...";
    status.textContent = "Reading the declarations from this image.";

    fetch("/extract-declarations", {method: "POST", body: body})
      .then(function (r) { return r.json().catch(function () {
        return {ok: false, error: "The extraction service could not be used. "
                + "Enter the declarations manually."}; }); })
      .then(function (d) {
        if (!d || !d.ok) {
          /* Every failure leaves the manual path usable and the upload intact.
             The image is untouched; the officer types the six fields. */
          status.textContent = (d && d.error) || "Extraction failed. Enter the "
            + "declarations manually.";
          return;
        }
        /* The bare model id. service.py owns the "vision:" prefix. */
        modelField.value = d.model;
        for (var i = 0; i < keys.length; i++) {
          var k = keys[i];
          showMachine(k, Object.prototype.hasOwnProperty.call(d.values, k)
                         ? d.values[k] : null,
                      (d.confirmed || {})[k]);
        }
        status.textContent = "Read by " + d.model
          + ". Review each declaration below; nothing is recorded until you do.";
        refreshGate();
      })
      .catch(function () {
        status.textContent = "Could not reach the extraction service. Enter "
          + "the declarations manually.";
      })
      .then(function () {
        btn.disabled = false;
        btn.textContent = "Read declarations from image";
      });
  });

  /* Restore the marks after a validation error re-renders the form. */
  (function restore() {
    if (!usedVision()) { refreshGate(); return; }
    for (var i = 0; i < keys.length; i++) {
      var k = keys[i];
      if (isReviewed(k)) {
        var mark = el(k, "__mark");
        mark.textContent = "confirmed by you";
        mark.className = "decl-mark reviewed";
        mark.hidden = false;
      } else {
        showMachine(k, el(k, "__machine").value || null,
                    {"1": true, "0": false}[el(k, "__ocr").value]);
      }
    }
    refreshGate();
  })();
})();
