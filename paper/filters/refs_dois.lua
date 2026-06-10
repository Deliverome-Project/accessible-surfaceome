--[[
  paper/filters/refs_dois.lua

  Pandoc Lua filter that re-shapes the References section so:

    1. The outer Zotero google-docs <a> link (the one Zotero inserts
       around every full reference entry, pointing back at the
       Zotero anchor) is REMOVED. References should read as plain
       prose, not a clickable Zotero hyperlink.

    2. The DOI URL inside each reference (https://doi.org/...) is
       PROMOTED to its own <a class="doi"> link. The stylesheet
       paints these in brand maroon while the rest of the reference
       stays grey.

  Activates ONLY inside the References section. We detect it by
  finding the Header with text "References" / "Bibliography" /
  "Works Cited" (case-insensitive) and applying the rewrite to every
  Para that follows, until the next Header at the same or lower
  level (i.e., a new section).

  Usage:  pandoc … --lua-filter=paper/filters/refs_dois.lua

  Tested with pandoc 3.x (via pypandoc-binary 1.17).
]]--

local in_refs = false
local refs_header_level = nil
local doi_pattern = "https?://doi%.org/[^%s%)%]]+"

-- Match the heading text against the section names we treat as
-- "References". Lower-cased + stripped of surrounding whitespace.
local function is_refs_heading(header)
  local s = pandoc.utils.stringify(header):lower():gsub("^%s+", ""):gsub("%s+$", "")
  return s == "references"
    or s == "bibliography"
    or s == "works cited"
    or s == "literature cited"
end

-- Walk all inlines in `inlines` (a List or table). For each Link,
-- check if its inner text contains a DOI. If so, replace it with
-- the inner text (as Str inlines) plus a fresh Link wrapping just
-- the DOI URL.
local function rewrite_refs_inlines(inlines)
  local out = {}
  for _, inline in ipairs(inlines) do
    if inline.t == "Link" then
      local inner_text = pandoc.utils.stringify(inline)
      local doi_start, doi_end = inner_text:find(doi_pattern)
      if doi_start then
        local pre = inner_text:sub(1, doi_start - 1)
        local doi = inner_text:sub(doi_start, doi_end)
        local post = inner_text:sub(doi_end + 1)
        if #pre > 0 then
          table.insert(out, pandoc.Str(pre))
        end
        local doi_link = pandoc.Link({pandoc.Str(doi)}, doi)
        doi_link.attr.classes:insert("doi")
        table.insert(out, doi_link)
        if #post > 0 then
          table.insert(out, pandoc.Str(post))
        end
      else
        -- No DOI inside this link — unwrap to plain text. The
        -- outer Zotero link target isn't useful to readers (it
        -- points at a Zotero anchor, not a citeable resource).
        for _, sub in ipairs(inline.content) do
          table.insert(out, sub)
        end
      end
    else
      table.insert(out, inline)
    end
  end
  return out
end

function Header(elem)
  if is_refs_heading(elem) then
    in_refs = true
    refs_header_level = elem.level
  elseif in_refs and refs_header_level ~= nil and elem.level <= refs_header_level then
    -- A heading at the same or higher level ends the references
    -- section (e.g. the next top-level section appears).
    in_refs = false
    refs_header_level = nil
  end
  return elem
end

function Para(elem)
  if not in_refs then
    return elem
  end
  return pandoc.Para(rewrite_refs_inlines(elem.content))
end
