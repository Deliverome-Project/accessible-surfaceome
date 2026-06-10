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

-- Map "figure 2" / "appendix figure 4" (lowercase, single-spaced)
-- to the h5 anchor identifier we'll link to.
local figure_ids = {}

-- Phase 1: collect figure-caption ids from h5 headings whose text
-- starts with "Figure N." or "Appendix Figure N.". Two-phase walk
-- via filter ordering (Header before Para via return order).
local function collect_figure_ids(elem)
  if elem.level ~= 5 then return end
  local text = pandoc.utils.stringify(elem):lower()
    :gsub("^%s+", "")
  -- Match either "appendix figure N" (checked first — longer prefix)
  -- or "figure N". Trailing punctuation (".", ":") is allowed.
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
  local p, w = s:match("^([%(%[]?)([Ff]igure)$")
  if p then return p, w end
  return s:match("^([%(%[]?)([Ff]ig%.?)$")
end

-- Same shape but for "Appendix" prefix word.
local function appendix_head_match(s)
  return s:match("^([%(%[]?)([Aa]ppendix)$")
end

-- Tail like "2", "2)", "2.", "2;". Returns (num, suffix) or nil.
local function tail_match(s)
  return s:match("^(%d+)([^%a%d]*)$")
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
  local opener_to_closer = {["("] = ")", ["["] = "]"}
  local matching_close = opener_to_closer[prefix]
  local before_link, link_text, after_link
  if matching_close and suffix:sub(1, 1) == matching_close then
    -- Matched bracket pair — pull both INTO the link text.
    before_link = ""
    link_text = prefix .. ref_text .. matching_close
    after_link = suffix:sub(2)
  else
    -- No matching close — prefix stays outside; the link covers
    -- just the reference text. Suffix (punctuation like "." or
    -- ",") sits to the right of the link.
    before_link = prefix
    link_text = ref_text
    after_link = suffix
  end
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

    -- "Figure N" (3 inlines)
    if not matched
        and i + 2 <= #inlines
        and inlines[i].t == "Str"
        and inlines[i + 1].t == "Space"
        and inlines[i + 2].t == "Str" then
      local prefix, fig_word = head_match(inlines[i].text)
      if fig_word then
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
         or elem.identifier:match("^appendix%-figure%-%d"))
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
      result:insert(pandoc.Para(new_inlines))
      local stripped_h = pandoc.Header(
        nxt.level, nxt.content,
        pandoc.Attr("", nxt.attr.classes, nxt.attr.attributes)
      )
      result:insert(stripped_h)
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
      return pandoc.Para(linkify_figure_refs(elem.content))
    end,
  },
}
