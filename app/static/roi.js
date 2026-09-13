/* Region selection on the stored evidence image.

   Vanilla, no library, nothing fetched. The one thing that matters here is the
   coordinate conversion: the box is drawn in DISPLAY pixels and must be posted
   in IMAGE pixels. The image is width-constrained by CSS, so the two differ by
   naturalWidth/clientWidth. Getting this wrong does not throw and does not look
   wrong -- it silently measures a different region and returns a different
   height. So the conversion happens in exactly one place, and the posted
   numbers are shown on the page where they can be read back. */
(function () {
  "use strict";
  var img = document.getElementById("roi-img");
  var canvas = document.getElementById("roi-canvas");
  if (!img || !canvas) { return; }

  var fx = document.getElementById("roi-x");
  var fy = document.getElementById("roi-y");
  var fw = document.getElementById("roi-w");
  var fh = document.getElementById("roi-h");

  var dragging = false;
  var x0 = 0, y0 = 0, x1 = 0, y1 = 0;

  function fit() {
    canvas.width = img.clientWidth;
    canvas.height = img.clientHeight;
    canvas.style.width = img.clientWidth + "px";
    canvas.style.height = img.clientHeight + "px";
    draw();
  }

  /* display px -> image px. Falls back to the server-rendered natural size if
     the browser has not decoded the image yet. */
  function factor() {
    var natural = img.naturalWidth || parseInt(img.dataset.naturalW, 10) || 0;
    var shown = img.clientWidth || 0;
    return (natural && shown) ? (natural / shown) : 1;
  }

  function draw() {
    var ctx = canvas.getContext("2d");
    ctx.clearRect(0, 0, canvas.width, canvas.height);
    if (x0 === x1 || y0 === y1) { return; }
    ctx.strokeStyle = "#0A1628";
    ctx.lineWidth = 2;
    ctx.strokeRect(Math.min(x0, x1), Math.min(y0, y1),
                   Math.abs(x1 - x0), Math.abs(y1 - y0));
  }

  function publish() {
    var k = factor();
    var dx = Math.min(x0, x1), dy = Math.min(y0, y1);
    var dw = Math.abs(x1 - x0), dh = Math.abs(y1 - y0);
    var natW = img.naturalWidth || parseInt(img.dataset.naturalW, 10) || 0;
    var natH = img.naturalHeight || parseInt(img.dataset.naturalH, 10) || 0;
    var x = Math.round(dx * k), y = Math.round(dy * k);
    var w = Math.round(dw * k), h = Math.round(dh * k);
    /* clamp inside the image so a drag that ends past the edge cannot post a
       region the server has to reject */
    if (natW) { x = Math.max(0, Math.min(x, natW - 1)); w = Math.min(w, natW - x); }
    if (natH) { y = Math.max(0, Math.min(y, natH - 1)); h = Math.min(h, natH - y); }
    fx.value = x; fy.value = y; fw.value = w; fh.value = h;
  }

  function at(ev) {
    var r = canvas.getBoundingClientRect();
    var p = (ev.touches && ev.touches[0]) ? ev.touches[0] : ev;
    return [p.clientX - r.left, p.clientY - r.top];
  }

  function start(ev) {
    dragging = true;
    var p = at(ev);
    x0 = x1 = p[0]; y0 = y1 = p[1];
    draw();
    ev.preventDefault();
  }

  function move(ev) {
    if (!dragging) { return; }
    var p = at(ev);
    x1 = p[0]; y1 = p[1];
    draw();
    publish();
    ev.preventDefault();
  }

  function end(ev) {
    if (!dragging) { return; }
    dragging = false;
    publish();
    if (ev.cancelable) { ev.preventDefault(); }
  }

  canvas.addEventListener("mousedown", start);
  window.addEventListener("mousemove", move);
  window.addEventListener("mouseup", end);
  canvas.addEventListener("touchstart", start);
  canvas.addEventListener("touchmove", move);
  canvas.addEventListener("touchend", end);

  window.addEventListener("resize", fit);
  if (img.complete) { fit(); } else { img.addEventListener("load", fit); }
})();

/* ---------------------------------------------------------------------------
   The in-flight "Measuring..." state.

   A scale-referenced measurement on a large capture takes seconds, and the
   browser shows the OLD page for the whole of that time. Silence reads as a
   hang. This marks the measurement as running the moment the request is sent,
   and the state clears because the response replaces the page -- it is driven
   by the actual request, never by a timer, and there is no setTimeout or
   setInterval anywhere in this file.

   Deliberately no percentage, no progress bar, no completion ring, and no
   spinner implying a known duration: the duration is not known, and a bar that
   pretends otherwise is the same dishonesty as a compliance score. Plain text
   and one static marker.
--------------------------------------------------------------------------- */
(function () {
  "use strict";
  var form = document.querySelector('form[action$="/measure"]');
  if (!form) { return; }
  var btn = document.getElementById("measure-submit");
  var panel = document.getElementById("measured-panel");
  var stage = document.querySelector('.pipeline .stage[data-stage="MEASURE"]');

  function markRunning() {
    if (btn) { btn.disabled = true; btn.textContent = "Measuring..."; }
    if (panel) {
      panel.innerHTML = "";
      var h = document.createElement("div");
      h.className = "m-headline";
      h.textContent = "Measuring...";
      var p = document.createElement("p");
      p.className = "m-body";
      p.textContent = "Measuring the operator-declared region against the "
        + "scale reference. This takes longer on a large capture.";
      panel.appendChild(h); panel.appendChild(p);
    }
    if (stage) {
      stage.className = "stage s-inflight";
      var vals = stage.querySelectorAll(".st-val, .st-note");
      for (var i = 0; i < vals.length; i++) { vals[i].remove(); }
      var v = document.createElement("div");
      v.className = "st-val";
      v.textContent = "measuring...";
      stage.appendChild(v);
    }
  }

  form.addEventListener("submit", function () { markRunning(); });

  /* Coming back via the bfcache would otherwise restore a page frozen in the
     running state for a request that finished long ago. */
  window.addEventListener("pageshow", function (ev) {
    if (ev.persisted && btn) { btn.disabled = false; btn.textContent = "Measure this region"; }
  });
})();
