--[[
  paper/filters/figures.lua

  Two figure-related transformations:

  1. **Split image-in-heading shapes.** When a .docx author leaves an
     image embedded in the same paragraph as the figure caption (and
     that paragraph is styled as Heading N), pandoc emits something
     like:

         <h5 id="figure-2.-…"><img src="…" />Figure 2. Caption…</h5>

     The print CSS treats `<h5>` as the caption card — which means
     the image gets crammed inside the caption's beige box. This
     filter splits the image out into its own `Para`, and keeps the
     heading with just the caption text + original id:

         <p><img src="…" /></p>
         <h5 id="figure-2.-…">Figure 2. Caption…</h5>

     Fires for ANY heading level — same shape sometimes happens with
     <h2> when the .docx's Heading 1 / 2 style leaks onto the image
     paragraph instead of just the caption.

  2. **Linkify in-body "Figure N" references.** Walks every Para,
     finds text patterns like "Figure 2", "Figure 3", "Appendix
     Figure 4", "(Figure 2)", etc., and converts them into `<a>`
     anchor links targeting the matching `<h5 id="figure-N…">`
     caption heading. Reader can click a body-text "Figure 2" and
     jump to the figure. Skipped inside the caption headings
     themselves so the figure label doesn't self-link.

  Usage:  pandoc … --lua-filter=paper/filters/figures.lua
]]--


-- ── Configuration ────────────────────────────────────────────────
--
-- Everything this filter assumes about a particular manuscript lives
-- HERE. Adapting it to another paper should mean editing this block,
-- not the matching logic below.
--
-- CAPTION_LEVELS
--   Heading levels that hold figure captions. This project's .docx
--   styles captions as Heading 5, so pandoc emits <h5>. A journal
--   template that uses Heading 6, or two levels, just lists them.
--
-- LABEL_WORDS
--   The words that can introduce a reference, as Lua patterns
--   anchored whole-token. Plurals matter: "Figures S1, S2" is as
--   common as the singular, and omitting the plural silently drops
--   every multi-reference.
--
-- SERIES
--   One entry per numbering series the manuscript uses. `caption`
--   is the lower-cased prefix the CAPTION starts with; `cite` is how
--   the BODY writes the number.
--
--   The supplementary entry carries `cite_prefix = "s"` because this
--   manuscript captions them "Supplementary Figure 10" but cites
--   them "Figure S10" — a split worth supporting generally, since
--   many journals do exactly this. Both spellings are registered
--   against the same anchor, so either works.
--
-- SEPARATORS
--   Characters that may join numbers inside one reference run:
--   "Figures S1, S2" and "(Figure S13/S14)" both occur here.
local CAPTION_LEVELS = {[5] = true}

local LABEL_WORDS = {"[Ff]igures?", "[Ff]igs?%.?"}

local SERIES = {
  {caption = "supplementary figure", cite_prefix = "s"},
  {caption = "appendix figure",      cite_prefix = "appendix "},
  {caption = "figure",               cite_prefix = ""},
}

local SEPARATORS = "/&,;"

-- Map "figure 2" / "appendix figure 4" (lowercase, single-spaced)
-- to the h5 anchor identifier we'll link to.
local figure_ids = {}

-- Phase 1: collect figure-caption ids from h5 headings whose text
-- starts with "Figure N." or "Appendix Figure N.". Two-phase walk
-- via filter ordering (Header before Para via return order).
local function collect_figure_ids(elem)
  if not CAPTION_LEVELS[elem.level] then return end
  local text = pandoc.utils.stringify(elem):lower()
    :gsub("^%s+", "")
  -- "supplementary figure N" / "appendix figure N" are checked before
  -- plain "figure N" because the longer prefixes also contain it.
  -- Trailing punctuation (".", ":") is allowed.
  local supp = text:match("^supplementary figure (%d+)")
  if supp and elem.identifier ~= "" then
    -- The body cites these as "Figure S10" while the captions read
    -- "Supplementary Figure 10". Register BOTH spellings against the
    -- same anchor: linking has to work from what the prose actually
    -- says, and reconciling the manuscript's own wording is the
    -- author's call, not this filter's.
    figure_ids["figure s" .. supp] = elem.identifier
    figure_ids["supplementary figure " .. supp] = elem.identifier
    return
  end
  local key = text:match("^(appendix figure %d+)")
    or text:match("^(figure %d+)")
  if key and elem.identifier ~= "" then
    figure_ids[key] = elem.identifier
  end
end

-- Phase 1 ALSO: split image-in-heading. Returns either:
--   * `elem` unchanged (no image inside)
--   * a list of blocks: [Para(span#id, img), Para(img), ..., Header(caption_no_id)]
--
-- The heading's id MOVES to the first image's paragraph so links
-- to `#figure-N` land at the top of the image rather than at the
-- caption beneath. Implementation: the first image paragraph gets
-- an inline `<span id="…"></span>` anchor before the image; the
-- heading is reissued WITHOUT the id (it'd otherwise collide).
local function split_image_in_heading(elem)
  local imgs = {}
  local rest = pandoc.List({})
  for _, inline in ipairs(elem.content) do
    if inline.t == "Image" then
      table.insert(imgs, inline)
    else
      rest:insert(inline)
    end
  end
  if #imgs == 0 then
    return elem
  end
  local results = pandoc.List({})
  for idx, img in ipairs(imgs) do
    if idx == 1 and elem.identifier and elem.identifier ~= "" then
      -- Empty Span with the heading's id — acts as the in-page
      -- anchor target. The link from body text now scrolls so this
      -- span (at the top of the image paragraph) is at the top of
      -- the viewport.
      local anchor = pandoc.Span({}, pandoc.Attr(elem.identifier))
      results:insert(pandoc.Para({anchor, img}))
    else
      results:insert(pandoc.Para({img}))
    end
  end
  if #rest > 0 then
    -- Heading keeps its content but loses the id (now on the image
    -- paragraph). Classes / extra attributes preserved.
    local stripped_attr = pandoc.Attr(
      "",
      elem.attr and elem.attr.classes or {},
      elem.attr and elem.attr.attributes or {}
    )
    results:insert(pandoc.Header(elem.level, rest, stripped_attr))
  end
  -- Wrap image(s) + caption as ONE block, but ONLY when this heading
  -- actually held both. That is the supplementary-figure shape (image
  -- pasted into the caption paragraph), and without the wrapper it
  -- relied on the advisory break-after/break-before pair — which
  -- WeasyPrint ignored across the column-span:all boundary, printing
  -- Supplementary Figure 3's artwork on one page and its caption
  -- alone on the next.
  --
  -- When the heading was image-ONLY (`rest` empty — Figure 6's shape,
  -- where the caption is its own following heading), return the bare
  -- paragraph. Wrapping it here would hide the Para from
  -- reattach_ids_to_image_paras, which pairs it with that next
  -- heading and does its own wrapping; hiding it silently cost
  -- Figure 6 its canonical-render swap.
  if #rest > 0 then
    return pandoc.List({
      pandoc.Div(results, pandoc.Attr("", {"figure-block"})),
    })
  end
  return results
end

-- Single-pass Header here is unused; we wire collect + transform as
-- two separate phases in the returned filter list at the bottom of
-- this file. Pandoc applies them in order so all ids are recorded
-- BEFORE any Para is asked to linkify.

-- Phase 2: walk every Para's inlines and replace "Figure N" /
-- "Appendix Figure N" text with a Link pointing at the captured id.
--
-- Strategy: scan inline-by-inline for the canonical pandoc tokenization
-- of these phrases:
--   "Figure 2"               → Str "Figure" + Space + Str "2"  (3 inlines)
--   "Appendix Figure 4"      → Str "Appendix" + Space + Str "Figure"
--                              + Space + Str "4"               (5 inlines)
--   "(Figure 2)"             → Str "(Figure" + Space + Str "2)" (same
--                              shape but the first Str has a "(" prefix
--                              and the last has a ")" / "." / ";" suffix)
--
-- We accept optional bracketing punctuation on the head and tail and
-- preserve it verbatim so the parenthetical reads naturally with the
-- link inside.
--
-- A trailing "S2" / "Table 2" / "Figure 1A" pattern is NOT a figure
-- reference; we only match a bare integer N with no letter suffix
-- (the %d+ pattern in `tail_num` requires no following alpha char).

-- Pattern accepted as the leading word: "Figure", "Fig", "Fig.",
-- with optional leading "(" / "[".
-- IMPORTANT: don't write `match(A) or match(B)` — the surrounding `or`
-- truncates multi-capture returns to a single value, so the second
-- capture (the word) gets dropped. Branch explicitly.
local function head_match(s)
  -- Driven by LABEL_WORDS so another manuscript's vocabulary is a
  -- config change. Plurals are included there because "Figures S1,
  -- S2" is as common as the singular, and matching only the singular
  -- silently drops every multi-reference.
  for _, word in ipairs(LABEL_WORDS) do
    local p, w = s:match("^([%(%[]?)(" .. word .. ")$")
    if p then return p, w end
  end
  return nil
end

-- Same shape but for "Appendix" prefix word.
local function appendix_head_match(s)
  return s:match("^([%(%[]?)([Aa]ppendix)$")
end

-- Tail like "2", "2)", "2.", "2;". Returns (num, suffix) or nil.
local function tail_match(s)
  return s:match("^(%d+)([^%a%d]*)$")
end

-- Supplementary tail: "S3", "S10)", "S4,". Returns (label, suffix) or
-- nil, where label is the lookup key fragment ("s3"). Kept separate
-- from tail_match because a bare %d+ must NOT swallow the "S" — an
-- unqualified "Figure 3" and a supplementary "Figure S3" are
-- different figures and mixing them would silently mis-link.
local function supp_tail_match(s)
  local num, suffix = s:match("^[Ss](%d+)([^%a%d]*)$")
  if not num then return nil end
  return num, suffix or ""
end

-- Slash-joined supplementary pairs: "S13/S14", "S13/S14)". The draft
-- cites two panels-worth of supplement that way, and a single-number
-- matcher leaves the whole run unlinked. Returns {n1, n2, ...} and the
-- trailing punctuation, or nil when the shape does not fit.
local function supp_multi_match(s)
  local body, suffix = s:match("^([Ss]%d+[/&,]?[Ss]?[%d/&,Ss]*)([^%a%d/&,]*)$")
  if not body or not body:find("/") then return nil end
  local nums = {}
  for n in body:gmatch("[Ss](%d+)") do nums[#nums + 1] = n end
  if #nums < 2 then return nil end
  return nums, suffix or ""
end

-- Emit a body-text figure reference as a Link, pulling matched
-- bracket pairs INSIDE the link text. The complication is that the
-- prefix (a leading "(" or "[" on the head Str) and the suffix
-- (a tail Str like ")." / ");" / ".") may or may not form a
-- matched pair around the reference:
--
--   "(Figure 1)"        prefix="(", suffix=")"   → link covers whole thing
--   "(Figure 1)."       prefix="(", suffix=")."  → link covers "(Figure 1)", trailing "."
--   "[Figure 1]"        prefix="[", suffix="]"   → link covers whole thing
--   "(Figure 1, 2)"     prefix="(", suffix=","   → no close paren in suffix; prefix stays OUTSIDE the link (the ")" lives further along the inline chain, with the rest of the citation group)
--   "Figure 1."         prefix="",  suffix="."   → link covers "Figure 1", trailing "."
local function emit_link_with_brackets(result, prefix, ref_text, suffix, id)
  -- Brackets ALWAYS stay outside the link, so only "Figure 1" carries
  -- link colour and the surrounding "( )" prints in body ink. They
  -- belong to the sentence, not to the reference — the same treatment
  -- filters/citations.lua gives "(Brase, 2009)".
  --
  -- An earlier version pulled a matched pair INTO the link text,
  -- which painted the brackets maroon and made a parenthetical
  -- reference read as one solid coloured blob.
  local before_link = prefix
  local link_text = ref_text
  local after_link = suffix
  if before_link ~= "" then result:insert(pandoc.Str(before_link)) end
  result:insert(pandoc.Link({pandoc.Str(link_text)}, "#" .. id))
  if after_link ~= "" then result:insert(pandoc.Str(after_link)) end
end

local function linkify_figure_refs(inlines)
  local result = pandoc.List({})
  local i = 1
  while i <= #inlines do
    local matched = false

    -- "Appendix Figure N" (5 inlines)
    if i + 4 <= #inlines
        and inlines[i].t == "Str"
        and inlines[i + 1].t == "Space"
        and inlines[i + 2].t == "Str"
        and inlines[i + 3].t == "Space"
        and inlines[i + 4].t == "Str" then
      local prefix, app_word = appendix_head_match(inlines[i].text)
      local _, fig_word = head_match(inlines[i + 2].text)
      if app_word and fig_word and inlines[i + 2].text:sub(1, 1) ~= "(" then
        local num, suffix = tail_match(inlines[i + 4].text)
        if num then
          local key = "appendix figure " .. num
          local id = figure_ids[key]
          if id then
            emit_link_with_brackets(result, prefix, app_word .. " " .. fig_word .. " " .. num, suffix, id)
            i = i + 5
            matched = true
          end
        end
      end
    end

    -- "Figure N" and "Figure SN" (3 inlines each)
    if not matched
        and i + 2 <= #inlines
        and inlines[i].t == "Str"
        and inlines[i + 1].t == "Space"
        and inlines[i + 2].t == "Str" then
      local prefix, fig_word = head_match(inlines[i].text)
      if fig_word then
        -- Supplementary first: "S3" would otherwise fall through to
        -- tail_match, fail, and leave the reference unlinked.
        -- Consume a RUN of supplementary numbers. Pandoc tokenises
        -- "Figures S1, S2)" as Str"S1," Space Str"S2)", so a matcher
        -- that only looked at one tail token linked S1 and dropped S2.
        -- Slash-joined pairs ("S13/S14") arrive as a single token and
        -- are handled by the same collector.
        local nums, seps, consumed, tail_suffix = {}, {}, 0, ""
        local j = i + 2
        while j <= #inlines and inlines[j].t == "Str" do
          -- Trailing punctuation may itself contain "," or ";" —
          -- "(Figure S1)," is common. Excluding those from the SUFFIX
          -- class (they're needed inside the body for run detection)
          -- made the whole token fail to match, silently dropping the
          -- reference. The suffix accepts any non-alphanumeric run;
          -- Lua's greedy body capture still claims a separator comma
          -- when one is genuinely mid-run ("S1, S2").
          local body, suf = inlines[j].text:match("^([Ss]%d+[/&,;]?[Ss]?[%d/&,;Ss]*)([^%a%d]*)$")
          if not body then break end
          for n in body:gmatch("[Ss](%d+)") do
            if #nums > 0 then
              seps[#nums] = body:find("/") and "/" or ", "
            end
            nums[#nums + 1] = n
          end
          consumed = j - i + 1
          tail_suffix = suf or ""
          -- Continue only when this token ended with a separator and
          -- the next inline is " S<n>" — otherwise the run is done.
          local trailing = body:sub(-1)
          if (trailing == "," or trailing == ";")
              and inlines[j + 1] and inlines[j + 1].t == "Space"
              and inlines[j + 2] and inlines[j + 2].t == "Str"
              and inlines[j + 2].text:match("^[Ss]%d") then
            seps[#nums] = ", "
            j = j + 2
          else
            break
          end
        end

        if #nums > 0 then
          local all_known = true
          for _, n in ipairs(nums) do
            if not figure_ids["figure s" .. n] then all_known = false end
          end
          if all_known then
            if prefix ~= "" then result:insert(pandoc.Str(prefix)) end
            for idx, n in ipairs(nums) do
              if idx > 1 then result:insert(pandoc.Str(seps[idx - 1] or ", ")) end
              local label = (idx == 1)
                and (fig_word .. " S" .. n) or ("S" .. n)
              result:insert(pandoc.Link({pandoc.Str(label)},
                "#" .. figure_ids["figure s" .. n]))
            end
            if tail_suffix ~= "" then result:insert(pandoc.Str(tail_suffix)) end
            i = i + consumed
            matched = true
          end
        end

        if not matched then
          local num, suffix = tail_match(inlines[i + 2].text)
          if num then
            local key = "figure " .. num
            local id = figure_ids[key]
            if id then
              emit_link_with_brackets(result, prefix, fig_word .. " " .. num, suffix, id)
              i = i + 3
              matched = true
            end
          end
        end
      end
    end

    if not matched then
      result:insert(inlines[i])
      i = i + 1
    end
  end
  return result
end

-- Predicates for the Blocks pass below.
local function para_contains_img(elem)
  if elem.t ~= "Para" then return false end
  for _, inl in ipairs(elem.content) do
    if inl.t == "Image" then return true end
  end
  return false
end

local function is_figure_caption_heading(elem)
  return elem.t == "Header"
    and elem.identifier ~= nil
    and elem.identifier ~= ""
    and (elem.identifier:match("^figure%-%d")
         or elem.identifier:match("^appendix%-figure%-%d")
         -- Supplementary captions carry ids like
         -- "supplementary-figure-2-…". Omitting this pattern meant the
         -- image-only-heading shape (image in its own heading, caption
         -- in the next) never got paired for supplementary figures, so
         -- they kept splitting across pages even after the wrapper
         -- landed.
         or elem.identifier:match("^supplementary%-figure%-%d"))
end

-- After splitting + emitting, walk neighbouring (img-Para, caption-Hdr)
-- pairs and move the heading's anchor id onto the preceding Para via
-- a leading empty Span. Without this, a body-text link to
-- `#figure-2` lands at the CAPTION block — i.e., one figure-card
-- below where the reader wants to land. With it, the same link
-- scrolls so the image appears at the top of the viewport.
local function reattach_ids_to_image_paras(blocks)
  local result = pandoc.List({})
  local i = 1
  while i <= #blocks do
    local cur = blocks[i]
    local nxt = blocks[i + 1]
    if para_contains_img(cur) and nxt and is_figure_caption_heading(nxt) then
      local id = nxt.identifier
      -- If the Para's content already starts with a Span carrying
      -- the same id (Fig 2 case — heading was split earlier),
      -- there's nothing to move; the heading has already lost its
      -- id during the split. The conditional above (h5 must have a
      -- non-empty figure id) shields us from that case naturally.
      local anchor = pandoc.Span({}, pandoc.Attr(id))
      local new_inlines = pandoc.List({anchor})
      for _, inl in ipairs(cur.content) do new_inlines:insert(inl) end
      local stripped_h = pandoc.Header(
        nxt.level, nxt.content,
        pandoc.Attr("", nxt.attr.classes, nxt.attr.attributes)
      )
      -- Wrap the pair in ONE block so the artwork and its caption are
      -- structurally inseparable. `break-after`/`break-before: avoid`
      -- on the two siblings is only advisory, and WeasyPrint dropped
      -- it across the column-span:all boundary — Supplementary Figure
      -- 3 ended up with its caption stranded alone at the top of a
      -- near-empty page. A single container with break-inside: avoid
      -- is a constraint the layout engine cannot quietly ignore.
      result:insert(pandoc.Div(
        {pandoc.Para(new_inlines), stripped_h},
        pandoc.Attr("", {"figure-block"})
      ))
      i = i + 2
    else
      result:insert(cur)
      i = i + 1
    end
  end
  return result
end

-- Three-phase pipeline. Pandoc applies each filter table in order
-- against the full document tree.
-- Reference-shaped text the filter did NOT link, reported at the end
-- of the build. Without this a reference that falls outside the
-- patterns above just stays plain text — which is how "(Figure S1),"
-- and every "Figures S1, S2" went unlinked through several builds
-- without anything saying so.
local unlinked = {}

local function note_unlinked(inlines)
  -- Scan only the text OUTSIDE links. Stringifying the whole run
  -- would include each Link's own label ("Figure 1"), so every
  -- successfully-linked reference would report itself as unlinked —
  -- a checker that fires on success is worse than no checker.
  local parts = {}
  for _, inl in ipairs(inlines) do
    if inl.t ~= "Link" then
      parts[#parts + 1] = pandoc.utils.stringify(inl)
    else
      parts[#parts + 1] = "\0"   -- barrier: don't fuse across a link
    end
  end
  local text = table.concat(parts, " ")
  for ref in text:gmatch("[Ff]igures?%s+S?%d+") do
    local key = ref:gsub("%s+", " ")
    unlinked[key] = (unlinked[key] or 0) + 1
  end
end

return {
  -- Phase 1: walk all headings, record figure-N id → anchor map.
  {
    Header = function(elem)
      collect_figure_ids(elem)
      return nil
    end,
  },
  -- Phase 2: split image-in-heading shapes.
  {
    Header = function(elem)
      return split_image_in_heading(elem)
    end,
  },
  -- Phase 3: move figure-caption ids from h5 → preceding Para(img)
  -- so body links land at the image's top, then linkify body refs.
  {
    Blocks = reattach_ids_to_image_paras,
    Para = function(elem)
      local out = linkify_figure_refs(elem.content)
      note_unlinked(out)
      return pandoc.Para(out)
    end,
  },
  -- Phase 4: report anything reference-shaped that stayed plain text.
  {
    Pandoc = function(doc)
      local names = {}
      for k in pairs(unlinked) do names[#names + 1] = k end
      if #names > 0 then
        table.sort(names)
        io.stderr:write(
          ("figures.lua: %d reference(s) left UNLINKED (no caption matched): ")
            :format(#names) .. table.concat(names, "; ") .. "\n")
      end
      return doc
    end,
  },
}
