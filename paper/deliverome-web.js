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
  imgEl.setAttribute("tabindex", "0");
  imgEl.setAttribute("role", "button");
  imgEl.setAttribute("aria-label", "Zoom figure");
  imgEl.addEventListener("keydown", function (e) {
    if (e.key === "Enter" || e.key === " ") {
      e.preventDefault();
      overlay.classList.toggle("is-zoomed");
    }
  });
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
    /* Carry the caption's rich markup, not just its text: the run-in
     * "Figure N. Title." is a <strong> and the caption ends with a
     * "Figure data and script." link to the figure's gist. Flattening
     * to textContent dropped both the bold and the (clickable) link;
     * innerHTML keeps them. The caption never carries an id (figures.lua
     * moves it to the image anchor) so the copy raises no duplicate id.
     * The link stays clickable because the click-to-dismiss handler
     * already excludes anything inside <figcaption>. */
    capEl.innerHTML = caption ? caption.innerHTML : "";
    overlay.hidden = false;
    /* Force a reflow so the opacity transition has a start state,
     * then flip the class SYNCHRONOUSLY. The obvious
     * requestAnimationFrame version is wrong: rAF is paused in a
     * background or hidden tab, so the overlay would un-hide with
     * opacity 0 and never become visible — an invisible full-screen
     * layer swallowing every click. */
    void overlay.offsetWidth;
    overlay.classList.add("is-open");
    /* A new figure always starts fitted, never inheriting the previous
     * one's zoom — stepping through figures should be comparable. */
    overlay.classList.remove("is-zoomed");
    document.body.style.overflow = "hidden";
    closeBtn.focus();
  }

  function close() {
    overlay.classList.remove("is-open");
    overlay.classList.remove("is-zoomed");
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
    /* The figure itself toggles zoom rather than dismissing. Fitting a
     * figure above its legend costs it half the screen; this gives that
     * space back for a look at the detail, then returns. Everything
     * else in the overlay keeps dismissing as before. */
    if (e.target === imgEl) {
      overlay.classList.toggle("is-zoomed");
      return;
    }
    /* An in-page caption link (e.g. "Methods", href="#…") has to take the
     * reader to that section — but the overlay is a fixed layer sitting on
     * top, so the jump is invisible while it's open. Close first, then let
     * the anchor navigate. External links (target=_blank) open a new tab
     * and leave the figure up, so they keep the caption exception below. */
    if (e.target.closest("figcaption a[href^='#']")) {
      close();
      return;
    }
    if (e.target.closest("figcaption")) return;
    close();
  });

  document.addEventListener("keydown", function (e) {
    if (overlay.hidden) return;
    if (e.key === "Escape") {
      /* Step back out of zoom first: Escape should undo the last thing
       * the reader did, not two things at once. */
      if (overlay.classList.contains("is-zoomed")) {
        overlay.classList.remove("is-zoomed");
      } else {
        close();
      }
    }
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

/*
 * Reader comments — a progressive-enhancement island at the bottom of
 * the paper (markup emitted by build.py). Posts to the shared feedback
 * Worker (Resend-backed, author-moderated) under a paper-only "gene"
 * sentinel, so a comment here can never surface on a surfaceome gene
 * page. Approved comments are fetched and shown above the form; a reader
 * can opt in to having theirs posted publicly on this page after review.
 */
(function () {
  "use strict";

  var section = document.querySelector(".paper-comments");
  if (!section) return;

  var apiBase = (section.getAttribute("data-api-base") || "").replace(/\/+$/, "");
  var gene = section.getAttribute("data-gene") || "";
  var siteKey = section.getAttribute("data-turnstile-key") || "";
  if (!apiBase || !gene) return;

  var form = section.querySelector(".paper-comments__form");
  var listEl = section.querySelector(".paper-comments__list");
  var statusEl = section.querySelector(".paper-comments__status");
  var turnstileSlot = section.querySelector(".paper-comments__turnstile");
  var submitBtn = section.querySelector(".paper-comments__submit");
  var token = "";
  var widgetId = null;

  function setStatus(msg, kind) {
    statusEl.textContent = msg || "";
    statusEl.className = "paper-comments__status" + (kind ? " is-" + kind : "");
  }

  /* Approved public comments. Rendered with textContent throughout — the
   * bodies are reader-supplied, so never touch innerHTML here. */
  function renderNotes(notes) {
    listEl.textContent = "";
    if (!notes || !notes.length) return;
    for (var i = 0; i < notes.length; i++) {
      var n = notes[i];
      var li = document.createElement("li");
      li.className = "paper-comments__note";
      var bodyEl = document.createElement("p");
      bodyEl.className = "paper-comments__note-body";
      bodyEl.textContent = n.comment || "";
      var whoEl = document.createElement("p");
      whoEl.className = "paper-comments__note-by";
      whoEl.textContent = "— " + (n.submitter_name || "Anonymous");
      li.appendChild(bodyEl);
      li.appendChild(whoEl);
      listEl.appendChild(li);
    }
  }

  /* Approved comments are fetched live on load — never baked into the page.
   * Two robustness wrinkles the naive one-shot fetch got wrong:
   *   1. D1 read-replica lag. Right after a comment is approved, the write
   *      may not have reached every region's read replica, so the first
   *      fetch can come back empty. Retry a bounded few times WHILE the list
   *      is still empty, so a freshly-approved note appears without a manual
   *      reload. A genuinely comment-free page just does a few cheap GETs
   *      and stops (retries only fire while nothing has rendered yet).
   *   2. A note approved while the tab sits open won't show until reload —
   *      so also refetch when the tab regains focus.
   * A transient empty response (replica lag on a later refetch) must never
   * blank notes we've already shown: once we've rendered a non-empty list we
   * only ever replace it with another non-empty list. */
  var renderedNonEmpty = false;

  function applyNotes(notes) {
    if (notes && notes.length) {
      renderNotes(notes);
      renderedNonEmpty = true;
    } else if (!renderedNonEmpty) {
      renderNotes([]);
    }
  }

  function loadNotes(retriesOnEmpty) {
    fetch(apiBase + "/v1/feedback/public?gene=" + encodeURIComponent(gene), {
      headers: { accept: "application/json" },
      cache: "no-store"
    })
      .then(function (r) { return r.ok ? r.json() : null; })
      .then(function (j) {
        var notes = j && j.notes ? j.notes : [];
        applyNotes(notes);
        if (!notes.length && !renderedNonEmpty && retriesOnEmpty > 0) {
          setTimeout(function () { loadNotes(retriesOnEmpty - 1); }, 2000);
        }
      })
      .catch(function () {});
  }

  /* Turnstile: load the loader script once, then render explicitly. */
  function renderTurnstile() {
    if (!siteKey || !turnstileSlot || !window.turnstile) return;
    try {
      widgetId = window.turnstile.render(turnstileSlot, {
        sitekey: siteKey,
        callback: function (t) { token = t; },
        "error-callback": function () { token = ""; },
        "expired-callback": function () { token = ""; }
      });
    } catch (e) {
      /* widget already rendered / bad key — leave the form usable */
    }
  }

  function loadTurnstile() {
    if (!siteKey) return;
    if (window.turnstile) { renderTurnstile(); return; }
    if (!document.getElementById("cf-turnstile-script")) {
      var s = document.createElement("script");
      s.id = "cf-turnstile-script";
      s.src = "https://challenges.cloudflare.com/turnstile/v0/api.js";
      s.async = true;
      s.defer = true;
      document.head.appendChild(s);
    }
    var tries = 0;
    var iv = setInterval(function () {
      if (window.turnstile) { clearInterval(iv); renderTurnstile(); }
      else if (++tries > 100) { clearInterval(iv); }
    }, 100);
  }

  function resetTurnstile() {
    token = "";
    if (widgetId !== null && window.turnstile) {
      try { window.turnstile.reset(widgetId); } catch (e) {}
    }
  }

  form.addEventListener("submit", function (e) {
    e.preventDefault();
    var name = form.elements["name"].value.trim();
    var email = form.elements["email"].value.trim();
    var comment = form.elements["comment"].value.trim();
    var isPublic = form.elements["public"].checked;
    if (!name) return setStatus("Please enter your name.", "error");
    if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email))
      return setStatus("Please enter a valid e-mail.", "error");
    if (!comment) return setStatus("Please write a comment.", "error");
    if (siteKey && !token)
      return setStatus("Please complete the verification below.", "error");

    setStatus("Sending…", "pending");
    submitBtn.disabled = true;

    fetch(apiBase + "/v1/feedback/submit", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        gene: gene,
        name: name,
        email: email,
        subject: "Comment on the accessible human surfaceome paper",
        comment: comment,
        public_requested: isPublic,
        referrer: window.location.href,
        user_agent: navigator.userAgent,
        site_version: "paper-web",
        turnstile_token: token
      })
    })
      .then(function (r) {
        return r.json().catch(function () { return {}; }).then(function (j) {
          return { ok: r.ok, status: r.status, j: j };
        });
      })
      .then(function (res) {
        submitBtn.disabled = false;
        if (res.ok) {
          form.reset();
          resetTurnstile();
          setStatus(
            isPublic
              ? "Thanks — sent to the authors. It'll appear here once approved."
              : "Thanks — your comment was sent to the authors.",
            "ok"
          );
          return;
        }
        var err = (res.j && res.j.error) || ("Server returned " + res.status + ".");
        if (err === "rate_limited") {
          err = "You've sent a few already — please try again later.";
        } else if (err === "turnstile_failed") {
          resetTurnstile();
          err = "Verification failed — please complete the checkbox again.";
        }
        setStatus(err, "error");
      })
      .catch(function () {
        submitBtn.disabled = false;
        setStatus("Network error — please try again.", "error");
      });
  });

  loadNotes(3); // initial load + up to 3 empty-retries (~6s replica-lag window)
  document.addEventListener("visibilitychange", function () {
    if (document.visibilityState === "visible") loadNotes(0);
  });
  loadTurnstile();
})();

/*
 * Scroll reveal.
 *
 * The `reveal` classes are stamped into the markup by paper/web_assets.py
 * and the `js-reveal` gate is set by an inline <head> script, both before
 * this file runs — see REVEAL_BOOTSTRAP_SCRIPT for why that ordering is
 * load-bearing. What is left for here is the part that needs a viewport:
 * deciding what is already on screen, arming the transition afterwards so
 * the opening screen doesn't animate, and un-hiding the rest on approach.
 *
 * If this file never loads, the gate is still set but nothing ever adds
 * `is-visible` — which is why the gate is conditional on
 * IntersectionObserver, the same capability this observer needs. A
 * browser without it never hides anything in the first place.
 */
(function () {
  "use strict";

  var root = document.documentElement;
  if (!root.classList.contains("js-reveal")) return;

  var targets = document.querySelectorAll(".paper-root .reveal");

  function show(el) {
    el.classList.add("is-visible");
  }

  /* Anything already on screen is shown BEFORE arming, so it transitions
   * from nothing and simply exists at first paint. Everything after this
   * point animates. */
  var i;
  for (i = 0; i < targets.length; i++) {
    var box = targets[i].getBoundingClientRect();
    if (box.top < window.innerHeight && box.bottom > 0) show(targets[i]);
  }

  if (!("IntersectionObserver" in window)) {
    /* Can't happen while the gate checks the same thing, but if the gate
     * ever moves, fail to the readable state rather than a blank page. */
    for (i = 0; i < targets.length; i++) show(targets[i]);
    return;
  }

  /* Commit the values above BEFORE arming, by forcing a style flush.
   * Reading offsetWidth makes the browser resolve layout now, so the
   * elements just marked visible settle at opacity 1 with no transition
   * attached and simply exist at first paint.
   *
   * A requestAnimationFrame here is wrong twice over — the same trap the
   * lightbox hits above. It is paused in a background tab, so a paper
   * cmd-clicked into one would never arm; and it races the observer
   * below, which can deliver its first batch before the frame callback
   * runs, leaving the first block under the fold to snap in unarmed. A
   * synchronous flush has neither problem. */
  void document.body.offsetWidth;
  root.classList.add("reveal-armed");

  /* Find-in-page sees text that is still at opacity 0, so a reader
   * searching the paper could be scrolled to what looks like a blank
   * stretch. Rather than keeping prose out of the reveal — which is
   * what makes the whole effect visible — drop the reveal entirely the
   * moment anyone starts searching. Best-effort: the browser may claim
   * the shortcut first in some configurations, and nothing breaks if
   * it does; this only ever makes MORE text visible. */
  function revealEverything() {
    for (var k = 0; k < targets.length; k++) show(targets[k]);
  }
  document.addEventListener("keydown", function (e) {
    if ((e.metaKey || e.ctrlKey) && (e.key === "f" || e.key === "F")) {
      revealEverything();
    }
  });
  /* Chrome fires this on a hidden element it is about to scroll a
   * find-in-page match to. Where supported it is exact, and it also
   * covers "scroll to text fragment" links. */
  document.addEventListener("beforematch", revealEverything, true);

  var observer = new IntersectionObserver(
    function (entries) {
      for (var j = 0; j < entries.length; j++) {
        if (!entries[j].isIntersecting) continue;
        show(entries[j].target);
        /* Once revealed, stay revealed: re-animating on the way back up
         * turns a page you are scanning into a flickering one. */
        observer.unobserve(entries[j].target);
      }
    },
    /* Hold the reveal until the block is ~18% of the viewport up from
     * the bottom edge, rather than firing as it clips the edge.
     *
     * This is the difference between motion you see and motion you
     * only infer. Triggered at the edge, a block has finished arriving
     * while it is still in the last few percent of the screen — below
     * where anyone is looking — so the page just seems to have been
     * that way already. Held slightly, the same animation plays where
     * the eye actually is. */
    { rootMargin: "0px 0px -18% 0px", threshold: 0 }
  );

  for (i = 0; i < targets.length; i++) {
    if (!targets[i].classList.contains("is-visible")) observer.observe(targets[i]);
  }
})();

/*
 * Contents rail — dock on scroll.
 *
 * The rail is fixed-position, so without this it sits beside the title
 * band offering navigation for a paper the reader hasn't begun. Fade it
 * in once they're past the header. Purely cosmetic: with this script
 * absent the stylesheet leaves the rail permanently visible, which is
 * where it was before.
 */
(function () {
  "use strict";

  var toc = document.getElementById("TOC");
  var header = document.querySelector(".paper-header");
  if (!toc || !header || !("IntersectionObserver" in window)) return;

  var observer = new IntersectionObserver(
    function (entries) {
      /* Docked once the title band has left the viewport entirely. */
      toc.classList.toggle("is-docked", !entries[0].isIntersecting);
    },
    /* No rootMargin, deliberately. A negative TOP inset shrinks the
     * observer root down past the header, so at the top of the page —
     * the one position where the rail must be hidden — the header reads
     * as "not intersecting" and the rail docks immediately, inverting
     * the whole behaviour. Plain viewport intersection is both simpler
     * and correct: visible while any of the title band is on screen. */
    { threshold: 0 }
  );
  observer.observe(header);
})();

/*
 * Post-jump highlight.
 *
 * After a smooth scroll the page settles a beat before the eye catches
 * up, and in a wall of near-identical reference lines "which one did I
 * just land on?" is a real question. Flash the destination.
 *
 * Deliberately NOT wired to body-text figure cross-references: those
 * open the figure in place rather than scrolling (see the lightbox
 * section above), so there is no destination to point at.
 */
(function () {
  "use strict";

  var FLASH = "is-jump-flash";
  var DURATION = 1200;
  var timer = null;
  var current = null;

  function flash(id) {
    var target;
    try {
      target = document.getElementById(decodeURIComponent(id));
    } catch (e) {
      target = document.getElementById(id);
    }
    if (!target) return;
    /* citations.lua anchors a reference with an EMPTY span at its start,
     * which has no box to highlight — paint the enclosing block. */
    var box = target.closest("li, p, div, h2, h3, h4, section") || target;

    if (current) current.classList.remove(FLASH);
    if (timer) window.clearTimeout(timer);

    /* Force a reflow between removal and re-add, or re-clicking the same
     * link is a no-op: the class never left the computed style, so the
     * animation is never restarted. */
    void box.offsetWidth;

    box.classList.add(FLASH);
    current = box;
    timer = window.setTimeout(function () {
      box.classList.remove(FLASH);
      if (current === box) current = null;
    }, DURATION);
  }

  document.addEventListener("click", function (e) {
    var a = e.target.closest ? e.target.closest('a[href^="#"]') : null;
    if (!a) return;
    var href = a.getAttribute("href");
    if (!href || href === "#") return;
    /* Let the browser do the scrolling; just mark where it lands. */
    flash(href.slice(1));
  });

  window.addEventListener("hashchange", function () {
    if (location.hash.length > 1) flash(location.hash.slice(1));
  });
})();
