# Final UX release verification

Date: 2026-10-15. Scope: clearer onboarding, readable minimalist workspace, simpler copy and technical disclosures, and the recording script. Python solver, reconciliation pipeline, entity resolver, models, ledger exporter, and all existing backend test cases remain unchanged.

## Functional checks

| Check | Evidence |
| --- | --- |
| Static source audit | PASS across 26 runtime files, including the new welcome component |
| Backend tests | 66 passed, including all original 54 tests |
| Frontend tests | 7 passed |
| Production build | Vite build passed |
| Workspace browser suite | 10 real browser/API checks passed |
| Hard-pass browser suite | 12 real browser/API checks passed |
| Existing smoke suite | Passed, including keyboard focus, exceptions, exports, and mobile overflow |
| Accounting truth on failure | One-cent mutation remains unmatched with no journal; summary now explicitly says “No journal generated” |

The UI browser checks were updated for the new user-visible labels and for opening the actual Solver details disclosure before reading its metrics. No response mocks, artificial delays, solver shortcuts, or precomputed matches were added.

## Readability and responsive evidence

Batched captures covered the actual welcome screen, composer, and computed benchmark at 1440×1000 desktop, 834×1112 tablet, and 390×844 mobile. All three sizes had zero document/composer horizontal overflow and zero JavaScript runtime errors. Accounting tables intentionally scroll horizontally rather than compress financial data.

Computed welcome body text: 17px desktop, 16px tablet, 15px mobile. Financial values remain tabular; deposit amounts are 14px on desktop and mobile. Mobile composer input text is 16px.

A fresh independent finish reviewer identified three material issues: a clipped sticky composer action, mobile deposit values reduced below the intended size, and duplicated technical telemetry outside its disclosure. One corrective batch resolved those findings; the reviewer's verdict pass marked all three resolved and gave **ship** at that scope. Exact composer-button bounds were also asserted fully inside both desktop and mobile viewports. The unmatched-journal status/checkmark correction received a separate code/wording confirmation.

This is expert review and automated verification, not a human ten-second usability study. No such measured usability claim is made.

## User-facing deliverables

- A plain-language welcome screen with one primary create action and clear import/sample alternatives.
- Three business outcomes after reconciliation; actual timing and search nodes remain available on demand.
- Real invoice-state calculation, balanced accounting proof, editable inputs, source claims, and exports preserved.
- [Pitch script](PITCH_VIDEO.md): approximately three minutes, timed say/show/click instructions, exact custom inputs, optional scenes below five minutes, and a 2:00 AM PKT submission schedule with recording/upload buffer.
- [Research and decisions](UX_RESEARCH.md), updated token-bearing design documentation, and current screenshots in README.

The release is deployed through the existing GitHub → Vercel production integration. Post-deployment browser checks run against https://settlesum.vercel.app after the pushed commit becomes READY; GitHub Actions independently reruns static checks, all tests, and the production build. Earlier audit documents remain historical records of their original scope.
