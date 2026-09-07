# Access Policy

## Authorized users (current)

| User | Email | Status | PIN issued |
|---|---|---|---|
| Mike Bacotti | michaelbacotti@gmail.com | Active | 2026-09-07 (v1) |

**Single-user mode.** This dashboard is private to the principal of Dependability Holdings, LLC until Mike explicitly authorizes additional users.

## Adding a new user (future)

When Mike wants to share access with someone (family, advisor, etc.):

1. Generate a PIN for the new user (or have them pick one, min 16 chars)
2. Hash it locally: `node scripts/hash-pin.js '<new-pin>'` — outputs the SHA-256 hash with the project's salt
3. Add a row to the `USER_PINS` object in `functions/_middleware.js`:
   ```javascript
   const USER_PINS = {
     "mike": { hash: "<hash-from-step-2>", name: "Mike Bacotti" },
     "<new-user>": { hash: "<their-hash>", name: "<their-name>" }
   };
   ```
4. Re-deploy: `bash scripts/build-and-deploy.sh`
5. Deliver the PIN to the new user via secure channel (1Password share, in-person, etc.)
6. Update the authorized-users table above

The Worker code change is small (~5 lines added) and tracked in git history.

## Removing a user

1. Remove their entry from `USER_PINS` in `functions/_middleware.js`
2. Re-deploy
3. Update the authorized-users table above

Their existing cookies become invalid (signature fails or user lookup misses). They'll be prompted for a new PIN on next visit.

## PIN rotation policy

| Trigger | Action |
|---|---|
| Annual review (every Sept) | Rotate Mike's PIN, update env var |
| Suspected compromise | Immediate rotation + force-logout (rotate `SESSION_SECRET` too) |
| User leaves/changes role | Remove from `USER_PINS`, do not reuse the PIN |
| Adding a user | Don't rotate existing PINs unless already due |

**Recommended cadence:** annual rotation unless compromise is suspected.

## Rotation procedure

For Mike's PIN:

```bash
# 1. Generate new PIN (24 chars, URL-safe, no ambiguous chars)
python3 -c "
import secrets
alphabet = 'ABCDEFGHJKLMNPQRSTUVWXYZabcdefghjkmnpqrstuvwxyz23456789!@#\$%^&*?+='
print(''.join(secrets.choice(alphabet) for _ in range(24)))"

# 2. Hash it (uses SALT hardcoded in functions/_middleware.js)
SALT="dep-dash-v1-2026-09-07-mb-only"
echo -n "${SALT}<new-pin>" | shasum -a 256 | awk '{print $1}'

# 3. Update Pages env var (replace value below)
wrangler pages secret put ACCESS_CODE_HASH --project-name=dependability-dashboard
# (paste hash, Enter, Ctrl-D)

# 4. Save new PIN to your password manager BEFORE closing the terminal

# 5. Old cookie is now invalid (new hash doesn't match). Re-enter PIN to log in.
```

## Security model

### What the PIN gate protects against

| Threat | Mitigation |
|---|---|
| Public URL exposure | PIN required; without PIN, attacker sees PIN entry page only |
| Brute force | 5 wrong attempts / 10 min = 15-min IP lockout |
| Cookie theft (XSS) | HTTP-only cookie (JS can't read it), Secure (HTTPS-only), SameSite=Strict |
| Cookie forgery | HMAC-SHA256 signature with server-side `SESSION_SECRET` |
| Replay | Cookie expires after 30 days |
| CSRF | SameSite=Strict blocks cross-origin requests |
| Plaintext PIN storage | PIN is SHA-256 hashed before storage; PIN itself never leaves the user's browser |
| Shoulder-surfing | Standard browser threat — mitigated by site being a single-user tool |

### What the PIN gate does NOT protect against

| Threat | Mitigation |
|---|---|
| Compromised endpoint | Mike's responsibility — keep browser/Mac secure |
| Weak PIN | Mike's responsibility — generate strong 24-char PIN, store in password manager |
| Insider with physical access to Mike's Mac | Out of scope — they could read the cookie file directly |
| Network observer | TLS (HTTPS) protects in transit; CF Pages auto-provisions certificates |
| Phishing | User must enter PIN at `dashboard.dependability.us` only — verify the URL |

### Rate limiting — known limitation

The current implementation uses in-memory state (per Worker isolate). For a single-user dashboard, this is sufficient — attacker would need to also use Mike's IP to benefit from the lack of cross-isolate coordination.

If you ever scale to multi-user or expose to the public internet, upgrade to Workers KV:

```javascript
// Replace the in-memory Map with:
const lockoutData = await env.RATE_LIMIT.get(`lockout:${ip}`, { type: 'json' });
await env.RATE_LIMIT.put(`lockout:${ip}`, JSON.stringify({ ... }), { expirationTtl: 900 });
```

Requires adding a KV namespace binding to `wrangler.toml` and re-deploying.

## Audit trail

Access events are NOT currently logged to a persistent store. If audit logging becomes important:

1. Add a D1 binding to `wrangler.toml`
2. Write events to `audit_log` table on auth success/failure/lockout
3. Surface in CF dashboard or sync back to workspace

For now, CF Workers Logs (free tier, 3-day retention) captures auth events. Enable via `wrangler pages deployment tail --project-name=dependability-dashboard` during troubleshooting.

## Contact

For access issues, see the workspace's workspace `MEMORY.md` (security incidents section) or contact the workspace owner.
