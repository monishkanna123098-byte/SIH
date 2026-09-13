/* Landing page behaviour. Vanilla, no library, nothing fetched.

   Three jobs: reveal sections as they enter the viewport, give the navbar a
   scrolled state, and draw a slow measurement grid behind the page. All three
   are inert under prefers-reduced-motion -- the content is fully visible, the
   canvas is not drawn at all, and no rAF loop runs.

   There is no scroll event listener anywhere in this file. The navbar state
   comes from an IntersectionObserver on a sentinel, so nothing runs on every
   scroll frame. */
(function () {
  "use strict";

  var reduce = window.matchMedia
    && window.matchMedia("(prefers-reduced-motion: reduce)").matches;

  /* ---- 1. scroll reveal ------------------------------------------------ */
  var targets = document.querySelectorAll(".lp-reveal");

  if (reduce || !("IntersectionObserver" in window)) {
    for (var i = 0; i < targets.length; i++) {
      targets[i].classList.add("is-visible");
    }
  } else {
    var revealer = new IntersectionObserver(function (entries) {
      for (var j = 0; j < entries.length; j++) {
        if (entries[j].isIntersecting) {
          entries[j].target.classList.add("is-visible");
          revealer.unobserve(entries[j].target);   /* reveal once, then stop */
        }
      }
    }, {rootMargin: "0px 0px -10% 0px", threshold: 0.08});
    for (var k = 0; k < targets.length; k++) { revealer.observe(targets[k]); }
  }

  /* ---- 2. navbar scrolled state --------------------------------------- */
  var nav = document.getElementById("lp-nav");
  if (nav && "IntersectionObserver" in window) {
    var sentinel = document.createElement("div");
    sentinel.setAttribute("aria-hidden", "true");
    sentinel.style.cssText = "position:absolute;top:0;height:1px;width:1px;";
    document.body.insertBefore(sentinel, document.body.firstChild);
    new IntersectionObserver(function (e) {
      nav.classList.toggle("is-stuck", !e[0].isIntersecting);
    }).observe(sentinel);
  }

  /* ---- 3. mobile navigation ------------------------------------------- */
  var burger = document.getElementById("lp-burger");
  var menu = document.getElementById("lp-menu");
  if (burger && menu) {
    burger.addEventListener("click", function () {
      var open = menu.classList.toggle("is-open");
      burger.setAttribute("aria-expanded", open ? "true" : "false");
      burger.setAttribute("aria-label", open ? "Close navigation" : "Open navigation");
    });
    menu.addEventListener("click", function (ev) {
      if (ev.target.tagName === "A") {
        menu.classList.remove("is-open");
        burger.setAttribute("aria-expanded", "false");
      }
    });
    document.addEventListener("keydown", function (ev) {
      if (ev.key === "Escape" && menu.classList.contains("is-open")) {
        menu.classList.remove("is-open");
        burger.setAttribute("aria-expanded", "false");
        burger.focus();
      }
    });
  }

  /* ---- 4. flip cards --------------------------------------------------- */
  /* CSS handles hover. This adds click and keyboard, so the back face is
     reachable without a pointer -- the cards are <button>s, so Enter and
     Space already activate them. */
  var flips = document.querySelectorAll(".lp-flip");
  for (var f = 0; f < flips.length; f++) {
    flips[f].addEventListener("click", function () {
      var on = this.getAttribute("aria-expanded") === "true";
      this.setAttribute("aria-expanded", on ? "false" : "true");
    });
  }

  /* ---- 5. the background: a slow measurement grid ---------------------- */
  /* Deliberately not a particle field or a 3D scene. It is a drifting rule
     with tick marks -- on theme for an instrument, and about 60 lines instead
     of 600KB of library. Drawn once per frame at device resolution, paused
     whenever the tab is hidden or the page is scrolled past it. */
  var canvas = document.getElementById("lp-canvas");
  if (!canvas || reduce || !canvas.getContext) { return; }
  var ctx = canvas.getContext("2d");
  var w = 0, h = 0, dpr = 1, raf = 0, t = 0, running = false;

  function size() {
    dpr = Math.min(window.devicePixelRatio || 1, 2);
    w = canvas.clientWidth; h = canvas.clientHeight;
    canvas.width = Math.floor(w * dpr);
    canvas.height = Math.floor(h * dpr);
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
  }

  function draw() {
    ctx.clearRect(0, 0, w, h);
    var step = 46, major = 5, drift = (t * 0.0016) % step;

    for (var x = -step; x < w + step; x += step) {
      var gx = x + drift, isMajor = Math.round(x / step) % major === 0;
      ctx.beginPath();
      ctx.moveTo(gx, 0); ctx.lineTo(gx, h);
      ctx.strokeStyle = isMajor ? "rgba(10,22,40,.070)" : "rgba(10,22,40,.032)";
      ctx.lineWidth = 1; ctx.stroke();
      if (isMajor) {                                  /* a caliper tick */
        ctx.beginPath();
        ctx.moveTo(gx - 4, 26); ctx.lineTo(gx + 4, 26);
        ctx.strokeStyle = "rgba(10,22,40,.10)";
        ctx.stroke();
      }
    }
    for (var y = -step; y < h + step; y += step) {
      var gy = y + drift * 0.55;
      ctx.beginPath();
      ctx.moveTo(0, gy); ctx.lineTo(w, gy);
      ctx.strokeStyle = "rgba(10,22,40,.026)";
      ctx.stroke();
    }
    t += 16;
    raf = window.requestAnimationFrame(draw);
  }

  function start() { if (!running) { running = true; draw(); } }
  function stop() { running = false; window.cancelAnimationFrame(raf); }

  size();
  start();

  var resizePending = false;
  window.addEventListener("resize", function () {
    if (resizePending) { return; }
    resizePending = true;
    window.requestAnimationFrame(function () { size(); resizePending = false; });
  });

  document.addEventListener("visibilitychange", function () {
    if (document.hidden) { stop(); } else { start(); }
  });

  /* Stop drawing once the hero has scrolled away -- nothing is visible then. */
  if ("IntersectionObserver" in window) {
    var hero = document.querySelector(".lp-hero");
    if (hero) {
      new IntersectionObserver(function (e) {
        if (e[0].isIntersecting) { start(); } else { stop(); }
      }, {rootMargin: "200px"}).observe(hero);
    }
  }
})();
