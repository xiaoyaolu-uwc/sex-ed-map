---
name: End-of-Build Summary Convention
description: After any extensive build session, always close with a feature-level summary
type: feedback
---

After completing any extensive build (multiple files written/edited), always close the response with a summary covering:
1. What changed at the feature level (not file-by-file diffs)
2. Where each thing lives in the repo structure
3. How the user can test it

**Why:** User wants to stay oriented after large builds without reading every file diff.

**How to apply:** Any session where 3+ files are written or significantly edited. Put it at the end, after version control is done.
