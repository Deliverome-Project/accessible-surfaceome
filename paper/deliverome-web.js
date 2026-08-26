/*
 * Deliverome paper — web-only progressive enhancement.
 *
 * Hover (or keyboard-focus) a citation and read the reference without
 * losing your place. Clicking still jumps, exactly as before: this is
 * layered on top of working anchors, so with JS disabled, on a touch
 * device, or if this file fails to load, every link behaves the way it
 * did before the script existed.
 *
 * Scoped to in-document reference anchors (href="#ref-…"), which
 * filters/citations.lua puts on every citation.
 */
(function () {
  "use strict";

  var SELECTOR = 'a[href^="#ref-"]';
  var SHOW_DELAY = 90;
  var HIDE_DELAY = 160;

  var links = document.querySelectorAll(SELECTOR);
  if (!links.length) return;

  var tip = document.createElement("div");
  tip.className = "ref-tooltip";
  tip.setAttribute("role", "tooltip");
  tip.hidden = true;
  document.body.appendChild(tip);

  var showTimer = null;
  var hideTimer = null;
  var current = null;

  /* The anchor `citations.lua` writes is an EMPTY <span id="ref-…">
   * sitting at the start of the reference. Its own textContent is
   * therefore "" — the text we want belongs to the enclosing block, so
   * walk up to it. */
  function referenceTextFor(href) {
    var id;
    try {
      id = decodeURIComponent(href.slice(1));
    } catch (e) {
      id = href.slice(1);
    }
    var target = document.getElementById(id);
    if (!target) return null;
    var block = target.closest("li, p, div");
    var text = (block || target).textContent || "";
    return text.replace(/\s+/g, " ").trim() || null;
  }

  function place(anchor) {
    var r = anchor.getBoundingClientRect();
    /* Measure first, then decide which side to sit on. */
    tip.style.left = "0px";
    tip.style.top = "0px";
    var t = tip.getBoundingClientRect();

    var margin = 8;
    var left = r.left + r.width / 2 - t.width / 2;
    left = Math.max(margin, Math.min(left, window.innerWidth - t.width - margin));

    /* Prefer above; flip below when there isn't room. */
    var top = r.top - t.height - margin;
    if (top < margin) top = r.bottom + margin;

    tip.style.left = Math.round(left + window.scrollX) + "px";
    tip.style.top = Math.round(top + window.scrollY) + "px";
  }

  function show(anchor) {
    var text = referenceTextFor(anchor.getAttribute("href"));
    if (!text) return;
    current = anchor;
    tip.textContent = text;
    tip.hidden = false;
    place(anchor);
    tip.classList.add("is-visible");
  }

  function hide() {
    tip.classList.remove("is-visible");
    tip.hidden = true;
    current = null;
  }

  function onEnter(e) {
    window.clearTimeout(hideTimer);
    window.clearTimeout(showTimer);
    var anchor = e.currentTarget;
    showTimer = window.setTimeout(function () {
      show(anchor);
    }, SHOW_DELAY);
  }

  function onLeave() {
    window.clearTimeout(showTimer);
    hideTimer = window.setTimeout(hide, HIDE_DELAY);
  }

  for (var i = 0; i < links.length; i++) {
    links[i].addEventListener("mouseenter", onEnter);
    links[i].addEventListener("mouseleave", onLeave);
    /* Keyboard parity: tabbing to a citation reveals the same panel. */
    links[i].addEventListener("focus", onEnter);
    links[i].addEventListener("blur", onLeave);
  }

  /* Keep the panel open while the pointer is inside it, so a long
   * reference can be read (and its DOI selected) without it vanishing. */
  tip.addEventListener("mouseenter", function () {
    window.clearTimeout(hideTimer);
  });
  tip.addEventListener("mouseleave", onLeave);

  document.addEventListener("keydown", function (e) {
    if (e.key === "Escape" && current) hide();
  });

  /* A tooltip anchored to viewport coordinates goes stale the moment
   * the page moves under it. */
  window.addEventListener(
    "scroll",
    function () {
      if (current) place(current);
    },
    { passive: true }
  );
  window.addEventListener("resize", function () {
    if (current) place(current);
  });
})();
