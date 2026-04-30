# RealtorNet Phase H Workbook

Scale, Email & Platform Maturity. This Markdown companion mirrors the repository
root `.docx` workbook so Phase H instructions remain easy to inspect in code
review and agent sessions.

## Preflight

| Item | Value |
|---|---|
| Phase G closed | April 29, 2026; all exit criteria met, `CLAUDE.md` committed to both repos |
| Backend | v0.5.3+ on Railway, 1803 tests, 92.99% coverage, 0 Pyright errors |
| Frontend | Next.js 16.2.1 on Vercel, Lighthouse mobile LCP 1.5s |
| Stack | Next.js, TypeScript, Supabase, TanStack Query, FastAPI |
| Production Supabase | `avkhpachzsbgmbnkfnhu`; do not mix with dev project `umhtnqxdvffpifqbdtjs` |
| Production DB head | `c8f3b2a91e44` |

## Governing Principle

Phase H converts the agency-first marketplace into a platform that communicates
with users, performs under real traffic, and operates without manual
intervention. The three pillars are email delivery, performance maturity, and
operational resilience.

## Phase H Streams

| Stream | Focus | Phases | Blocks launch? |
|---|---|---|---|
| A | Email notification service | H.1-H.2 | Yes |
| B | Frontend performance and UX completeness | H.3-H.5 | No, but required before scaling |
| C | Operational resilience and test coverage | H.6 | No, runs throughout |

## Opening Backlog

| ID | Item | Priority | Owner |
|---|---|---|---|
| `DEF-H-EMAIL-001` | Email notification service for agency approval, rejection, and invitations | High | Backend |
| `DEF-H-INQ-001` | Agency-wide inquiry aggregation endpoint, `GET /agencies/{id}/inquiries` | High | Backend |
| `DEF-H-MOD-001` | Moderation UI consistency across full enum lifecycle | High | Frontend |
| `DEF-G-TBT-001` | TBT reduction, revised Phase H target 300ms | Medium | Frontend |
| `DEF-H-UX-001` | Error and empty states for agency/profile/dashboard surfaces | Medium | Frontend |
| `DEF-H-NAV-001` | Admin Analytics docs/nav contract drift | Medium | Frontend |
| `DEF-H-ENUM-001` | Listing filter enums hardcoded in frontend | Medium | Frontend |
| `DEF-H-STORE-001` | `storage_services.py` coverage from 20% to at least 80% | Medium | Backend |
| `DEF-H-EMAIL-TEST` | `email_tasks.py` and `email_utils.py` coverage to at least 80% | Medium | Backend |
| `DEF-002` | Audit log retention policy after 60 days real traffic | Low | Backend |
| `DEF-007` | Validate psycopg3 prepared statement closure | Low | Backend |
| `DEF-G-POLYFILL-001` | Residual third-party `core-js` cleanup | Low | Frontend |
| `DEF-H-DOMAIN` | Custom domain setup | Low | Ops |
| `DEF-H-MAP-001` | Advanced map view | Low | Frontend |
| `DEF-H-GEO-001` | Nominatim/OSM geocoding | Low | Backend |
| `DEF-H-SMOKE` | Smoke runner auto-teardown | Low | Backend |

## H.1 Email Infrastructure

Goal: wire a real email service and extend existing Mailgun welcome and
verification task scaffolding to agency workflow events.

| Task | Notes |
|---|---|
| Wire `MAILGUN_API_KEY` / `MAILGUN_DOMAIN` to Railway | Keys exist in Mailgun dashboard; add to backend service variables |
| Audit existing `email_tasks.py` | Confirm welcome/verification dispatch; if Celery worker is inactive, switch to sync send |
| Add agency approval email | Fires on `PATCH /admin/agencies/{id}/approve/`; applicant email; subject `Your agency application was approved`; include login CTA |
| Add agency rejection email | Fires on `PATCH /admin/agencies/{id}/reject/`; applicant email; subject `Agency application update`; include reason if set |
| Add agent invitation email | Fires on `POST /agencies/{id}/invite/`; invited email; invite link with token; expires in 72h |
| Add join request status email | Fires when agency owner accepts or declines a join request; notify requester |
| Raise `email_tasks.py` coverage | Target at least 80% |
| Raise `email_utils.py` coverage | Target at least 80% |

Done when: all six email types send in staging, Mailgun dashboard shows
delivery, `email_tasks.py` and `email_utils.py` are at least 80% covered, and no
email fires in dry-run test mode.

## H.2 Agency Inquiry Aggregation

Add `GET /api/v1/agencies/{id}/inquiries/`, role-gated to `agency_owner` and
admin, returning paginated `InquiryExtendedResponse` results without N+1 queries.

## H.3 Moderation UI Consistency

Replace frontend boolean `is_verified` checks with full `moderation_status`
handling. All four states must render correctly and public feeds must hide every
non-verified listing.

## H.4 TBT Reduction And Bundle Hygiene

Target Lighthouse TBT below 300ms on `/properties` and `/agencies`. Use trace
evidence, dynamic imports, RSC migration where appropriate, and bundle analysis.

## H.5 UX Completeness And Enum-Driven Filters

Close silent error states, add loading skeletons where missing, make listing
filters enum-driven, and correct frontend `CLAUDE.md` nav/docs drift.

## H.6 Operational Resilience

Raise `storage_services.py` coverage to at least 80%, validate `DEF-007`, add
smoke-runner auto-teardown, decide audit retention posture, confirm storage
bucket deploy-time validation, and maintain pyright/pytest gates.

## Exit Criteria

| Criterion | Verification |
|---|---|
| Six email types send in staging | Mailgun dashboard delivery confirmation |
| `email_tasks.py` and `email_utils.py` at least 80% | Coverage report |
| Agency inquiry aggregation endpoint live | Paginated agency-owner response |
| No N+1 queries on agency inquiry endpoint | `EXPLAIN ANALYZE` evidence |
| No frontend boolean `is_verified` references | grep / tsc |
| All four moderation states render | Agent and admin walkthrough |
| Public feed excludes non-verified listings | Smoke test |
| Lighthouse TBT below 300ms | `/properties` and `/agencies` reports |
| UX error/empty states handled | Manual walkthrough |
| Listing filters source enums from contract | Code review |
| `storage_services.py` at least 80% | Coverage report |
| `DEF-007` validated | Evidence committed or deferred with evidence |
| Smoke runner auto-teardown | Script confirmation |
| Pyright 0 errors | `venv pyright` |
| Pytest passing, coverage at least 93% | pytest coverage gate |
| Frontend type/build gates pass | `pnpm tsc --noEmit`, `pnpm build` |
| `DEFERRED.md` and `CLAUDE.md` files updated | Phase H close state committed |

## Phase I Deferrals

Advanced Mapbox map view, Nominatim/OSM geocoding, agency owner self-service
onboarding, full residual `core-js` elimination, TBT below 100ms, advanced admin
analytics, saved search notifications, custom domain setup, audit retention at
scale, and public agency directory aggregation optimisation.
