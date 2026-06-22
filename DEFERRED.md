# Deferred Items — Backend

## Phase Q

| ID | Item | Phase |
|---|---|---|
| DEF-P-BLOCK-001 | `blocked` membership status: block endpoint existed at HEAD `2aeddc2`; join request guard added for blocked users (403 on join request). **Closed Q.4** — Blocked tab + restricted CTA frontend deployed. | Q ✗ |
| DEF-P-RECONSIDER-001 | Reconsider CTA for rejected agency join requests. **Closed Q.5** — `PATCH /{agency_id}/join-requests/{request_id}/reconsider/` endpoint at `ac5546b`; Reconsider button frontend deployed. | Q ✗ |
| DEF-K-AUDIT-FK-001 | Smoke-user hard-delete blocked by audit FK. **Closed Q.7** — FK design is correct (CASCADE for user_id, SET NULL for actor_id). Cleanup scripts exist in `scripts/`. Soft-delete pattern recommended. | Q ✗ |
| DEF-006 | Storage bucket provisioning automation. **Closed Q.7** — bootstrap wired into startup, fail-open, three buckets provisioned, tested. Railway `preDeployCommand` enhancement deferred to Phase R. | Q ✗ |
| DEF-007 | psycopg3 prepared statement corruption in dev. **Closed Q.7** — `prepare_threshold=None` already set in `app/core/database.py:35`. Fix is deployed and stable. | Q ✗ |
| DEF-FE-004A | Residual core-js dependency audit. **Closed Q.7** — `core-js` npm package is NOT in the dependency tree. The `__core-js_shared__` reference is Next.js 16's internal polyfill runtime. No action needed. | Q ✗ |
| DEF-L-ADMIN-AUDIT-001 | Admin audit UI section (frontend). **Closed Phase L** — UI section exists at frontend HEAD `b04601d` in `AdminAnalyticsClient.tsx`. | L ✗ |
| DEF-N-ENDPOINTS-001 | Agency owner read endpoints implemented at `ac5546b`; frontend Q.2 deployed. **Closed Q.2**. | Q ✗ |
| DEF-N-TRANSITIONS-001 | `revoked → admin_rejected` endpoint existed at HEAD `2aeddc2`. Reject Permanently button frontend Q.3 deployed. **Closed Q.3**. | Q ✗ |
| DEF-N-NOTIFICATIONS-001 | All three notification email fire points wired and tested at HEAD `2aeddc2`. **Closed O/Q.1**. | O ✗ |
| DEF-M-NOTIF-001 | In-platform notifications: bell icon, notification list, badge count, 7 fire points. Poll-based at 60s. **Closed Phase O**. Real-time push remains deferred. | O ✗ |

## Phase R (Deferred)

| ID | Item | Phase |
|---|---|---|
| DEF-J-EMAIL-DOMAIN-001 | Real-user email delivery blocked until a verified sender domain is configured in Resend and Railway `MAIL_FROM` is updated. Operator action only — no code changes needed. | R |
| DEF-R-MSG-001 | In-app messaging + auto Mark Responded on reply. Manual Mark Responded button is correct MVP behavior until this lands. | R |
| DEF-R-AGENT-STATS-001 | Agent personal stats tab (own listings by status, rejected/revoked breakdown, inquiries received, response rate, agency active memberships, rejected/revoked/blocked/left membership counts). | R |
| DEF-Q-UNBLOCK-001 | Agency-level unblock endpoint (`PATCH /agencies/{id}/members/{user_id}/unblock`) not implemented. | R |
| DEF-002 | Audit log retention policy. Trigger not reached (~31 creations, ~11 deletions in 30d at Phase Q close, 5 users). Revisit when audit_logs exceeds 10K rows or user count exceeds 500. | R |

## Phase Q close count

- Backend HEAD: `1875fed`
- Frontend HEAD: `739bd1b`
- pytest: 2059 passed, coverage 95.28%
- pyright: 0 errors
- tsc: 0, lint: 0, build: 0
- All 12 N.9 integration journeys confirmed passing
