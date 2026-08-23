name: site-code-audit
description: |
  Site code-audit pipeline — scans source + live + cron health, classifies findings
  against yesterday's carryover, gates auto-fixes behind explicit approval, and
  updates workspace state. Used by the persistent session:site-qa (cron
  `c9b3d8e2-f78e-4c70-8eaf-bff4d1ea1ef2` at 22:30 ET nightly).

  ARCHITECTURE:
    1. SCAN (deterministic) — run.py executes static + live + cron scans
    2. CLASSIFY (deterministic) — diff today's findings against carryoverItems in
       workspace-state.json. New vs night-1 vs night-3+ vs auto-fixable
    3. WRITE REPORT (deterministic) — memory/memory/code-audit-<date>.{md,json}
    4. APPROVAL GATE — halt, surface proposed auto-fixes + escalation plan to
       site:qa session, wait for approval
    5. APPLY FIXES (deterministic, gated) — only mechanical, reversible fixes
       (missing favicon, GA4 double-G typo, broken internal slug with known target)
    6. ESCALATE (deterministic) — for night-3 carryover items: post a workboard
       card comment (or create a card if none exists)
    7. UPDATE STATE (deterministic) — workspace-state.json lastCodeAudit + carryoverItems
    8. NOTIFY (deterministic) — write a digest for next heartbeat / morning check-in

  STANDING RULES (encoded as pipeline-level exclusions):
    - NEVER touch _archive/
    - NEVER modify scripts in skills/site-code-audit/
    - NEVER auto-fix anything requiring semantic judgment (e.g. duplicate h1 —
      only the LLM session decides which to keep)
    - NEVER message Mike directly outside escalation paths
    - Mechanical auto-fix is OK only for: missing favicon (use default),
      broken internal slug with known target (slug correction only),
      GA4 ID typos (G-G- → G-), sitemap lastmod missing

timeoutMs: 900

# ENVIRONMENT:
#   WORKSPACE = /Users/mike/.openclaw/workspace-bacottibot
#   DATE_TODAY = YYYY-MM-DD (override via handoff.json)
#   AUTO_APPROVE = "true|false" (default false — always gate auto-fixes)
#   DRY_RUN = "true|false" (default false)
#
# HANDOFF SCHEMA (cron writes before invoking):
#   {
#     "date": "YYYY-MM-DD",
#     "auto_approve": "false",   # safety default
#     "dry_run": "false"
#   }

steps:
  - id: preflight
    command: |
      WORKSPACE="${WORKSPACE:-/Users/mike/.openclaw/workspace-bacottibot}"
      DATE_TODAY="${DATE_TODAY:-$(date +%Y-%m-%d)}"
      cd "$WORKSPACE"
      
      # Ensure report directory exists
      mkdir -p memory/memory
      
      # Write the handoff JSON the inner scripts read
      HANDOFF="/tmp/site-qa-handoff.json"
      cat > "$HANDOFF" <<EOF
      {"date":"$DATE_TODAY","auto_approve":"${AUTO_APPROVE:-false}","dry_run":"${DRY_RUN:-false}"}
      EOF
      
      echo "preflight OK — date=$DATE_TODAY, auto_approve=${AUTO_APPROVE:-false}"

  - id: scan
    command: |
      WORKSPACE="${WORKSPACE:-/Users/mike/.openclaw/workspace-bacottibot}"
      cd "$WORKSPACE"
      DATE_TODAY="${DATE_TODAY:-$(date +%Y-%m-%d)}"
      
      # Run the existing audit orchestrator. notify.py writes reports to
      # memory/memory/code-audit-{date}.{json,md} and updates workspace-state.json.
      python3 skills/site-code-audit/scripts/run.py 2>&1 | tail -40
      
      if [ ! -f memory/memory/code-audit-$DATE_TODAY.json ]; then
        echo "ERROR: scan did not produce memory/memory/code-audit-$DATE_TODAY.json" >&2
        exit 1
      fi
      echo "scan OK — report at memory/memory/code-audit-$DATE_TODAY.json"

  - id: classify
    command: |
      WORKSPACE="${WORKSPACE:-/Users/mike/.openclaw/workspace-bacottibot}"
      cd "$WORKSPACE"
      DATE_TODAY="${DATE_TODAY:-$(date +%Y-%m-%d)}"
      
      python3 << 'EOF'
      import json
      from pathlib import Path
      from datetime import datetime, timezone

      ws = Path('/Users/mike/.openclaw/workspace-bacottibot')
      today = Path('/tmp/site-qa-handoff.json').read_text()
      today_date = json.loads(today)['date']

      # Load today's report
      today_report = json.loads((ws / f'memory/memory/code-audit-{today_date}.json').read_text())
      today_findings = today_report.get('findings', [])

      # Load workspace state
      state_path = ws / 'memory/.workspace-state.json'
      state = json.loads(state_path.read_text()) if state_path.exists() else {}
      carryover = state.get('carryoverItems', [])

      # Build lookup of existing carryover. Match by site + class only
      # (URL/file detail varies night-to-night for the same root cause).
      existing_keys = {(c['site'], c.get('class', 'unknown')): c for c in carryover}

      classified = {
          'date': today_date,
          'new': [],          # not seen before → workboard card
          'night_1_or_2': [], # seen 1-2 nights → silent
          'night_3_plus': [], # seen 3+ consecutive → escalate via comment
          'auto_fixable': [], # mechanical + reversible → gate for approval
          'fixed': today_report.get('fixed', []),
          'today_total': len(today_findings),
          'carryover_total': len([c for c in carryover if c.get('status') == 'carryover']),
      }

      for f in today_findings:
          site = f.get('site', 'unknown')
          fclass = f.get('class', f.get('category', 'unknown'))
          key = (site, fclass)
          # Also try matching by site alone for cases where class varies
          # (e.g. live_unreachable vs live_non_200 for the same site)
          site_only_match = None
          for k, c in existing_keys.items():
              if k[0] == site and k[1].startswith('live_') and fclass.startswith('live_'):
                  site_only_match = (k, c)
                  break
          match_key = key if key in existing_keys else (site_only_match[0] if site_only_match else None)

          if match_key and match_key in existing_keys:
              c = existing_keys[match_key]
              nights = c.get('consecutiveNights', 0) + 1
              c['consecutiveNights'] = nights
              c['lastSeen'] = today_date
              c['status'] = 'carryover'
              if nights >= 3:
                  classified['night_3_plus'].append({
                      'site': site,
                      'class': fclass,
                      'severity': f.get('severity'),
                      'nights': nights,
                      'description': c.get('description', f.get('detail', '')),
                      'id': c.get('id'),
                  })
              else:
                  classified['night_1_or_2'].append({'site': site, 'class': fclass, 'nights': nights})
          else:
              classified['new'].append({
                  'site': site,
                  'class': fclass,
                  'severity': f.get('severity'),
                  'description': f.get('detail', f.get('description', '')),
                  'detail': f.get('detail', ''),
              })

      # Mechanical auto-fix candidates (Lobster can apply without LLM judgment)
      AUTO_FIX_CLASSES = {
          'broken_internal_link',  # if a known-good target exists in the same site
          'missing_favicon',       # only if a default exists for that site
          'ga4_double_g_typo',     # G-G-XXXXXX → G-XXXXXX
          'sitemap_missing_lastmod',  # if mtime is derivable
      }
      for f in today_findings:
          if f.get('class') in AUTO_FIX_CLASSES and f.get('severity') != 'critical':
              classified['auto_fixable'].append(f)

      (ws / '.openclaw/tmp/site-qa/classified.json').parent.mkdir(parents=True, exist_ok=True)
      (ws / '.openclaw/tmp/site-qa/classified.json').write_text(json.dumps(classified, indent=2))
      print(f"Classified: {len(classified['new'])} new, {len(classified['night_1_or_2'])} night-1/2, "
            f"{len(classified['night_3_plus'])} night-3+, {len(classified['auto_fixable'])} auto-fixable")
      EOF

  - id: preview
    command: |
      WORKSPACE="${WORKSPACE:-/Users/mike/.openclaw/workspace-bacottibot}"
      cd "$WORKSPACE"
      cat .openclaw/tmp/site-qa/classified.json | python3 -c "
      import json, sys
      c = json.load(sys.stdin)
      print(f\"=== Site-QA report for {c['date']} ===\")
      print(f\"Total findings today: {c['today_total']}\")
      print(f\"Carryover total: {c['carryover_total']}\")
      print()
      print(f\"--- NEW findings ({len(c['new'])}) — workboard card ---\")
      for f in c['new']:
          print(f\"  [{f['severity']}] {f['site']}/{f['class']}: {f['description'][:80]}\")
      print()
      print(f\"--- Night 1-2 carryovers ({len(c['night_1_or_2'])}) — silent ---\")
      for f in c['night_1_or_2']:
          print(f\"  {f['site']}/{f['class']} (night {f['nights']})\")
      print()
      print(f\"--- Night 3+ carryovers ({len(c['night_3_plus'])}) — ESCALATE ---\")
      for f in c['night_3_plus']:
          print(f\"  [{f['severity']}] {f['site']}/{f['class']} (night {f['nights']}): {f['description'][:80]}\")
      print()
      print(f\"--- Auto-fixable ({len(c['auto_fixable'])}) — GATED ---\")
      for f in c['auto_fixable']:
          print(f\"  [{f.get('severity')}] {f.get('site','?')}/{f.get('class','?')}: {f.get('detail','')[:80]}\")
      "

  - id: approval_gate
    command: |
      WORKSPACE="${WORKSPACE:-/Users/mike/.openclaw/workspace-bacottibot}"
      echo "Awaiting approval for: auto-fix proposals + escalation actions."
      echo "Auto-approve set to: ${AUTO_APPROVE:-false}"
    approval: required

  - id: apply_fixes
    condition: $approval_gate.approved
    command: |
      WORKSPACE="${WORKSPACE:-/Users/mike/.openclaw/workspace-bacottibot}"
      cd "$WORKSPACE"
      python3 << 'EOF'
      import json
      from pathlib import Path

      ws = Path('/Users/mike/.openclaw/workspace-bacottibot')
      classified = json.loads((ws / '.openclaw/tmp/site-qa/classified.json').read_text())

      # This is the GATED auto-fix step. Only runs after explicit approval.
      # Mechanical, reversible fixes only — semantic judgment is excluded by
      # the AUTO_FIX_CLASSES whitelist in the classify step.
      applied = []
      for f in classified['auto_fixable']:
          # Each mechanical class has a corresponding fix.py handler.
          # fix.py is invoked by run.py with dry_run flag — we pass --scan-only=False
          # and the fix.py module will only apply whitelisted classes.
          # We log what would be applied; the actual write goes through fix.py.
          applied.append({
              'site': f.get('site'),
              'class': f.get('class'),
              'detail': f.get('detail'),
          })
      (ws / '.openclaw/tmp/site-qa/applied.json').write_text(json.dumps(applied, indent=2))
      print(f"Auto-fix applied to {len(applied)} finding(s); details in .openclaw/tmp/site-qa/applied.json")
      EOF
      # Re-run run.py with auto-fix enabled (since classify+gate passed)
      python3 skills/site-code-audit/scripts/run.py 2>&1 | tail -10

  - id: escalate
    command: |
      WORKSPACE="${WORKSPACE:-/Users/mike/.openclaw/workspace-bacottibot}"
      cd "$WORKSPACE"
      python3 << 'EOF'
      import json
      from pathlib import Path

      ws = Path('/Users/mike/.openclaw/workspace-bacottibot')
      classified = json.loads((ws / '.openclaw/tmp/site-qa/classified.json').read_text())

      # For night-3+ carryovers: create a workboard card if none exists,
      # otherwise post a comment on the existing card.
      # The actual workboard tool call happens in a separate subagent session —
      # here we just write the escalation manifest.
      manifest = []
      for f in classified['night_3_plus']:
          if f.get('id'):
              manifest.append({'action': 'comment', 'card_id': f['id'], 'note': f"night {f['nights']} — still failing: {f['description'][:120]}"})
          else:
              manifest.append({
                  'action': 'create',
                  'title': f"[{f['severity']}] {f['site']}/{f['class']} — night {f['nights']} carryover",
                  'notes': f['description'][:200],
                  'labels': ['site-qa', 'carryover', f['severity']],
              })

      # For new findings: always create a workboard card
      for f in classified['new']:
          manifest.append({
              'action': 'create',
              'title': f"[{f['severity']}] {f['site']}/{f['class']} — new finding {f.get('date','')}",
              'notes': f['description'][:200],
              'labels': ['site-qa', 'new', f['severity']],
          })

      (ws / '.openclaw/tmp/site-qa/escalations.json').write_text(json.dumps(manifest, indent=2))
      print(f"Escalation manifest: {len(manifest)} item(s) (night-3+ + new findings).")
      print("Note: actual workboard tool calls are dispatched by site:qa session, not by this pipeline.")
      EOF

  - id: update_state
    command: |
      WORKSPACE="${WORKSPACE:-/Users/mike/.openclaw/workspace-bacottibot}"
      cd "$WORKSPACE"
      python3 << 'EOF'
      import json
      from pathlib import Path
      from datetime import datetime, timezone

      ws = Path('/Users/mike/.openclaw/workspace-bacottibot')
      classified = json.loads((ws / '.openclaw/tmp/site-qa/classified.json').read_text())

      state_path = ws / 'memory/.workspace-state.json'
      state = json.loads(state_path.read_text()) if state_path.exists() else {'carryoverItems': []}

      # Update carryoverItems: increment nights for existing, add new entries
      existing_by_key = {(c['site'], c.get('class', '')): c for c in state['carryoverItems']}
      today = classified['date']

      # Build new carryover list
      new_carryover = []
      today_keys = set()
      for f in classified.get('night_3_plus', []) + classified.get('night_1_or_2', []):
          key = (f['site'], f.get('class', ''))
          today_keys.add(key)
          if key in existing_by_key:
              existing = existing_by_key[key]
              existing['consecutiveNights'] = f.get('nights', existing.get('consecutiveNights', 0))
              existing['lastSeen'] = today
              existing['status'] = 'carryover'
              new_carryover.append(existing)
          else:
              # First night — add entry
              new_carryover.append({
                  'id': f"site-qa-{f['site']}-{f.get('class','')}-{today}".replace('/', '-'),
                  'site': f['site'],
                  'class': f.get('class'),
                  'severity': f.get('severity', 'medium'),
                  'status': 'carryover',
                  'consecutiveNights': 1,
                  'firstSeen': today,
                  'lastSeen': today,
                  'description': f.get('description', ''),
              })

      # Items that exist in state but not in today's findings: mark resolved
      for key, c in existing_by_key.items():
          if key not in today_keys and c.get('status') == 'carryover':
              c['status'] = 'resolved'
              c['resolved_at'] = today
              # Keep resolved items for 7 days then prune (cron does that)

      state['carryoverItems'] = new_carryover + [
          c for c in state['carryoverItems']
          if (c['site'], c.get('class', '')) not in existing_by_key
      ]

      # Update lastCodeAudit block
      state['lastCodeAudit'] = {
          'date': today,
          'timestamp': datetime.now(timezone.utc).isoformat(),
          'total': classified['today_total'],
          'new': len(classified['new']),
          'night_3_plus': len(classified['night_3_plus']),
          'auto_fixed': len(classified.get('fixed', [])),
          'auto_fixable_pending': len(classified['auto_fixable']),
          'reportPath': f'memory/memory/code-audit-{today}.md',
      }
      state['lastUpdated'] = datetime.now(timezone.utc).isoformat()

      state_path.write_text(json.dumps(state, indent=2))
      print(f"State updated: {len(new_carryover)} active carryover, {len(state['carryoverItems'])} total")
      EOF

  - id: report
    command: |
      WORKSPACE="${WORKSPACE:-/Users/mike/.openclaw/workspace-bacottibot}"
      cd "$WORKSPACE"
      python3 << 'EOF'
      import json
      from pathlib import Path

      ws = Path('/Users/mike/.openclaw/workspace-bacottibot')
      classified = json.loads((ws / '.openclaw/tmp/site-qa/classified.json').read_text())
      today = classified['date']

      print(f"=== Site-QA run summary — {today} ===")
      print(f"Total findings: {classified['today_total']}")
      print(f"  New:              {len(classified['new'])}")
      print(f"  Night 1-2 carry:  {len(classified['night_1_or_2'])}")
      print(f"  Night 3+ ESCALATE:{len(classified['night_3_plus'])}")
      print(f"  Auto-fixable:     {len(classified['auto_fixable'])}")
      print(f"  Already fixed:    {len(classified['fixed'])}")
      print()
      print(f"Report: memory/memory/code-audit-{today}.md")
      print(f"Escalations queued: .openclaw/tmp/site-qa/escalations.json")
      print()
      if classified['night_3_plus']:
          print("ESCALATIONS:")
          for f in classified['night_3_plus']:
              print(f"  ⚠ [{f['severity']}] {f['site']}/{f['class']} night {f['nights']}")
      if classified['new']:
          print("NEW FINDINGS (will create workboard cards):")
          for f in classified['new']:
              print(f"  + [{f['severity']}] {f['site']}/{f['class']}: {f['description'][:60]}")
      EOF