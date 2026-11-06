# PylaAI UI refresh implementation plan

Goal: apply the approved graphite/yellow presentation to the existing panel.
Architecture: preserve Flask endpoints and vanilla-JS state/events; replace presentation assets and copy only.
Spec: ../specs/2026-11-06-ui-design.md

## Tasks

- [x] Apply the nine unslop passes: spacing, color, icons, copy, type, layout, details, visuals, motion. Files: webui/static/style.css, webui/static/icons.svg, webui/templates/index.html, webui/static/app.js.
- [x] Use consistent 4px spacing, 256px desktop sidebar, fluid main content, neutral surfaces, yellow/dark primary control and visible focus. Preserve selectors and routes.
- [x] Replace decorative glyphs with local line icons, rewrite vague headings and uppercase labels, present actual brawler portraits with clear catalog/queue labels.
- [x] Verify syntax, setup flow, full Python suite and actual browser behavior at desktop/mobile sizes. No new runtime behavior or mirrored implementation tests are required for this presentation change.
- [x] Run whole-change code review and document evidence in OVERVIEW.md. Security scan, commit and publication are the final integration steps recorded by Git history.

## Ledger

- Existing isolated sanitized checkout retained; base 02ec2d6. User approved direction and continuation. Existing publication authorization remains in effect.
- Baseline: 198 tests passed and one skipped in this chat; UI was visually audited before approval.
- Review focus: wizard still blocks missing device/queue; polling does not replace focused inputs; icon buttons retain accessible names; local portrait paths and user names stay escaped; mobile forms remain operable.
- Ruling: overview artwork always uses labeled catalog portraits rather than cached queue rows, which can belong to another profile. Actual selected rosters stay on the queue/review screens.
- Verification complete: 199 tests, one skipped; 13 setup-flow assertions; syntax, contrast and SVG checks; desktop/mobile browser actions. Queue restored empty, bot idle. Fresh reviewer found no blocking issue.
