# Upstream migration

Fork baseline: `361e9f24fd6ef81ab03a1ca9d7854f4aec62f303` from Biomistik-Official/PylaAI-Biomistik-Realese. Upstream reference: `763c38926fbb3e2edc074db1c3ca2ddb9350d325` from PylaAI/PylaAI, dated 2026-10-31.

## Included

- Local browser menus with sequential preparation, optional player-account loading, portrait cards, queue editing, profiles and runtime control. Legacy desktop menus remain available.
- Current named search in the game's brawler menu. Queue/API progression selects the named row, confirms selection and blocks unauthorized watchdog starts.
- Paired modern ONNX models, metadata-aware pose/entity decoding and semantic terrain handling. The legacy models are retained as an explicit fallback.
- Movement uses ground coordinates when available; water, fences and map bounds affect movement separately from projectile-blocking walls.
- Hostile summon targeting, friendly/ignored summon filtering and targeted ability guards.
- Versioned lobby, search, popup, daily-win and prestige templates with distinct state handlers.
- Updated brawler catalog and portraits without replacing existing fork playstyles.
- Instance-specific queues, adaptive state, control files and capture cleanup. API fields and live logs redact stored secrets.

## Validation and remaining work

Automated regression tests cover the browser/API/process boundaries, selection gating, model output decoding and game states. CPU and DirectML model inference and the live brawler search menu have been smoke-tested. Browser account loading, trophies and sequential navigation have also been checked.

Full matches after this migration, clean-machine dependency installation and rebuilt executables remain unverified. Upstream playstyle bundles and compressed match diagnostics were not copied because their contracts differ from this fork.

The repository contains code, models, resources, tests and blank config templates. Local credentials, account statistics, logs, generated queues, development archives and personal screenshots are not distributed.
