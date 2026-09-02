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
  function referenceNodeFor(href) {
    var id;
    try {
      id = decodeURIComponent(href.slice(1));
    } catch (e) {
      id = href.slice(1);
    }
    var target = document.getElementById(id);
    if (!target) return null;
    return target.closest("li, p, div") || target;
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
    var node = referenceNodeFor(anchor.getAttribute("href"));
    if (!node) return;
    current = anchor;
    /* Clone the reference's MARKUP, not just its text: the DOI is an
     * <a> inside it, and textContent flattened it to a dead string —
     * the one thing a reader most wants to click from a citation
     * preview. The panel already allows the pointer inside it so the
     * link is reachable. */
    tip.innerHTML = "";
    var clone = node.cloneNode(true);
    /* Drop the invisible anchor span the citation filter injects. */
    var stray = clone.querySelector('span[id^="ref-"]');
    if (stray && stray.parentNode) stray.parentNode.removeChild(stray);
    while (clone.firstChild) tip.appendChild(clone.firstChild);
    if (!tip.textContent.trim()) return;
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

/*
 * Figure lightbox — click any figure to open it large, with its
 * caption. Same progressive-enhancement contract as the citation
 * panel: without this script the figures are still full-width images
 * in the flow, they just don't zoom.
 */
(function () {
  "use strict";

  var blocks = document.querySelectorAll(".figure-block");
  if (!blocks.length) return;

  var overlay = document.createElement("div");
  overlay.className = "figure-lightbox";
  overlay.setAttribute("role", "dialog");
  overlay.setAttribute("aria-modal", "true");
  overlay.hidden = true;
  overlay.innerHTML =
    '<button class="figure-lightbox__close" type="button" aria-label="Close figure">&times;</button>' +
    '<button class="figure-lightbox__nav figure-lightbox__prev" type="button" aria-label="Previous figure">&#8249;</button>' +
    '<button class="figure-lightbox__nav figure-lightbox__next" type="button" aria-label="Next figure">&#8250;</button>' +
    '<figure class="figure-lightbox__inner">' +
    '<img alt="" />' +
    '<figcaption></figcaption>' +
    '<p class="figure-lightbox__counter"></p>' +
    "</figure>";
  document.body.appendChild(overlay);

  var imgEl = overlay.querySelector("img");
  var capEl = overlay.querySelector("figcaption");
  var closeBtn = overlay.querySelector(".figure-lightbox__close");
  var prevBtn = overlay.querySelector(".figure-lightbox__prev");
  var nextBtn = overlay.querySelector(".figure-lightbox__next");
  var counter = overlay.querySelector(".figure-lightbox__counter");
  var lastFocused = null;
  /* Document order == the order figures are referenced in the text,
   * because each figure sits where it is first discussed. */
  var order = Array.prototype.slice.call(blocks);
  var index = -1;

  function open(block) {
    var source = block.querySelector("img");
    if (!source) return;
    var caption = block.querySelector("h5");
    index = order.indexOf(block);
    if (counter) {
      counter.textContent =
        index >= 0 ? index + 1 + " of " + order.length : "";
    }
    if (prevBtn) prevBtn.disabled = index <= 0;
    if (nextBtn) nextBtn.disabled = index < 0 || index >= order.length - 1;
    if (lastFocused === null) lastFocused = document.activeElement;
    imgEl.setAttribute("src", source.getAttribute("src"));
    imgEl.setAttribute("alt", source.getAttribute("alt") || "");
    capEl.textContent = caption ? caption.textContent.trim() : "";
    overlay.hidden = false;
    /* Force a reflow so the opacity transition has a start state,
     * then flip the class SYNCHRONOUSLY. The obvious
     * requestAnimationFrame version is wrong: rAF is paused in a
     * background or hidden tab, so the overlay would un-hide with
     * opacity 0 and never become visible — an invisible full-screen
     * layer swallowing every click. */
    void overlay.offsetWidth;
    overlay.classList.add("is-open");
    document.body.style.overflow = "hidden";
    closeBtn.focus();
  }

  function close() {
    overlay.classList.remove("is-open");
    overlay.hidden = true;
    document.body.style.overflow = "";
    imgEl.removeAttribute("src");
    if (lastFocused && lastFocused.focus) lastFocused.focus();
    lastFocused = null;
    index = -1;
  }

  function step(delta) {
    var next = index + delta;
    if (next < 0 || next >= order.length) return;
    open(order[next]);
  }

  for (var i = 0; i < blocks.length; i++) {
    (function (block) {
      var img = block.querySelector("img");
      if (!img) return;
      img.classList.add("is-zoomable");
      /* The image itself is the hit target, not the whole block — a
       * click on the caption should still be able to select its text. */
      img.addEventListener("click", function () {
        open(block);
      });
      img.setAttribute("tabindex", "0");
      img.setAttribute("role", "button");
      img.setAttribute("aria-label", "Open figure larger");
      img.addEventListener("keydown", function (e) {
        if (e.key === "Enter" || e.key === " ") {
          e.preventDefault();
          open(block);
        }
      });
    })(blocks[i]);
  }

  /* A body-text "Figure 3" opens the figure HERE rather than scrolling
   * away to it. On screen that's the better affordance: you check the
   * figure and carry on reading, instead of losing your place and
   * having to scroll back. The PDF keeps the jump, which is the only
   * thing a page-based format can do.
   *
   * Delegated, and it leaves the href intact — without JS, or on a
   * modifier-click / middle-click, the link still navigates to the
   * anchor exactly as before. */
  document.addEventListener("click", function (e) {
    if (e.defaultPrevented) return;
    if (e.metaKey || e.ctrlKey || e.shiftKey || e.altKey || e.button !== 0) return;
    var a = e.target.closest && e.target.closest("a[href^='#']");
    if (!a) return;
    if (a.closest(".figure-lightbox")) return;
    var href = a.getAttribute("href") || "";
    if (!/^#(figure|supplementary-figure|appendix-figure)-/.test(href)) return;
    var id;
    try {
      id = decodeURIComponent(href.slice(1));
    } catch (err) {
      id = href.slice(1);
    }
    var target = document.getElementById(id);
    if (!target) return;
    var block = target.closest(".figure-block");
    if (!block) return;          // no block to show — let it jump
    e.preventDefault();
    open(block);
  });

  closeBtn.addEventListener("click", close);
  if (prevBtn) {
    prevBtn.addEventListener("click", function (e) {
      e.stopPropagation();
      step(-1);
    });
  }
  if (nextBtn) {
    nextBtn.addEventListener("click", function (e) {
      e.stopPropagation();
      step(1);
    });
  }

  /* Any click dismisses — backdrop OR the figure itself. Requiring the
   * click to land exactly on the backdrop meant a click on the image
   * did nothing, so getting out of a large figure took two goes. The
   * caption is excluded so its text stays selectable. */
  overlay.addEventListener("click", function (e) {
    if (e.target.closest(".figure-lightbox__nav")) return;
    if (e.target.closest("figcaption")) return;
    close();
  });

  document.addEventListener("keydown", function (e) {
    if (overlay.hidden) return;
    if (e.key === "Escape") close();
    else if (e.key === "ArrowRight") step(1);
    else if (e.key === "ArrowLeft") step(-1);
  });
})();

/*
 * Contents rail — active-section tracking.
 *
 * Highlights the entry for whatever section you're currently reading.
 * Uses IntersectionObserver against the heading elements rather than a
 * scroll handler doing getBoundingClientRect on every frame.
 *
 * The "active" heading is the LAST one to have crossed the top of the
 * viewport, which is not the same as "the topmost intersecting
 * element" — while you read the middle of a long section, no heading
 * is on screen at all, and a naive intersection test would leave the
 * rail blank or, worse, jump to the next section early.
 */
(function () {
  "use strict";

  var toc = document.getElementById("TOC");
  if (!toc || !("IntersectionObserver" in window)) return;

  var links = toc.querySelectorAll('a[href^="#"]');
  if (!links.length) return;

  var byId = {};
  var targets = [];
  for (var i = 0; i < links.length; i++) {
    var id;
    try {
      id = decodeURIComponent(links[i].getAttribute("href").slice(1));
    } catch (e) {
      id = links[i].getAttribute("href").slice(1);
    }
    var el = document.getElementById(id);
    if (!el) continue;
    byId[id] = links[i];
    targets.push(el);
  }
  if (!targets.length) return;

  var activeLink = null;
  function setActive(link) {
    if (link === activeLink) return;
    if (activeLink) activeLink.classList.remove("is-active");
    if (link) link.classList.add("is-active");
    activeLink = link;
  }

  /* Track how far each heading is from the top so we can pick the last
   * one above the fold, rather than only the ones currently visible. */
  function recompute() {
    var best = null;
    var bestTop = -Infinity;
    for (var i = 0; i < targets.length; i++) {
      var top = targets[i].getBoundingClientRect().top;
      /* 120px grace so a heading just scrolled past still counts. */
      if (top <= 120 && top > bestTop) {
        bestTop = top;
        best = targets[i];
      }
    }
    if (!best) best = targets[0];
    setActive(byId[best.id] || null);
  }

  var ticking = false;
  var observer = new IntersectionObserver(
    function () {
      if (ticking) return;
      ticking = true;
      requestAnimationFrame(function () {
        recompute();
        ticking = false;
      });
    },
    { rootMargin: "-100px 0px -70% 0px", threshold: [0, 1] }
  );
  for (var j = 0; j < targets.length; j++) observer.observe(targets[j]);

  window.addEventListener(
    "scroll",
    function () {
      if (ticking) return;
      ticking = true;
      requestAnimationFrame(function () {
        recompute();
        ticking = false;
      });
    },
    { passive: true }
  );

  recompute();
})();
