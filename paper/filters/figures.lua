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
--   * a list of blocks: [Para(img), Para(img), ..., Header(caption)]
-- The Header keeps its original level + attributes (so the id
-- survives for downstream linkification).
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
  for _, img in ipairs(imgs) do
    results:insert(pandoc.Para({img}))
  end
  -- Drop the heading entirely if no caption text survives — the
  -- bare-image case (some .docx authors style a standalone image
  -- paragraph as a heading; the heading carries no semantic content).
  -- Otherwise keep the heading with just the caption text.
  if #rest > 0 then
    results:insert(pandoc.Header(elem.level, rest, elem.attr))
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
            if prefix ~= "" then result:insert(pandoc.Str(prefix)) end
            local link_text = app_word .. " " .. fig_word .. " " .. num
            result:insert(pandoc.Link({pandoc.Str(link_text)}, "#" .. id))
            if suffix ~= "" then result:insert(pandoc.Str(suffix)) end
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
            if prefix ~= "" then result:insert(pandoc.Str(prefix)) end
            local link_text = fig_word .. " " .. num
            result:insert(pandoc.Link({pandoc.Str(link_text)}, "#" .. id))
            if suffix ~= "" then result:insert(pandoc.Str(suffix)) end
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

-- Two-phase pipeline. Pandoc applies each filter table in order,
-- against the FULL document tree. So Phase 1 fully populates
-- `figure_ids` before Phase 2 runs (otherwise body paragraphs that
-- appear in the doc BEFORE the captioning h5 would see an empty
-- map and skip linkification).
return {
  -- Phase 1: walk all headings, record figure-N id → anchor map.
  {
    Header = function(elem)
      collect_figure_ids(elem)
      return nil -- no transform in this pass
    end,
  },
  -- Phase 2: split image-in-heading shapes; linkify body refs.
  {
    Header = function(elem)
      return split_image_in_heading(elem)
    end,
    Para = function(elem)
      return pandoc.Para(linkify_figure_refs(elem.content))
    end,
  },
}
