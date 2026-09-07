// functions/_middleware.js — PIN gate for dashboard.dependability.us
//
// Cloudflare Pages Function that runs on every request before static files are served.
// If user has valid HMAC-signed session cookie: pass through (next()) to serve dashboard.
// If user does not: render PIN entry page; on POST, verify PIN, set cookie, pass through.
//
// Env vars (set via `wrangler pages secret put`):
//   ACCESS_CODE_HASH  — SHA-256(SALT + pin).hex()
//   SESSION_SECRET    — 32-byte random hex, HMAC key for cookie signing
//
// To add more users, populate USER_PINS below. Single-user by default.
// SALT MUST match the value used to generate ACCESS_CODE_HASH (see ACCESS.md rotation procedure).

const COOKIE_NAME = 'dash_auth';
const COOKIE_MAX_AGE = 30 * 24 * 60 * 60;  // 30 days
const COOKIE_PATH = '/';

const LOCKOUT_THRESHOLD = 5;      // wrong attempts allowed
const LOCKOUT_WINDOW = 600;       // seconds (10 min) — sliding window
const LOCKOUT_DURATION = 900;     // seconds (15 min) — how long to lock after threshold

// Hardcoded salt — must match the value in ACCESS.md "Rotation procedure" step 2.
const SALT = 'dep-dash-v1-2026-09-07-mb-only';

// User table. To add a user, generate a hash with hashPin() below and add an entry.
// In production with single-user env-var model, USER_PINS contains only 'mike' from env.
async function loadUserPins(env) {
  return {
    mike: {
      hash: env.ACCESS_CODE_HASH,
      name: 'Mike Bacotti',
    },
    // To add more users, hash their PIN with the same SALT and add:
    // jane: { hash: '<hash>', name: 'Jane Doe' },
  };
}

// ============================================================================
// PIN verification (constant-time string compare)
// ============================================================================

async function sha256Hex(input) {
  const bytes = new TextEncoder().encode(input);
  const buf = await crypto.subtle.digest('SHA-256', bytes);
  return Array.from(new Uint8Array(buf))
    .map((b) => b.toString(16).padStart(2, '0'))
    .join('');
}

async function verifyPin(submittedPin, expectedHash) {
  if (!submittedPin || typeof submittedPin !== 'string') return false;
  const actualHash = await sha256Hex(SALT + submittedPin);
  // Constant-time compare
  if (actualHash.length !== expectedHash.length) return false;
  let diff = 0;
  for (let i = 0; i < actualHash.length; i++) {
    diff |= actualHash.charCodeAt(i) ^ expectedHash.charCodeAt(i);
  }
  return diff === 0;
}

// ============================================================================
// Session cookie (HMAC-signed timestamp)
// ============================================================================

async function hmacSign(message, secretHex) {
  const secretBytes = new Uint8Array(
    secretHex.match(/.{1,2}/g).map((b) => parseInt(b, 16))
  );
  const key = await crypto.subtle.importKey(
    'raw',
    secretBytes,
    { name: 'HMAC', hash: 'SHA-256' },
    false,
    ['sign']
  );
  const sig = await crypto.subtle.sign('HMAC', key, new TextEncoder().encode(message));
  return Array.from(new Uint8Array(sig))
    .map((b) => b.toString(16).padStart(2, '0'))
    .join('');
}

async function issueSessionToken(env) {
  const expiry = Math.floor(Date.now() / 1000) + COOKIE_MAX_AGE;
  const sig = await hmacSign(String(expiry), env.SESSION_SECRET);
  return `${expiry}.${sig}`;
}

async function verifySessionToken(token, env) {
  if (!token || typeof token !== 'string') return false;
  const [expiryStr, sig] = token.split('.');
  if (!expiryStr || !sig) return false;
  const expiry = parseInt(expiryStr, 10);
  if (!Number.isFinite(expiry)) return false;
  if (Math.floor(Date.now() / 1000) > expiry) return false;
  const expected = await hmacSign(expiryStr, env.SESSION_SECRET);
  return sig === expected;
}

function parseCookie(cookieHeader, name) {
  if (!cookieHeader) return null;
  for (const part of cookieHeader.split(';')) {
    const [k, ...rest] = part.trim().split('=');
    if (k === name) return rest.join('=');
  }
  return null;
}

// ============================================================================
// Rate limiting (in-memory; per Worker isolate)
// ============================================================================

const lockoutState = new Map(); // ip -> { attempts: number, firstAttemptTs: number, lockedUntilTs: number }

function isLockedOut(ip) {
  const state = lockoutState.get(ip);
  if (!state) return false;
  if (state.lockedUntilTs && Date.now() / 1000 < state.lockedUntilTs) return true;
  return false;
}

function lockoutSecondsRemaining(ip) {
  const state = lockoutState.get(ip);
  if (!state || !state.lockedUntilTs) return 0;
  return Math.max(0, Math.ceil(state.lockedUntilTs - Date.now() / 1000));
}

function recordFailedAttempt(ip) {
  const now = Date.now() / 1000;
  const state = lockoutState.get(ip) || { attempts: 0, firstAttemptTs: now, lockedUntilTs: 0 };
  // Reset window if first attempt was more than LOCKOUT_WINDOW ago
  if (now - state.firstAttemptTs > LOCKOUT_WINDOW) {
    state.attempts = 0;
    state.firstAttemptTs = now;
    state.lockedUntilTs = 0;
  }
  state.attempts += 1;
  if (state.attempts >= LOCKOUT_THRESHOLD) {
    state.lockedUntilTs = now + LOCKOUT_DURATION;
  }
  lockoutState.set(ip, state);
  return {
    attempts: state.attempts,
    locked: state.attempts >= LOCKOUT_THRESHOLD,
  };
}

function clearLockout(ip) {
  lockoutState.delete(ip);
}

// ============================================================================
// HTML templates
// ============================================================================

function escapeHtml(str) {
  return String(str)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;');
}

function pinPageHtml({ error = null, attemptsLeft = null } = {}) {
  const errorBlock = error
    ? `<div class="error">${escapeHtml(error)}</div>`
    : '';
  const attemptsBlock = attemptsLeft !== null && attemptsLeft > 0
    ? `<div class="attempts">${attemptsLeft} attempt${attemptsLeft === 1 ? '' : 's'} remaining</div>`
    : '';
  return `<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="robots" content="noindex, nofollow">
<title>Dashboard — Access</title>
<style>
  :root {
    --bg: #0d1117;
    --surface: #161b22;
    --border: #30363d;
    --text: #e6edf3;
    --muted: #7d8590;
    --gold: #d4a843;
    --red: #f85149;
  }
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body {
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Helvetica, Arial, sans-serif;
    background: var(--bg);
    color: var(--text);
    min-height: 100vh;
    display: flex;
    align-items: center;
    justify-content: center;
    padding: 24px;
  }
  .card {
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: 12px;
    padding: 32px;
    max-width: 400px;
    width: 100%;
    box-shadow: 0 8px 24px rgba(0,0,0,0.4);
  }
  h1 {
    font-size: 18px;
    font-weight: 600;
    margin-bottom: 8px;
    color: var(--gold);
  }
  .subtitle {
    color: var(--muted);
    font-size: 13px;
    margin-bottom: 24px;
    line-height: 1.5;
  }
  label {
    display: block;
    font-size: 12px;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.5px;
    color: var(--muted);
    margin-bottom: 8px;
  }
  input[type="password"] {
    width: 100%;
    background: var(--bg);
    border: 1px solid var(--border);
    color: var(--text);
    padding: 12px;
    border-radius: 6px;
    font-size: 15px;
    font-family: ui-monospace, SFMono-Regular, monospace;
    letter-spacing: 1px;
  }
  input[type="password"]:focus {
    outline: none;
    border-color: var(--gold);
    box-shadow: 0 0 0 2px rgba(212, 168, 67, 0.2);
  }
  button {
    width: 100%;
    background: var(--gold);
    color: #0d1117;
    border: none;
    padding: 12px;
    border-radius: 6px;
    font-size: 14px;
    font-weight: 600;
    cursor: pointer;
    margin-top: 16px;
    transition: background 0.15s;
  }
  button:hover { background: #e6b94d; }
  button:active { background: #b8923a; }
  .error {
    color: var(--red);
    font-size: 13px;
    margin-top: 12px;
    padding: 8px 12px;
    background: rgba(248, 81, 73, 0.1);
    border-radius: 4px;
    border: 1px solid rgba(248, 81, 73, 0.3);
  }
  .attempts {
    color: var(--muted);
    font-size: 12px;
    margin-top: 12px;
    text-align: center;
  }
  .footer {
    color: var(--muted);
    font-size: 11px;
    margin-top: 24px;
    text-align: center;
    line-height: 1.5;
  }
</style>
</head>
<body>
  <div class="card">
    <h1>Market Dashboard</h1>
    <div class="subtitle">Enter the access code from your password manager.</div>
    <form method="POST" autocomplete="off">
      <label for="pin">Access code</label>
      <input type="password" id="pin" name="pin" required autofocus spellcheck="false" autocomplete="off">
      <button type="submit">Unlock</button>
      ${errorBlock}
      ${attemptsBlock}
    </form>
    <div class="footer">
      Authorized access only · Dependability Holdings, LLC
    </div>
  </div>
</body>
</html>`;
}

function lockoutPageHtml(secondsRemaining) {
  const minutes = Math.ceil(secondsRemaining / 60);
  return `<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="robots" content="noindex, nofollow">
<title>Dashboard — Locked</title>
<style>
  body {
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Helvetica, Arial, sans-serif;
    background: #0d1117;
    color: #e6edf3;
    min-height: 100vh;
    display: flex;
    align-items: center;
    justify-content: center;
    padding: 24px;
    text-align: center;
  }
  .card {
    background: #161b22;
    border: 1px solid #30363d;
    border-radius: 12px;
    padding: 32px;
    max-width: 400px;
  }
  h1 { color: #f85149; font-size: 18px; margin-bottom: 12px; }
  p { color: #7d8590; font-size: 14px; line-height: 1.6; }
  .countdown { font-size: 24px; font-weight: 600; color: #d4a843; margin: 16px 0; }
</style>
</head>
<body>
  <div class="card">
    <h1>Too many failed attempts</h1>
    <p>Access is temporarily locked. Please try again in:</p>
    <div class="countdown">${minutes} minute${minutes === 1 ? '' : 's'}</div>
    <p>Authorized access only · Dependability Holdings, LLC</p>
  </div>
</body>
</html>`;
}

// ============================================================================
// Main handler
// ============================================================================

export async function onRequest(context) {
  const { request, env, next } = context;
  const url = new URL(request.url);
  const ip =
    request.headers.get('CF-Connecting-IP') ||
    request.headers.get('X-Forwarded-For')?.split(',')[0]?.trim() ||
    '0.0.0.0';

  // Lockout check first
  if (isLockedOut(ip)) {
    return new Response(lockoutPageHtml(lockoutSecondsRemaining(ip)), {
      status: 429,
      headers: {
        'Content-Type': 'text/html; charset=utf-8',
        'Retry-After': String(lockoutSecondsRemaining(ip)),
        'Cache-Control': 'no-store',
      },
    });
  }

  // Check existing session cookie
  const cookieHeader = request.headers.get('Cookie') || '';
  const sessionToken = parseCookie(cookieHeader, COOKIE_NAME);

  if (sessionToken && (await verifySessionToken(sessionToken, env))) {
    // Valid session — serve dashboard (or whatever static file was requested)
    return next();
  }

  // No valid session — handle PIN entry
  if (request.method === 'POST') {
    let submittedPin = null;
    const contentType = request.headers.get('Content-Type') || '';

    if (contentType.includes('application/x-www-form-urlencoded')) {
      const formData = await request.formData();
      submittedPin = formData.get('pin');
    } else if (contentType.includes('application/json')) {
      try {
        const body = await request.json();
        submittedPin = body.pin;
      } catch {
        // ignore malformed body
      }
    }

    const userPins = await loadUserPins(env);
    let matchedUser = null;
    for (const [key, user] of Object.entries(userPins)) {
      if (user.hash && (await verifyPin(submittedPin, user.hash))) {
        matchedUser = key;
        break;
      }
    }

    if (matchedUser) {
      // PIN accepted — issue session cookie, clear lockout, serve dashboard
      clearLockout(ip);
      const token = await issueSessionToken(env);
      const dashboardResponse = await next();
      // Clone response so we can attach Set-Cookie header
      const newHeaders = new Headers(dashboardResponse.headers);
      newHeaders.set(
        'Set-Cookie',
        `${COOKIE_NAME}=${token}; Path=${COOKIE_PATH}; HttpOnly; Secure; SameSite=Strict; Max-Age=${COOKIE_MAX_AGE}`
      );
      newHeaders.set('Cache-Control', 'no-store');
      return new Response(dashboardResponse.body, {
        status: dashboardResponse.status,
        statusText: dashboardResponse.statusText,
        headers: newHeaders,
      });
    }

    // PIN rejected
    const { attempts, locked } = recordFailedAttempt(ip);
    if (locked) {
      return new Response(lockoutPageHtml(LOCKOUT_DURATION), {
        status: 429,
        headers: {
          'Content-Type': 'text/html; charset=utf-8',
          'Retry-After': String(LOCKOUT_DURATION),
          'Cache-Control': 'no-store',
        },
      });
    }
    return new Response(
      pinPageHtml({
        error: 'Incorrect access code.',
        attemptsLeft: Math.max(0, LOCKOUT_THRESHOLD - attempts),
      }),
      {
        status: 401,
        headers: { 'Content-Type': 'text/html; charset=utf-8', 'Cache-Control': 'no-store' },
      }
    );
  }

  // GET request without valid session — show PIN entry page
  return new Response(pinPageHtml(), {
    status: 200,
    headers: {
      'Content-Type': 'text/html; charset=utf-8',
      'Cache-Control': 'no-store',
    },
  });
}
