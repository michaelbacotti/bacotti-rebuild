# Anti-Patterns (Documented 2026-08-23)

Captured during the audit + cron-quality upgrade work. Each anti-pattern has: symptom, detection, mitigation, real-world lesson.

---

## Anti-pattern #89 — Hand-edited HTML E-E-A-T wiped on cron rebuild

**Symptom:** You hand-add an E-E-A-T block to a rendered HTML file. The next cron run (which regenerates HTML from MD source) silently overwrites your edit.

**Detection:** `verify_published.py` flags `anti-pattern #89: E-E-A-T appears in HTML but is NOT wrapped in .eeat-block / .eeat / .byline-box — next cron run will wipe it`.

**Mitigation:**

1. ALWAYS run `check_source.py <file>` BEFORE any HTML edit. If it returns `md_source` or `inline_static`, edit the source (MD or build.py), not the HTML.
2. E-E-A-T blocks MUST be wrapped in `<section class="eeat-block">` AND defined as a Python string constant in `build.py` (e.g. `EEAT_BLOCK = "..."`), then interpolated into the render function. This way every cron rebuild regenerates E-E-A-T.
3. After editing build.py, rebuild + run `verify_published.py --site <key>` to confirm E-E-A-T survived.

**Lessons learned (real):** During the 2026-08-23 audit, E-E-A-T sections were initially considered for direct HTML insertion. The fix: bake `EEAT_BLOCK` into `render_newsletter_article()` in build.py for bithues, then mirror the pattern to all 5 cron-driven sites (dependability, succession, tredey, spaceorbitals, triadive). Confirmed: rebuilt newsletters/articles now have E-E-A-T in `.eeat-block` wrapper that survives cron rebuilds.

---

## Anti-pattern #92 — Edit-at-source doctrine

**Rule:** Before any HTML edit, classify the file first.

`check_source.py` returns one of:
- `hand_crafted` → edit HTML directly
- `md_source` → edit the MD, rebuild
- `inline_static` → edit `build.py`, rebuild
- `orphan` → manual review (no source)

Edit the source the file was generated from, never the rendered HTML.

**Why:** sites with `build.py` (spaceorbitals, triadive, succession newsletters, bithues-crypto, tredey, dependability-may26) regenerate HTML on every cron run. Direct HTML edits get silently wiped. This has caused at least 3 round-trips in past sessions (the playbook page ad-slot dup, the dup H1 on /reading-maps/, the duplicate `<ins>` blocks).

---

## Anti-pattern #91 — Confirm deploy method per site

**Rule:** Don't assume `git push` deploys.

| Deploy method | Sites |
|---|---|
| `git push origin main` (auto-deploy via CF Pages) | dependability, succession, tredey |
| `wrangler pages deploy` (manual upload) | bacotti, bithues-crypto, triadive, spaceorbitals |

Check `TOOLS.md` before claiming "deployed". After wrangler upload, wait ~30s for CF Pages edge cache to propagate.

---

## Anti-pattern #93 — Verify live, not git

A commit in the local repo does NOT mean the change is live.

- For `wrangler pages deploy` sites: push alone is not enough — must also run wrangler.
- For git-push sites: CF Pages build can take ~30s after push to propagate to the edge.
- Run `curl -s https://<site>/<path> | grep "..."` to confirm live content.
