#!/usr/bin/env python3
"""Pre-commit hook: scan staged files for credential-shaped strings.

Matches well-known prefixes for the API surfaces this repo uses (or
might use). False-positive prone keys (generic high-entropy strings)
are intentionally NOT matched — that's `gitleaks`/`detect-secrets`
territory; this hook is the targeted block for things that *would*
hurt if committed:

  * OpenAI         — sk-proj-..., sk-...     (only sk-proj- is the
                                                current shape; sk- is
                                                covered for legacy keys)
  * Anthropic      — sk-ant-api03-...
  * GitHub tokens  — ghp_, ghs_, gho_, github_pat_
  * AWS access key — AKIA[A-Z0-9]{16}
  * Slack          — xoxb-, xoxp-, xoxa-, xoxr-
  * Google         — AIza[A-Za-z0-9_-]{30,}

False positives we deliberately silence:
  * AKIA-prefixed strings inside `data/external/**/*.fasta` (protein
    sequences — A/K/I/A are amino-acid codes). The `exclude` pattern
    in `.pre-commit-config.yaml` already skips fasta files; the regex
    here also requires the AKIA pattern to have exactly 16 trailing
    uppercase alphanumerics, which biological sequences rarely produce
    in isolation but do produce often enough that the exclude is the
    real defense.

Exits 1 (with a loud named error) on any hit. Pre-commit invokes
this with the staged file paths as argv.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

# Each pattern: (label, compiled regex). The regex MUST be specific
# enough that a casual match is intentional — false positives here
# are toil for the user.
PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("OpenAI project key (sk-proj-...)", re.compile(r"sk-proj-[A-Za-z0-9_-]{20,}")),
    ("OpenAI legacy key (sk-...)",        re.compile(r"\bsk-[A-Za-z0-9]{20,}\b")),
    ("Anthropic key (sk-ant-...)",        re.compile(r"sk-ant-[A-Za-z0-9_-]{20,}")),
    ("GitHub personal-access token",      re.compile(r"\bghp_[A-Za-z0-9]{30,}\b")),
    ("GitHub server-side token",          re.compile(r"\bghs_[A-Za-z0-9]{30,}\b")),
    ("GitHub fine-grained PAT",           re.compile(r"\bgithub_pat_[A-Za-z0-9_]{30,}\b")),
    ("Slack bot/user token",              re.compile(r"\bxox[bpaors]-[A-Za-z0-9-]{20,}\b")),
    ("Google API key (AIza...)",          re.compile(r"\bAIza[A-Za-z0-9_-]{35}\b")),
    ("AWS access key ID (AKIA...)",       re.compile(r"\bAKIA[A-Z0-9]{16}\b")),
    ("Slack webhook URL",                 re.compile(r"https://hooks\.slack\.com/services/T[A-Z0-9]+/B[A-Z0-9]+/[A-Za-z0-9]+")),
    ("Generic 'PRIVATE KEY' PEM",         re.compile(r"-----BEGIN (RSA |EC |DSA |OPENSSH |PGP )?PRIVATE KEY-----")),
]

# Sentinel placeholders to allow — substrings of templates / docs we
# intentionally ship and don't want to flag.
ALLOWLIST_SUBSTRINGS = {
    "sk-proj-EXAMPLE",
    "sk-ant-EXAMPLE",
    "REPLACE_WITH_",
    "your_api_key_here",
    "<your-api-key>",
}


def _scan(path: Path) -> list[tuple[str, str]]:
    try:
        text = path.read_text(errors="replace")
    except (OSError, UnicodeError):
        return []
    hits: list[tuple[str, str]] = []
    for label, pat in PATTERNS:
        for m in pat.finditer(text):
            tok = m.group(0)
            if any(allowed in tok for allowed in ALLOWLIST_SUBSTRINGS):
                continue
            hits.append((label, tok))
    return hits


def main(argv: list[str]) -> int:
    any_hit = False
    for arg in argv:
        path = Path(arg)
        if not path.is_file():
            continue
        hits = _scan(path)
        if not hits:
            continue
        any_hit = True
        sys.stderr.write(f"\n\033[31mSECRET DETECTED in {path}:\033[0m\n")
        for label, tok in hits:
            # Mask the middle of the token in the error output — print
            # the prefix + suffix only so the developer can identify
            # the key without re-leaking it in CI logs.
            shown = tok if len(tok) <= 18 else f"{tok[:8]}…{tok[-4:]}"
            sys.stderr.write(f"  {label}: {shown}\n")
    if any_hit:
        sys.stderr.write(
            "\nCommit blocked. Remove the secret(s) above, rotate the key, "
            "and re-stage.\n"
            "If this is a false positive, add the surrounding token to "
            "ALLOWLIST_SUBSTRINGS in scripts/precommit/scan_secrets.py.\n"
        )
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
