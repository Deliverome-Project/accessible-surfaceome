--[[
  paper/filters/citations.lua

  Turns Zotero's in-text citations into real cross-references.

  The .docx comes out of Google Docs, where Zotero wraps every
  in-text citation in a link back to its own service:

      <a href="https://www.zotero.org/google-docs/?m7oWBb">(Brase, 2009)</a>

  Two problems with shipping that as-is:

  1. **The link goes nowhere useful.** zotero.org/google-docs/?KEY
     is an internal Zotero anchor, not a citeable resource. A reader
     clicking a citation in the PDF lands on a Zotero page that
     means nothing to them.

  2. **The parentheses are inside the link**, so the whole
     "(Brase, 2009)" — brackets included — gets painted in link
     maroon. Typographically the brackets belong to the sentence,
     not to the citation.

  This filter fixes both: it re-points each citation at the matching
  entry in the References section, and re-emits the brackets OUTSIDE
  the link so only the author-year text carries colour.

      (<a href="#ref-brase-2009">Brase, 2009</a>)

  Matching is by (first-author surname, year), parsed from both
  sides:

    reference entry   "Balbi, P.E.M., Sadek, A., …, 2026. Mapping…"
                      → author "Balbi", year "2026"
    in-text citation  "(Balbi et al., 2026)"
                      → author "Balbi", year "2026"

  Handled shapes, all of which occur in the current draft:

    (Brase, 2009)                     single author
    (Loes et al., 2021)               et al.
    (UniProt Consortium, 2025)        corporate author
    (van Oostrum et al., 2019)        lowercase particle in surname
    (A et al., 2025; B et al., 2020)  several citations, split on ';'
    (Piwowar et al., 2019, 2018)      ONE author, TWO years → two links
    ("Plasma membrane (HPA)," n.d.)   quoted title as author, no date,
                                      and nested brackets in the name

  A citation that matches no reference is left as PLAIN TEXT and
  reported on stderr. A dead in-document anchor is worse than an
  unlinked citation, so this never guesses.

  Must run AFTER refs_dois.lua, which unwraps Zotero's outer link
  around each *reference entry* — otherwise the reference paragraphs
  still look like citations.

  Usage:  pandoc … --lua-filter=paper/filters/citations.lua
]]--

-- key "surname|year" → anchor id
local ref_ids = {}
-- Diagnostics.
local unmatched = {}
local matched_count = 0

local function is_refs_heading(header)
  local s = pandoc.utils.stringify(header):lower()
    :gsub("^%s+", ""):gsub("%s+$", "")
  -- "Supplementary References" counts too. Miss it and that section's
  -- entries keep their Zotero wrappers, which citations.lua then reads
  -- as in-text citations — producing nonsense keys off page numbers
  -- ("… Brunak, S. 1005") and leaving real citations unlinked.
  s = s:gsub("^supplementary%s+", ""):gsub("^supplemental%s+", "")
  return s == "references" or s == "bibliography"
    or s == "works cited" or s == "literature cited"
end

-- Normalise an author string for matching: lowercase, drop the
-- decorations that differ between a reference entry and an in-text
-- citation ("et al.", "[WWW Document]", curly quotes, stray commas),
-- collapse whitespace.
local function norm_author(s)
  s = s:lower()
  s = s:gsub("%[www document%]", "")
  s = s:gsub("et%s+al%.?", "")
  -- Curly and straight quotes, and the comma Zotero leaves inside
  -- a quoted title ("Plasma membrane (HPA)," n.d.).
  s = s:gsub("[\u{201C}\u{201D}\u{2018}\u{2019}\"']", "")
  s = s:gsub("[,%.]%s*$", "")
  -- Strip only UNBALANCED brackets. Zotero occasionally leaves the
  -- closing ")" outside the <a> it wraps, so a group can arrive as
  -- "(Westergaard et al., 2018" — the outer-bracket peel below can't
  -- fire on that, and the "(" would ride into the lookup key and fail
  -- to match a perfectly good reference.
  --
  -- Balanced brackets must SURVIVE, because a bracket can be part of
  -- the name itself: "Plasma membrane (HPA)" is a real reference whose
  -- key needs its "(HPA)" intact. Count first, strip only the excess.
  local opens = select(2, s:gsub("%(", ""))
  local closes = select(2, s:gsub("%)", ""))
  if opens > closes then
    s = s:gsub("^%(", "", opens - closes)
  elseif closes > opens then
    for _ = 1, closes - opens do s = s:gsub("%)%s*$", "") end
  end
  s = s:gsub("^%[+", ""):gsub("%]+$", "")
  s = s:gsub("^%s+", ""):gsub("%s+$", "")
  s = s:gsub("%s+", " ")
  return s
end

-- Slugify for use in an HTML id.
local function slug(s)
  s = s:lower():gsub("[^%w]+", "-"):gsub("^%-+", ""):gsub("%-+$", "")
  return s
end

-- Pull (author, year) out of a REFERENCE entry.
--
-- Entries are author-date style: the author list runs up to the
-- first comma, and the year is the first ", NNNN." or ", n.d."
-- group. Anchoring the year on that trailing period matters —
-- a bare %d%d%d%d would happily match a volume or page number
-- later in the citation ("Nucleic Acids Res. 54, D1779–D1792").
local function parse_reference(text)
  local year = text:match(",%s*(%d%d%d%d)%.")
  if not year and text:match(",%s*n%.d%.") then year = "n.d." end
  if not year then return nil end
  local author = text:match("^(.-),")
  if not author then return nil end
  return norm_author(author), year
end

-- Pull the citations out of one in-text group (already stripped of
-- its outer brackets and split on ';'). Returns a list of
-- {author=, years={...}} — `years` has more than one entry only for
-- the "(Piwowar et al., 2019, 2018)" shape.
local function parse_citation_part(part)
  part = part:gsub("^%s+", ""):gsub("%s+$", "")
  if part == "" then return nil end

  local years, first_at = {}, nil
  -- n.d. is a year for our purposes.
  local nd_at = part:find("n%.d%.")
  for y_start, y in part:gmatch("()(%d%d%d%d)") do
    years[#years + 1] = {year = y, pos = y_start}
    if not first_at then first_at = y_start end
  end
  if nd_at and #years == 0 then
    years[1] = {year = "n.d.", pos = nd_at}
    first_at = nd_at
  end
  if #years == 0 then return nil end

  local author = norm_author(part:sub(1, first_at - 1))
  if author == "" then return nil end
  return {author = author, years = years, text = part, first_at = first_at}
end

-- ── Phase 1: index the References section, and anchor each entry ──

-- Register one reference block (a Para/Plain holding the entry text)
-- and return it with an anchor Span prepended, or unchanged when it
-- doesn't parse as a reference.
local function anchor_reference_block(b)
  if b.t ~= "Para" and b.t ~= "Plain" then return b end
  local author, year = parse_reference(pandoc.utils.stringify(b))
  if not (author and year) then return b end
  local key = author .. "|" .. year
  -- First entry wins; a duplicate key means two references that
  -- genuinely collide, which the author has to disambiguate.
  if ref_ids[key] then return b end
  local id = "ref-" .. slug(author) .. "-" .. slug(year)
  ref_ids[key] = id
  local inlines = pandoc.List({pandoc.Span({}, pandoc.Attr(id))})
  for _, inl in ipairs(b.content) do inlines:insert(inl) end
  return (b.t == "Para") and pandoc.Para(inlines) or pandoc.Plain(inlines)
end

-- Zotero writes the bibliography as a LIST, not as loose paragraphs
-- (pandoc reads it as an OrderedList whose items each hold one
-- reference Para). An earlier version only looked at top-level
-- Para/Plain and silently indexed nothing, which left every citation
-- unlinked — so handle both shapes.
local function anchor_reference_container(b)
  if b.t == "OrderedList" or b.t == "BulletList" then
    local items = {}
    for _, item in ipairs(b.content) do
      local new_item = {}
      for _, sub in ipairs(item) do
        new_item[#new_item + 1] = anchor_reference_block(sub)
      end
      items[#items + 1] = new_item
    end
    if b.t == "OrderedList" then
      return pandoc.OrderedList(items, b.listAttributes)
    end
    return pandoc.BulletList(items)
  end
  return anchor_reference_block(b)
end

local function index_references(doc)
  local blocks = doc.blocks
  local in_refs, refs_level = false, nil
  for i = 1, #blocks do
    local b = blocks[i]
    if b.t == "Header" then
      if is_refs_heading(b) then
        in_refs, refs_level = true, b.level
      elseif in_refs and b.level <= (refs_level or 1) then
        in_refs = false
      end
    elseif in_refs then
      blocks[i] = anchor_reference_container(b)
    end
  end
  doc.blocks = blocks
  return doc
end

-- ── Phase 2: rewrite the in-text citation links ──────────────────

local function lookup(author, year)
  return ref_ids[author .. "|" .. year]
end

-- Build the inlines for one citation part, linking what we can.
local function render_part(p)
  local out = pandoc.List({})
  if not p then return out end

  local first = p.years[1]
  local head_end = first.pos + #first.year - 1
  local head_text = p.text:sub(1, head_end)
  local id = lookup(p.author, first.year)
  if id then
    out:insert(pandoc.Link({pandoc.Str(head_text)}, "#" .. id))
    matched_count = matched_count + 1
  else
    out:insert(pandoc.Str(head_text))
    unmatched[#unmatched + 1] = p.author .. " " .. first.year
  end

  -- Trailing extra years belong to the same author.
  local cursor = head_end + 1
  for i = 2, #p.years do
    local y = p.years[i]
    local between = p.text:sub(cursor, y.pos - 1)
    if #between > 0 then out:insert(pandoc.Str(between)) end
    local yid = lookup(p.author, y.year)
    if yid then
      out:insert(pandoc.Link({pandoc.Str(y.year)}, "#" .. yid))
      matched_count = matched_count + 1
    else
      out:insert(pandoc.Str(y.year))
      unmatched[#unmatched + 1] = p.author .. " " .. y.year
    end
    cursor = y.pos + #y.year
  end
  local tail = p.text:sub(cursor)
  if #tail > 0 then out:insert(pandoc.Str(tail)) end
  return out
end

local function rewrite_citation(link)
  local target = link.target or ""
  if not target:find("zotero%.org") then return nil end

  local text = pandoc.utils.stringify(link)
  -- Peel the outer brackets off so they can be re-emitted OUTSIDE
  -- the link. Zotero always brackets the whole group; a citation
  -- without them (a narrative "Loes et al. (2021)") just keeps
  -- whatever it had.
  local open, inner, close = text:match("^(%()(.*)(%))$")
  if not open then
    open, inner, close = "", text, ""
  end

  local out = pandoc.List({})
  if open ~= "" then out:insert(pandoc.Str(open)) end

  -- Split the group on ';' — each piece is its own citation.
  local pieces, last = {}, 1
  while true do
    local s, e = inner:find(";", last, true)
    if not s then
      pieces[#pieces + 1] = inner:sub(last)
      break
    end
    pieces[#pieces + 1] = inner:sub(last, s - 1)
    last = e + 1
  end

  for i, piece in ipairs(pieces) do
    if i > 1 then out:insert(pandoc.Str("; ")) end
    local parsed = parse_citation_part(piece)
    if parsed then
      for _, inl in ipairs(render_part(parsed)) do out:insert(inl) end
    else
      -- Unparseable — keep the original text rather than dropping it.
      out:insert(pandoc.Str((piece:gsub("^%s+", ""):gsub("%s+$", ""))))
    end
  end

  if close ~= "" then out:insert(pandoc.Str(close)) end
  return out
end

-- ── Phase 3: tag the front-matter resource lines ─────────────────
--
-- "Viewer: …", "Code (GitHub): …", "Data: …" are ordinary <p>s, so
-- they inherit the body's justified text. Justification stretches
-- the space between the short label and a long raw URL into a
-- ragged gap. Tag them so the stylesheet can set them left-aligned
-- and let the URL wrap on its own terms.
-- Each entry: prefix the line must start with (lower-cased), and the
-- icon file in paper/assets/ to set beside it. Order matters —
-- "code (zenodo)" must be tested before "code (" so the GitHub icon
-- doesn't win both Code lines.
local RESOURCE_LINES = {
  {prefix = "code (zenodo)", icon = "zenodo.svg", alt = "Zenodo"},
  {prefix = "code (github)", icon = "github.svg", alt = "GitHub"},
  {prefix = "code:",         icon = "github.svg", alt = "GitHub"},
  {prefix = "data:",         icon = "zenodo.svg", alt = "Zenodo"},
  -- The viewer line gets a mark too, purely so all four labels share
  -- a left edge: without one, "Viewer:" starts at the margin while the
  -- icon-bearing labels are pushed right, and the block reads ragged.
  {prefix = "viewer:",       icon = "viewer.svg", alt = "Web viewer"},
}

-- build.py exports this so the filter can emit absolute image paths.
-- WeasyPrint resolves <img src> against the HTML's directory (the
-- build/ dir next to the .docx), which is nowhere near paper/assets/,
-- so a relative path would silently fail to load.
local ASSETS_DIR = os.getenv("PAPER_ASSETS_DIR")

local function tag_resource_line(elem)
  local text = pandoc.utils.stringify(elem):lower():gsub("^%s+", "")
  for _, rule in ipairs(RESOURCE_LINES) do
    if text:sub(1, #rule.prefix) == rule.prefix then
      local content = elem.content
      if rule.icon and ASSETS_DIR then
        local img = pandoc.Image(
          {pandoc.Str(rule.alt)},
          ASSETS_DIR .. "/" .. rule.icon,
          "",
          pandoc.Attr("", {"resource-icon"})
        )
        local inlines = pandoc.List({img, pandoc.Space()})
        for _, inl in ipairs(content) do inlines:insert(inl) end
        content = inlines
      end
      return pandoc.Div(
        {pandoc.Para(content)}, pandoc.Attr("", {"resource-line"})
      )
    end
  end
  return nil
end

return {
  {Pandoc = index_references},
  {Link = rewrite_citation},
  {Para = tag_resource_line},
  {
    Pandoc = function(doc)
      io.stderr:write(("citations.lua: linked %d citation(s) to %d reference(s).\n")
        :format(matched_count, (function()
          local n = 0; for _ in pairs(ref_ids) do n = n + 1 end; return n
        end)()))
      if #unmatched > 0 then
        local seen, uniq = {}, {}
        for _, u in ipairs(unmatched) do
          if not seen[u] then seen[u] = true; uniq[#uniq + 1] = u end
        end
        io.stderr:write(("citations.lua: %d citation(s) matched NO reference and were "):format(#uniq)
          .. "left as plain text: " .. table.concat(uniq, "; ") .. "\n")
      end
      return doc
    end,
  },
}
