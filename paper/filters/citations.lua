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

-- ── Phase 3: front-matter resource row ───────────────────────────
--
-- The .docx lists the project's resources as four paragraphs stranded
-- after the abstract, each printing a full raw URL:
--
--     Viewer: surfaceome.deliverome.org
--     Code (GitHub): https://github.com/Deliverome-Project/accessible-…
--     Code (Zenodo): https://doi.org/10.5281/zenodo.22116981
--     Data: https://zenodo.org/records/20805383
--
-- Long URLs read badly in a justified column and say nothing a reader
-- can act on. This collapses them into ONE row of brand-marked links
-- placed directly under the corresponding-author line, where readers
-- look for a paper's resources.
--
-- Order and labels are driven by the prefix each paragraph starts
-- with, so re-ordering them in the .docx re-orders the row.
local RESOURCE_LINES = {
  {prefix = "code (zenodo)", icon = "zenodo.svg", label = "Code DOI"},
  {prefix = "code (github)", icon = "github.svg", label = "Code"},
  {prefix = "code:",         icon = "github.svg", label = "Code"},
  {prefix = "data:",         icon = "zenodo.svg", label = "Data"},
  {prefix = "viewer:",       icon = "viewer.svg", label = "Viewer"},
}

local ASSETS_DIR = os.getenv("PAPER_ASSETS_DIR")
-- Set by build.py only for the web build: bioRxiv and the PDF download
-- belong on the page, not inside the PDF itself.
local WEB_EXTRAS = os.getenv("PAPER_WEB_EXTRAS")

local function classify(text)
  local lower = text:lower():gsub("^%s+", "")
  for _, rule in ipairs(RESOURCE_LINES) do
    if lower:sub(1, #rule.prefix) == rule.prefix then return rule end
  end
  return nil
end

-- First link target inside a block — the URL the paragraph points at.
local function first_url(blk)
  local found = nil
  pandoc.walk_block(blk, {
    Link = function(l)
      if not found then found = l.target end
    end,
  })
  return found
end

local function icon_link(icon, label, url)
  local inlines = pandoc.List({})
  -- bioRxiv is set as TEXT, not an image. An SVG wordmark built from
  -- <text> is font-dependent, and a browser loading it through <img>
  -- isolates it from the page's fonts — so it rendered inconsistently
  -- and sometimes not at all. Typesetting it inline uses the page's
  -- own font and lets CSS colour the capital R, which is the whole of
  -- the mark's identity.
  if label == "bioRxiv" then
    -- Real bioRxiv logo (the official public-domain wordmark lockup),
    -- sized down in CSS. A fixed image reads as the brand and — unlike
    -- the old typeset wordmark — doesn't depend on the page's fonts.
    local src = ASSETS_DIR and (ASSETS_DIR .. "/biorxiv_logo.png")
      or "biorxiv_logo.png"
    local logo = pandoc.Image(
      {pandoc.Str("bioRxiv")}, src, "",
      pandoc.Attr("", {"resource-biorxiv-logo"})
    )
    return pandoc.Link(
      {logo}, url, "", pandoc.Attr("", {"resource-link", "resource-biorxiv"})
    )
  end
  if icon and ASSETS_DIR then
    inlines:insert(pandoc.Image(
      {pandoc.Str(label)},
      ASSETS_DIR .. "/" .. icon,
      "",
      pandoc.Attr("", {"resource-icon"})
    ))
    inlines:insert(pandoc.Space())
  end
  inlines:insert(pandoc.Str(label))
  return pandoc.Link(inlines, url, "", pandoc.Attr("", {"resource-link"}))
end

local function build_resource_row(doc)
  local collected = {}
  local kept = pandoc.List({})
  local anchor_at = nil

  for _, blk in ipairs(doc.blocks) do
    local text = (blk.t == "Para" or blk.t == "Plain")
      and pandoc.utils.stringify(blk) or ""
    local rule = (text ~= "") and classify(text) or nil
    if rule then
      local url = first_url(blk)
      if url then
        collected[#collected + 1] = {rule = rule, url = url}
      else
        kept:insert(blk)  -- no link to hang the row off; leave as prose
      end
    else
      kept:insert(blk)
      if anchor_at == nil and text:lower():find("corresponding author") then
        anchor_at = #kept
      end
    end
  end

  if #collected == 0 then return doc end

  local row = pandoc.List({})
  if WEB_EXTRAS then
    -- Web only, and FIRST in the row: on the page these are the two
    -- things a reader most wants (the preprint of record, and a copy
    -- to keep). Neither belongs inside the PDF.
    row:insert(icon_link("biorxiv.svg", "bioRxiv", WEB_EXTRAS))
    row:insert(pandoc.Space())
    row:insert(icon_link(nil, "Download PDF",
      "accessible-human-surfaceome.pdf"))
    row:insert(pandoc.Space())
  end
  for i, item in ipairs(collected) do
    if i > 1 or WEB_EXTRAS then row:insert(pandoc.Space()) end
    row:insert(icon_link(item.rule.icon, item.rule.label, item.url))
  end

  local row_div = pandoc.Div(
    {pandoc.Para(row)}, pandoc.Attr("", {"resource-row"})
  )
  -- Slot it under the corresponding-author line; if that line isn't
  -- found, fall back to leaving the row where the first entry was.
  local out = pandoc.List({})
  for i, blk in ipairs(kept) do
    out:insert(blk)
    if i == anchor_at then out:insert(row_div) end
  end
  if anchor_at == nil then out:insert(row_div) end
  doc.blocks = out
  return doc
end

return {
  {Pandoc = index_references},
  {Link = rewrite_citation},
  {Pandoc = build_resource_row},
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
