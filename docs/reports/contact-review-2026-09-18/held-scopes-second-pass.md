# Held scopes: focused second pass

All five scopes support narrow engineered-construct rules. Each matches exactly one original observation. The two ACE deposits remain separate; APP fragment evidence does not establish intact cell-surface APP binding.

## 5AM8

Verified against P12821 residues [30, 658]: N38Q, N54Q, N111Q, N146Q, N318Q, Q574R, P605L, R658L. These are UniProt positions, corroborated by DBREF/SEQADV.

Engineered 629-residue ACE N-domain, P12821 residues 30–658, with verified UniProt-numbered deposited substitutions N38Q, N54Q, N111Q, N146Q, N318Q, Q574R, P605L, R658L. Primary paper uses minimally glycosylated Ndom389, but the two deposits differ at P12821 position 160; do not assert identical construct identity. APP target is Aβ(4–10), not intact cell-surface APP; header reports only Asp7–Ser8 visible. Primary study: https://pmc.ncbi.nlm.nih.gov/articles/PMC4950319/

5AM8 has N160; 5AMB has Q160. The paper uses Ndom389 for crystallization; preserve deposited discrepancy without inferring different wet-lab preparations.
5AMB COMPND interval 30–657 conflicts with DBREF and 629-residue sequence mapping 30–658.

Sources: [PDB header](https://files.rcsb.org/header/5AM8.pdb), [stable UniProt FASTA](https://rest.uniprot.org/uniprotkb/P12821.fasta), [primary paper](https://pmc.ncbi.nlm.nih.gov/articles/PMC4950319/).

## 5AMB

Verified against P12821 residues [30, 658]: N38Q, N54Q, N111Q, N146Q, N160Q, N318Q, Q574R, P605L, R658L. These are UniProt positions, corroborated by DBREF/SEQADV.

Engineered 629-residue ACE N-domain, P12821 residues 30–658, with verified UniProt-numbered deposited substitutions N38Q, N54Q, N111Q, N146Q, N160Q, N318Q, Q574R, P605L, R658L. Primary paper uses minimally glycosylated Ndom389, but the two deposits differ at P12821 position 160; do not assert identical construct identity. APP target is Aβ(35–42), not intact cell-surface APP; header reports only Ile41–Ala42 visible. Primary study: https://pmc.ncbi.nlm.nih.gov/articles/PMC4950319/

5AM8 has N160; 5AMB has Q160. The paper uses Ndom389 for crystallization; preserve deposited discrepancy without inferring different wet-lab preparations.
5AMB COMPND interval 30–657 conflicts with DBREF and 629-residue sequence mapping 30–658.

Sources: [PDB header](https://files.rcsb.org/header/5AMB.pdb), [stable UniProt FASTA](https://rest.uniprot.org/uniprotkb/P12821.fasta), [primary paper](https://pmc.ncbi.nlm.nih.gov/articles/PMC4950319/).

## 2WK3

Verified against P14735 residues [1, 1019]: C110L, E111Q, C171S, C178A, C257V, C414L, C573N, C590S, C789S, C812A, C819A, C904S, C966N, C974A. These are UniProt positions, corroborated by DBREF/SEQADV.

Important precision: 13 cysteines are substituted plus E111Q, but C32 remains in the full deposited 1019-residue sequence. The proposed name therefore says cysteine-substituted, not literally cysteine-free. It must not merge with E111Q-only constructs.

Deposited IDE sequence has 13 cysteine substitutions plus E111Q: C110L, E111Q, C171S, C178A, C257V, C414L, C573N, C590S, C789S, C812A, C819A, C904S, C966N, C974A, in verified P14735 numbering. The 1019-residue deposited polymer still contains C32; avoid claiming this entire deposited polymer literally lacks cysteine. Keep separate from E111Q-only IDE. Target is Aβ(1–42), P05067 residues 672–713, not intact cell-surface APP. Primary citation: https://pmc.ncbi.nlm.nih.gov/articles/PMC2813390/

The experimental cysteine-free nomenclature must not imply zero cysteines in the complete deposited sequence: C32 remains. No expression processing/numbering assumption is needed for the proposed label.
Primary full-text endpoint intermittently returned a browser challenge; exact substitutions are supported by deposit plus reference sequence.

Sources: [PDB header](https://files.rcsb.org/header/2WK3.pdb), [stable UniProt FASTA](https://rest.uniprot.org/uniprotkb/P14735.fasta), [primary paper](https://pmc.ncbi.nlm.nih.gov/articles/PMC2813390/).

## 3S4S

Verified against P01730 residues [26, 203]: Q65Y, T70W. These are UniProt positions, corroborated by DBREF/SEQADV.

Deposited/paper Q40Y/T45W corresponds to UniProt Q65Y/T70W. The null mutation flag was misleading: SEQADV records conflicts. The core is 178 residues with DLGS and AAAHHHHHH tags (191 total). Both HLA target scopes receive the same PDB-qualified experimental-tool label.

Affinity-engineered CD4 D1–D2 double mutant. Deposited Q40Y/T45W explicitly maps to UniProt P01730 Q65Y/T70W. Core residues 26–203 (178 residues) plus DLGS and AAAHHHHHH tags give 191 residues. SEQADV calls these changes CONFLICT despite the missing mutation flag. Preserve HLA-DR1/hemagglutinin-peptide context and distinction from 3S5L four-mutation and 3T0E longer constructs; not wild-type CD4. Primary study: https://pmc.ncbi.nlm.nih.gov/articles/PMC3179091/

HLA beta entity maps to allele-specific P04229 in the header while supplied target is P01911; partner annotation does not alter target mapping.

Sources: [PDB header](https://files.rcsb.org/header/3S4S.pdb), [stable UniProt FASTA](https://rest.uniprot.org/uniprotkb/P01730.fasta), [primary paper](https://pmc.ncbi.nlm.nih.gov/articles/PMC3179091/).

## Validation and limits

Direct polymer comparisons used declared equal-length reference intervals; no inferred residue offset or speculative numbering was used. Exact mutation identity here means the deposited construct sequence, not independent verification of the physical sample. The ACE paper/deposit discrepancy at position 160 remains explicit. JSON stores sequence hashes, exact header evidence, five proposed rules and their original indices. No original observations or shared source were changed.

## Independent consolidation check

The consolidating reviewer independently fetched the four deposited polymer sequences and three stable UniProt FASTAs. Equal-length interval comparisons reproduced every listed substitution, including the ACE N160 discrepancy and the CD4 tag-adjusted numbering. These verify deposited sequences, not independently sampled physical material.
