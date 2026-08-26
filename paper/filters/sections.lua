--[[
  paper/filters/sections.lua

  Linkify in-body SECTION cross-references so a reader clicking
  "(see Methods)" in the Results jumps to the Methods heading — the
  same affordance filters/figures.lua gives "Figure N".

  Why a filter and not the .docx: the manuscript is authored in
  Google Docs, which exports its cross-references as plain text.
  The .docx carries 64 bookmarks, but they're all auto-generated
  Zotero/GDocs anchors (`_19b52mki8bwc`) with zero `w:anchor`
  hyperlinks pointing at them — so there is nothing to preserve and
  the links have to be synthesised from the prose.

  What it does NOT touch, deliberately:

  * "Figure S3", "Table S1" and friends. Supplementary lives in a
    SEPARATE file, so an intra-document anchor would be a dead link
    (worse than plain text — it looks clickable and goes nowhere).
    SUPPLEMENTARY_PATTERNS below encodes that; extend it if the
    supplement ever gains new label shapes.
  * The section headings themselves, so "Methods" in the Methods
    title doesn't self-link.
  * Any name that resolves to more than one heading. The draft has
    a duplicated "Web viewer and public API" H3; linking either
    copy would be a coin-flip, so ambiguous names are dropped from
    the link table and reported on stderr.

  Matching is whole-phrase and case-sensitive on the first letter
  (so prose like "the methods we used" stays plain, while the
  proper-noun "Methods" links). Multi-word section names are matched
  across the Str/Space inline runs pandoc emits.

  Usage:  pandoc … --lua-filter=paper/filters/sections.lua
          (must run AFTER figures.lua so figure anchors already exist)
]]--

-- Section names worth linking. Keys are matched against heading text
-- (case-insensitively); only headings that actually exist in the
-- document end up in the link table, so listing a name here that the
-- manuscript doesn't use is harmless.
local LINKABLE_SECTIONS = {
  "Methods",
  "Results",
  "Discussion",
  "Introduction",
  "Abstract",
  "Data availability",
  "Code availability",
}

-- ── Deep-linking to the RIGHT Methods subsection ──────────────────────
--
-- A bare "see Methods" link that lands on the Methods H2 makes the
-- reader scroll through ~20 subsections to find the relevant one.
-- Each rule below retargets the link for ONE reference site, matched
-- by a distinctive phrase in the same block (paragraph or caption).
--
--   contains — substring of the containing block's plain text. Only
--              blocks that ALSO mention the section name are ever
--              tested, so the phrase needs to be unique among those
--              blocks, not across the whole manuscript.
--   target   — heading id to link to (verify it exists: pandoc
--              slugifies heading text, e.g. "Deep-dive scoring" →
--              "deep-dive-scoring").
--   section  — which section name this retargets. Defaults to
--              "Methods"; set it if a rule ever needs to retarget
--              "Results" etc.
--
-- Anything with no matching rule falls back to the section's own
-- top-level heading, so an un-ruled reference degrades to the old
-- behaviour rather than breaking. Unfired and ambiguous rules are
-- reported on stderr at build time — see the report at the bottom.
local REFERENCE_TARGETS = {
  {
    contains = "prominent examples",
    target = "candidate-universe-construction",
    note = "Intro: names the five source databases",
  },
  {
    contains = "Five-way Venn diagram",
    target = "candidate-universe-construction",
    note = "Fig 1 caption: per-source inclusion rules",
  },
  {
    contains = "secreted targets primarily from ADCdb",
    target = "positive-control-target-sets",
    note = "Results: the three positive-control target lists",
  },
  {
    -- Keyed off the paragraph's opening clause, not "pipeline runs in
    -- three stages": that sentence appears twice — here, and again in
    -- Methods > Deep-dive pipeline architecture, which is the very
    -- paragraph this link points AT.
    contains = "We therefore constructed a deep-dive pipeline",
    target = "deep-dive-pipeline-architecture",
    note = "Results: three-stage pipeline → the subsection that expands it",
  },
  {
    contains = "induction trigger",
    target = "deep-dive-scoring",
    note = "Fig 5 caption: canonical/likely tier predicates",
  },
  {
    contains = "Five axes of richness",
    target = "deep-dive-scoring",
    note = "Fig 6 caption: confidence-tier definitions",
  },
}

-- rule index → how many blocks it fired on (for the build-time report).
local rule_hits = {}
for i = 1, #REFERENCE_TARGETS do rule_hits[i] = 0 end

-- Ids seen on headings, so a rule pointing at a typo'd/renamed target
-- is caught at build time rather than shipping a dead anchor.
local known_ids = {}

-- Anything matching these is supplementary — never linkify, and never
-- let a section match swallow the label.
local SUPPLEMENTARY_PATTERNS = {
  "^[Ff]igure$",   -- guarded contextually below (Figure S3)
  "^[Tt]able$",
}

-- name(lowercased) → {id = "...", count = N}
local section_index = {}
-- Set of lowercased names that are ambiguous (>1 heading) — skipped.
local ambiguous = {}

local function want(name)
  local lower = name:lower()
  for _, s in ipairs(LINKABLE_SECTIONS) do
    if s:lower() == lower then return true end
  end
  return false
end

-- Phase 1: index every heading whose text is a linkable section name.
local function index_heading(elem)
  if elem.identifier == nil or elem.identifier == "" then return end
  known_ids[elem.identifier] = true
  local text = pandoc.utils.stringify(elem)
    :gsub("^%s+", ""):gsub("%s+$", "")
  if not want(text) then return end
  local key = text:lower()
  local existing = section_index[key]
  if existing and existing.id ~= elem.identifier then
    -- Duplicate heading with the same name → ambiguous target.
    ambiguous[key] = true
    io.stderr:write(
      ("sections.lua: '%s' matches multiple headings (#%s, #%s) — "):format(
        text, existing.id, elem.identifier)
      .. "leaving these references as plain text.\n")
    return
  end
  section_index[key] = {id = elem.identifier}
end

-- True when inline i begins a supplementary label like "Figure S3" /
-- "Table S1": a Figure/Table word followed by Space then S<digits>.
local function is_supplementary_at(inlines, i)
  local cur = inlines[i]
  if cur == nil or cur.t ~= "Str" then return false end
  local bare = cur.text:gsub("^[%(%[]", "")
  local looks_labelish = false
  for _, pat in ipairs(SUPPLEMENTARY_PATTERNS) do
    if bare:match(pat) then looks_labelish = true break end
  end
  if not looks_labelish then return false end
  local nxt = inlines[i + 2]
  return inlines[i + 1] ~= nil and inlines[i + 1].t == "Space"
    and nxt ~= nil and nxt.t == "Str"
    and nxt.text:match("^[Ss]%d+") ~= nil
end

-- Try to match a (possibly multi-word) section name starting at
-- inline i. Returns matched_name, inlines_consumed, prefix, suffix.
-- Prefix/suffix are the bracketing punctuation carried on the first
-- and last Str (e.g. "(Methods)." → prefix "(", suffix ").").
local function match_section_at(inlines, i)
  -- Longest-first so "Data availability" wins over a bare "Data".
  local names = {}
  for _, s in ipairs(LINKABLE_SECTIONS) do names[#names + 1] = s end
  table.sort(names, function(a, b) return #a > #b end)

  for _, name in ipairs(names) do
    local key = name:lower()
    if section_index[key] and not ambiguous[key] then
      local words = {}
      for w in name:gmatch("%S+") do words[#words + 1] = w end
      -- Words occupy inlines i, i+2, i+4, … with Space between.
      local ok = true
      local prefix, suffix = "", ""
      for wi, word in ipairs(words) do
        local idx = i + (wi - 1) * 2
        local inl = inlines[idx]
        if inl == nil or inl.t ~= "Str" then ok = false break end
        if wi > 1 then
          local sp = inlines[idx - 1]
          if sp == nil or sp.t ~= "Space" then ok = false break end
        end
        local text = inl.text
        if wi == 1 then
          local p, rest = text:match("^([%(%[]?)(.*)$")
          prefix = p or ""
          text = rest or text
        end
        if wi == #words then
          local body, s = text:match("^(.-)([^%w]*)$")
          text = body or text
          suffix = s or ""
        end
        if text ~= word then ok = false break end
      end
      if ok then
        return name, #words * 2 - 1, prefix, suffix
      end
    end
  end
  return nil
end

-- Find the retarget rule (if any) that applies to a block, given the
-- block's already-stringified plain text. Returns target_id, section
-- name — or nil when the block matches no rule.
local function rule_for_block(block_text)
  for idx, rule in ipairs(REFERENCE_TARGETS) do
    if block_text:find(rule.contains, 1, true) then
      rule_hits[idx] = rule_hits[idx] + 1
      if not known_ids[rule.target] then
        io.stderr:write(
          ("sections.lua: rule '%s' targets #%s, which is not a heading id "):format(
            rule.contains, rule.target)
          .. "in this document — falling back to the section heading.\n")
        return nil
      end
      return rule.target, rule.section or "Methods"
    end
  end
  return nil
end

-- ``override_id`` / ``override_name``: when set, a link to
-- ``override_name`` points at ``override_id`` instead of that
-- section's own heading. Everything else is unaffected.
local function linkify_section_refs(inlines, override_id, override_name)
  local result = pandoc.List({})
  local i = 1
  while i <= #inlines do
    if is_supplementary_at(inlines, i) then
      -- Emit the whole "Figure S3" run untouched.
      result:insert(inlines[i])
      result:insert(inlines[i + 1])
      result:insert(inlines[i + 2])
      i = i + 3
    else
      local name, consumed, prefix, suffix = match_section_at(inlines, i)
      if name then
        local id = section_index[name:lower()].id
        if override_id and override_name
            and name:lower() == override_name:lower() then
          id = override_id
        end
        if prefix ~= "" then result:insert(pandoc.Str(prefix)) end
        result:insert(pandoc.Link({pandoc.Str(name)}, "#" .. id))
        if suffix ~= "" then result:insert(pandoc.Str(suffix)) end
        i = i + consumed
      else
        result:insert(inlines[i])
        i = i + 1
      end
    end
  end
  return result
end

return {
  -- Phase 1: build the heading index.
  {
    Header = function(elem)
      index_heading(elem)
      return nil
    end,
  },
  -- Phase 2: rewrite body paragraphs AND figure captions.
  --
  -- Captions matter: three of the six "Methods" references in the
  -- draft live inside caption text ("…details in Methods", "…see
  -- Methods"), and pandoc emits captions as <h5> headings, not
  -- paragraphs. Skipping all Headers would leave exactly those
  -- unlinked.
  --
  -- Self-linking is prevented by name, not by block type: a Header
  -- whose own text IS a linkable section name (the "Methods"
  -- heading itself) is left untouched. Any other Header — figure
  -- captions included — gets the same treatment as body prose.
  {
    Para = function(elem)
      local id, name = rule_for_block(pandoc.utils.stringify(elem))
      return pandoc.Para(linkify_section_refs(elem.content, id, name))
    end,
    Plain = function(elem)
      local id, name = rule_for_block(pandoc.utils.stringify(elem))
      return pandoc.Plain(linkify_section_refs(elem.content, id, name))
    end,
    Header = function(elem)
      local text = pandoc.utils.stringify(elem)
      local trimmed = text:gsub("^%s+", ""):gsub("%s+$", "")
      if want(trimmed) then return nil end
      local id, name = rule_for_block(text)
      return pandoc.Header(
        elem.level, linkify_section_refs(elem.content, id, name), elem.attr
      )
    end,
  },
  -- Phase 3: report rules that never fired, or fired on more than one
  -- block. A rule stops matching when the prose it keys off is
  -- reworded, and the link then silently reverts to the section
  -- heading — so surface it at build time rather than letting the
  -- deep link rot unnoticed.
  {
    Pandoc = function(doc)
      for idx, rule in ipairs(REFERENCE_TARGETS) do
        local n = rule_hits[idx]
        if n == 0 then
          io.stderr:write(
            ("sections.lua: rule '%s' (-> #%s) matched NO block — "):format(
              rule.contains, rule.target)
            .. "the prose it keys off may have been reworded.\n")
        elseif n > 1 then
          io.stderr:write(
            ("sections.lua: rule '%s' (-> #%s) matched %d blocks — "):format(
              rule.contains, rule.target, n)
            .. "tighten the phrase so it names one reference site.\n")
        end
      end
      return doc
    end,
  },
}
