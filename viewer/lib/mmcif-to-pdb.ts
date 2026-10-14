/**
 * Convert an RCSB mmCIF file into legacy PDB-format text.
 *
 * RCSB publishes no `.pdb` download for entries that can't be expressed
 * in the fixed-column format — a 5-character CCD ligand code (9V8W's
 * `A1D9S`), a multi-character chain id, more than 99,999 atoms. Those
 * entries carry `pdb_format_compatible: N` and `files.rcsb.org/download/
 * {ID}.pdb` 404s, while the `.cif` is always there. The structure viewer's
 * chain picker, residue projection and membrane orientation all read
 * fixed PDB columns, so rather than teach each of them mmCIF, the viewer
 * converts the `.cif` here and hands the rest of the pipeline the same
 * text shape it already handles.
 *
 * Only what the viewer consumes is emitted: a TITLE block plus ATOM /
 * HETATM records for the first model, in author numbering (auth_seq_id,
 * auth_asym_id, auth_comp_id — the numbering the legacy `.pdb` uses).
 * Values that don't fit their PDB columns are squeezed: residue names
 * longer than 3 characters are truncated (they are ligands, which the
 * viewer never styles), and multi-character chain ids are remapped onto
 * unused single characters, returned in `chainMap` so the caller can
 * translate a PDBe chain id into the one the converted text uses.
 */

export interface MmcifToPdbResult {
  pdb: string;
  /** Original auth_asym_id → single-character chain id in `pdb`.
   *  Identity for ids that were already one character. */
  chainMap: Record<string, string>;
}

/** Split one mmCIF data line into tokens. A quoted token ends at a
 *  matching quote followed by whitespace or end-of-line, so atom names
 *  like `"C1'"` keep their embedded prime. */
function _tokenize(line: string): string[] {
  const out: string[] = [];
  const re = /'(.*?)'(?=\s|$)|"(.*?)"(?=\s|$)|(\S+)/g;
  let m: RegExpExecArray | null;
  while ((m = re.exec(line)) !== null) {
    out.push(m[1] ?? m[2] ?? m[3]);
  }
  return out;
}

/** `_struct.title`, either inline (`_struct.title 'text'`) or as the
 *  next line / a `;`-delimited text block. */
function _structTitle(lines: string[]): string | null {
  for (let i = 0; i < lines.length; i += 1) {
    const line = lines[i];
    if (!line.startsWith("_struct.title")) continue;
    const rest = line.slice("_struct.title".length).trim();
    if (rest) return _tokenize(rest).join(" ");
    const next = lines[i + 1] ?? "";
    if (!next.startsWith(";")) return _tokenize(next).join(" ") || null;
    const block = [next.slice(1)];
    for (let j = i + 2; j < lines.length && !lines[j].startsWith(";"); j += 1) {
      block.push(lines[j]);
    }
    return block.join(" ").replace(/\s+/g, " ").trim() || null;
  }
  return null;
}

/** TITLE records, 60 characters of text per line, with the continuation
 *  number in cols 9-10 from the second line on. */
function _titleRecords(title: string): string[] {
  const words = title.replace(/\s+/g, " ").trim().split(" ");
  const chunks: string[] = [];
  let cur = "";
  for (const w of words) {
    if (cur && cur.length + 1 + w.length > 60) {
      chunks.push(cur);
      cur = w;
    } else {
      cur = cur ? `${cur} ${w}` : w;
    }
  }
  if (cur) chunks.push(cur);
  return chunks.map((c, i) =>
    i === 0 ? `TITLE     ${c}` : `TITLE   ${String(i + 1).padStart(2)} ${c}`,
  );
}

const _CHAIN_POOL =
  "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789";

/** PDB atom-name columns 13-16: a 1-letter element's name starts in
 *  col 14, so short names get a leading space. */
function _atomNameField(name: string, element: string): string {
  if (name.length >= 4) return name.slice(0, 4);
  return element.length === 1 ? ` ${name.padEnd(3)}` : name.padEnd(4);
}

function _fixed(n: number, width: number, decimals: number): string {
  return n.toFixed(decimals).padStart(width).slice(-width);
}

/**
 * @param cif  mmCIF text as served by `files.rcsb.org/download/{ID}.cif`
 *   or by the RCSB ModelServer.
 * @param opts.preferredChainId  chain the caller will select on. When
 *   chains have to be remapped it is assigned first, so it can never fall
 *   off the end of the single-character pool.
 * @param opts.title  TITLE text to emit when the file carries no
 *   `_struct.title` (ModelServer slices don't).
 */
export function mmcifToPdb(
  cif: string,
  opts: { preferredChainId?: string; title?: string | null } = {},
): MmcifToPdbResult {
  const { preferredChainId } = opts;
  const lines = cif.split(/\r?\n/);

  // Locate the atom_site loop: its `_atom_site.*` header lines, then
  // data rows until the next loop / category / blank-comment line.
  const cols: string[] = [];
  let i = 0;
  for (; i < lines.length; i += 1) {
    if (lines[i].startsWith("_atom_site.")) break;
  }
  for (; i < lines.length && lines[i].startsWith("_atom_site."); i += 1) {
    cols.push(lines[i].trim().slice("_atom_site.".length));
  }
  const col = (name: string) => cols.indexOf(name);
  const idx = {
    group: col("group_PDB"),
    element: col("type_symbol"),
    atom: col("auth_atom_id") >= 0 ? col("auth_atom_id") : col("label_atom_id"),
    alt: col("label_alt_id"),
    comp: col("auth_comp_id") >= 0 ? col("auth_comp_id") : col("label_comp_id"),
    chain: col("auth_asym_id") >= 0 ? col("auth_asym_id") : col("label_asym_id"),
    seq: col("auth_seq_id") >= 0 ? col("auth_seq_id") : col("label_seq_id"),
    ins: col("pdbx_PDB_ins_code"),
    x: col("Cartn_x"),
    y: col("Cartn_y"),
    z: col("Cartn_z"),
    occ: col("occupancy"),
    b: col("B_iso_or_equiv"),
    charge: col("pdbx_formal_charge"),
    model: col("pdbx_PDB_model_num"),
  };

  type Row = string[];
  const rows: Row[] = [];
  let firstModel: string | null = null;
  for (; i < lines.length; i += 1) {
    const line = lines[i];
    if (line.startsWith("#") || line.startsWith("_") || line.startsWith("loop_")) {
      break;
    }
    if (!line.trim()) continue;
    const t = _tokenize(line);
    if (t.length < cols.length) continue;
    if (idx.model >= 0) {
      firstModel ??= t[idx.model];
      if (t[idx.model] !== firstModel) continue;
    }
    rows.push(t);
  }

  // Chain remap. Single-character ids keep their name; longer ones take
  // the next unused pool character, preferred chain first.
  const chainsInOrder: string[] = [];
  const seen = new Set<string>();
  for (const r of rows) {
    const c = r[idx.chain];
    if (!seen.has(c)) {
      seen.add(c);
      chainsInOrder.push(c);
    }
  }
  if (preferredChainId && seen.has(preferredChainId)) {
    chainsInOrder.splice(chainsInOrder.indexOf(preferredChainId), 1);
    chainsInOrder.unshift(preferredChainId);
  }
  const chainMap: Record<string, string> = {};
  const used = new Set(chainsInOrder.filter((c) => c.length === 1));
  const pool = [..._CHAIN_POOL].filter((c) => !used.has(c));
  for (const c of chainsInOrder) {
    if (c.length === 1) chainMap[c] = c;
    else if (pool.length > 0) chainMap[c] = pool.shift() as string;
    // Pool exhausted: the chain is dropped rather than collided onto
    // another chain's id.
  }

  const out = _titleRecords(_structTitle(lines) ?? opts.title ?? "");
  let serial = 0;
  const val = (r: Row, k: number) => (k >= 0 && r[k] !== "?" && r[k] !== "." ? r[k] : "");
  for (const r of rows) {
    const chain = chainMap[r[idx.chain]];
    if (!chain) continue;
    serial += 1;
    const record = (val(r, idx.group) || "ATOM").padEnd(6).slice(0, 6);
    const element = val(r, idx.element).toUpperCase();
    const charge = val(r, idx.charge);
    const chargeField =
      charge && charge !== "0"
        ? `${charge.replace(/^[+-]/, "")}${charge.startsWith("-") ? "-" : "+"}`
        : "  ";
    out.push(
      record +
        String(serial % 100000).padStart(5) +
        " " +
        _atomNameField(val(r, idx.atom), element) +
        (val(r, idx.alt) || " ").slice(0, 1) +
        val(r, idx.comp).slice(0, 3).padStart(3) +
        " " +
        chain +
        val(r, idx.seq).padStart(4).slice(-4) +
        (val(r, idx.ins) || " ").slice(0, 1) +
        "   " +
        _fixed(Number(r[idx.x]), 8, 3) +
        _fixed(Number(r[idx.y]), 8, 3) +
        _fixed(Number(r[idx.z]), 8, 3) +
        _fixed(Number(val(r, idx.occ) || "1"), 6, 2) +
        _fixed(Number(val(r, idx.b) || "0"), 6, 2) +
        "          " +
        element.padStart(2).slice(-2) +
        chargeField.slice(0, 2),
    );
  }
  out.push("END");
  return { pdb: `${out.join("\n")}\n`, chainMap };
}
