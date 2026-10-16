# Email layout acceptance — 2026-10-16

Task: `BHM-EMAIL-LAYOUT-2026-10-16`. Source baseline: `4d751f4f7c709a349fb1f521e4424f188cc46aad`, local `main` and fresh GitHub `origin/main` equal before changes. Fetch and push URLs: `https://github.com/ProgresLab/BHM-mailer.git`.

## Scope and boundaries

Only `app/email_renderer.py` changes application behavior:

- HTML card, MSO width wrapper and banner width increase from 600 to 720 px. Fluid width, image aspect ratio, original content padding, fonts and colors remain.
- CTA presentation table fills the content area; white centered text, existing `#11263A`, 6 px radius. Zero-font spacer rows provide 26 px before and 24 px after; the contact table has no additional top margin when a valid CTA exists. Without a CTA, its original 18 px margin remains. Outlook receives cell padding via `mso-padding-alt`.
- The original white card and border use separate borders/zero spacing, 8 px radius and clipping. Clients ignoring radius retain a square bordered table. No VML or new dependency.

Editor, logo bytes, footer markup, URLs, unsubscribe, SQLite, SMTP, worker and campaign mechanisms are unchanged. Existing saved campaign HTML and historical send snapshots are not regenerated. This changes newly rendered HTML; no operational activation/restart is included. The editor's existing banner width hint was left untouched under the protected-editor scope.

## Validation evidence

- `.venv/Scripts/python -m compileall app`: exit 0.
- `.venv/Scripts/python -m unittest discover -s tests -v`: **47 tests OK**, 43.963 s, isolated SQLite and fake SMTP. Includes banner/MIME, legacy logo, invalid CTA, draft lock, historical snapshot preservation, unsubscribe and worker regressions. Simulation: 1000 fake attempts, minimum 20 s interval, five automatic breaks; no real message or SMTP connection.
- `output/email-layout-qa/generate.py`: baseline renderer loaded directly from Git `4d751f4`; current renderer compared using the same synthetic inputs. **10 fixtures** (PL/EN × banner, original logo, missing-header-logo text fallback, no CTA, invalid CTA). Text, ordered URLs, image CIDs/alt text, footer and plain text equal. HTML checks confirm 720 px attributes/max-width/MSO, table spacers and Outlook padding.
- `output/email-layout-qa/check.cjs`: **30 Chromium renders** (before/after × five variants × viewport 1200/390/360). No horizontal overflow at either mobile width, no JS errors, no external requests. Original logo decodes; banner retains 3:1 aspect. Additional square-corner fallback screenshot verified in Chromium.
- Measured after-change card widths: **720 / 366 / 336 px**. CTA widths: **662 / 308 / 278 px**, equal to the available content width. CTA-to-contact gap: **24 px** at all three sizes. Card radius 8 px, CTA radius 6 px; white/navy colors verified via computed style.
- Visually reviewed desktop before/after, 360 px before/after, original logo at 390 px and missing-header-logo fallback at 360 px. All 31 screenshots are in `output/playwright/email-layout/`; content and browser measurements are in `output/email-layout-qa/{content-checks,browser-checks}.json`. These synthetic local artifacts are ignored by Git. Preview copies substitute CID images with data URIs only for browser display; raw output HTML keeps CIDs.

Representative screenshots:

| View | Before | After |
| --- | --- | --- |
| Desktop 1200 | `output/playwright/email-layout/before-banner-1200.png` | `output/playwright/email-layout/after-banner-1200.png` |
| Mobile 390 | `output/playwright/email-layout/before-banner-390.png` | `output/playwright/email-layout/after-banner-390.png` |
| Mobile 360 | `output/playwright/email-layout/before-banner-360.png` | `output/playwright/email-layout/after-banner-360.png` |

## Process cleanup and limitations

QA rendered local files; no test HTTP server or application lifespan/worker was started. Playwright closed its browser in `finally`; unittest completed. Read-only process inventory found no remaining layout-QA browser or script. Ports 8017/8018/8019 were free before and after QA.

At initial preflight, 8000 listened under PID14944. A later read-only port check found no listener on 8000. No process-stop, kill or restart command was issued in this task; cause of that external runtime change is unverified. Do not infer active operational acceptance from this QA.

Native Outlook/Gmail/Apple Mail rendering and delivery were not tested. MSO width/padding and square-corner degradation are code-reviewed/browser-simulated, not native Outlook proof. No real email, operational data write, `.env` edit, deployment or historical snapshot update.

## Context Pack Closeout

`AGENTS.md`, `PROJECT_BRIEF.md` and `README.md` reviewed. AGENTS responsibilities unchanged; README documents rendering scope; V01–V06 added to the existing acceptance register and exactly one task Change Log entry added. Prior uncommitted activation documentation is preserved and excluded from this task's commit. Publication is limited to the reviewed renderer and this task's documentation; screenshots, synthetic HTML, databases, logs, uploads and secrets remain excluded. Final commit and verified remote SHA are reported in the chat/Git history.
