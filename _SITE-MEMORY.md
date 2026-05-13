# SITE MEMORY — Bacotti Inc.

## Identity
- Entity: Bacotti Inc. (private family office / stewardship company)
- Purpose: Institutional private family office website — not a consumer brand
- Repo: github.com/michaelbacotti/bacotti-rebuild
- Architecture: Flat HTML — see skills/website-flat-html.md

## Design System
- Colors: dark navy (#1a2332), charcoal (#2d3748), ivory (#f8f5f0), deep gold accent (#b8965a)
- Fonts: Georgia/serif for headings, system-ui sans-serif for body
- Style: institutional, restrained, trust-focused, generous whitespace, editorial calm

## File Roles
- /style.css — ALL styles
- /nav.js — Site-wide nav
- /footer.js — Site-wide footer
- /_template.html — Base for new pages

## Critical Rules
- All paths to style.css, nav.js, footer.js must start with /
- No build step. No Hugo. No GitHub Actions.
- No entity financials, legal specifics, or confidential detail

## Change Log
- 2026-05-13 — Initial build