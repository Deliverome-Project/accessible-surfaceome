--[[
  paper/filters/breakable_identifiers.lua

  Pandoc Lua filter that lets snake_case identifiers wrap at their
  underscores.

  The Methods name pipeline stages, fields and enum values verbatim
  (plan_trim_select, executive_summary, direct_multi_method, …). Each is
  one unbreakable word to the line breaker, and hyphenation never splits
  them, so in a justified two-column page the line before one stretches
  into wide word gaps, or the identifier overflows the column. A <wbr>
  after each underscore gives the breaker a place to wrap without
  inserting a hyphen, and changes nothing when the word fits.

  HTML output only (print + web builds); other writers pass through.

  Tables are skipped. A break opportunity inside a table cell (a <wbr>
  or even a zero-width space) makes WeasyPrint silently drop every page
  after a column-spanning table — the PDF just ends there — and table
  cells wrap their codes acceptably without help.

  Usage:  pandoc … --lua-filter=paper/filters/breakable_identifiers.lua
]]--

local function is_html(format)
  return format:match("html") ~= nil
end

-- An identifier: at least one underscore with a word character on each
-- side, so stray "_" and Markdown-ish emphasis markers are left alone.
local function has_identifier(text)
  return text:find("[%w]_[%w]") ~= nil
end

local function break_identifier(elem)
  if not has_identifier(elem.text) then
    return nil
  end
  local out = {}
  local start = 1
  for pos in elem.text:gmatch("()_") do
    out[#out + 1] = pandoc.Str(elem.text:sub(start, pos))
    out[#out + 1] = pandoc.RawInline("html", "<wbr>")
    start = pos + 1
  end
  if start <= #elem.text then
    out[#out + 1] = pandoc.Str(elem.text:sub(start))
  end
  return out
end

function Pandoc(doc)
  if not is_html(FORMAT) then
    return nil
  end
  local blocks = {}
  for _, block in ipairs(doc.blocks) do
    if block.t == "Table" then
      blocks[#blocks + 1] = block
    else
      blocks[#blocks + 1] = block:walk({ Str = break_identifier })
    end
  end
  doc.blocks = blocks
  return doc
end
