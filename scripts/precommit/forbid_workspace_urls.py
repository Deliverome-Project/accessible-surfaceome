#!/usr/bin/env python3
"""Block cloud-console URLs that embed a workspace or account identifier.

This repository is public. A Modal *run* identifier (``ap-...``) is a resource id and is
harmless on its own -- it grants nothing without a workspace token, and recording it makes
a published dataset traceable. The console URL around it is different: it embeds the
workspace slug, which is internal infrastructure detail and the sort of thing that belongs
in a private database, not on a public PR.

This fired for real on 2026-09-28: a PR comment carried
``modal.com/apps/<workspace>/main/ap-...``, publishing the workspace name. The comment was
edited; this hook stops the next one.

Bare identifiers are deliberately allowed. The goal is to strip the workspace, not to make
runs unciteable.
"""

from __future__ import annotations

import re
import sys

# Console URLs whose path segment after the product is an org / workspace / account slug.
PATTERNS = [
    (re.compile(r"modal\.com/apps/[A-Za-z0-9][-\w]*"), "Modal console URL (embeds the workspace)"),
    (re.compile(r"modal\.com/workspaces/[A-Za-z0-9][-\w]*"), "Modal workspace URL"),
    (re.compile(r"\b\d{12}\.dkr\.ecr\.[a-z0-9-]+\.amazonaws\.com"), "ECR URL (embeds the AWS account id)"),
    (re.compile(r"dash\.cloudflare\.com/[0-9a-f]{32}"), "Cloudflare dashboard URL (embeds the account id)"),
]

ALLOW = re.compile(r"<[^>]*>|REPLACE_WITH|\byour-\w+\b|example")


def main(paths: list[str]) -> int:
    bad = 0
    for path in paths:
        try:
            text = open(path, encoding="utf-8", errors="replace").read()
        except (OSError, IsADirectoryError):
            continue
        for lineno, line in enumerate(text.splitlines(), 1):
            for pattern, label in PATTERNS:
                m = pattern.search(line)
                if m and not ALLOW.search(m.group(0)):
                    print(f"{path}:{lineno}: {label}: {m.group(0)}")
                    bad += 1
    if bad:
        print(
            f"\n{bad} workspace/account-scoped URL(s). This repo is public.\n"
            "Record the bare run identifier instead (e.g. `ap-XXXX`), or put the URL in the\n"
            "private database. Placeholders like <workspace> are allowed."
        )
    return 1 if bad else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
