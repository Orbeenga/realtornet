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
| DEF-R-AGENT-STATS-001 | Agent personal stats tab (own listings by status, rejected/revoked breakdown, inquiries received, response rate, agency active memberships, rejected/revoked/blocked/left membership counts). **Closed R.4** — `GET /api/v1/analytics/agents/me/stats/` endpoint + `/account/stats` frontend page + nav link for agent/agency_owner roles deployed. | R ✗ |
| DEF-Q-UNBLOCK-001 | Agency-level unblock endpoint (`PATCH /agencies/{id}/agents/{membership_id}/unblock/`). **Closed R.5** — endpoint with role gate (agency_owner), state gate (blocked only), transitions to `inactive` with `audit_action='reinstated'`. Frontend Unblock CTA on Blocked tab. Deployed + staging validated. | R ✗ |

## Phase R (Deferred)

| ID | Item | Phase |
|---|---|---|
| DEF-J-EMAIL-DOMAIN-001 | Real-user email delivery blocked until a verified sender domain is configured in Resend and Railway `MAIL_FROM` is updated. Operator action only — no code changes needed. | R |
| DEF-J-LOC-001 | Location breadth/quality monitoring. Self-populating system live and working since Phase J. Production count: 63 locations (confirmed Phase R). No monitoring tooling warranted until user volume makes location data quality a reported user friction point. | R |
| DEF-R-MSG-001 | In-app messaging + auto Mark Responded on reply. Manual Mark Responded button is correct MVP behavior until this lands. | R |
| DEF-R-NOM-001 | Nominatim self-hosted instance. Public API sufficient at current scale (1 req/sec throttle, 5-min cache, Nigeria-first filtering all in place). No rate limiting errors in Railway logs since Phase J (confirmed Phase R). Evaluate when rate limiting becomes a confirmed operational constraint. | R |
| DEF-002 | Audit log retention policy. Trigger not reached: production counts at Phase R close — `agent_membership_audit`: 4 rows, `audit_creations`: 31 (~31 creations in 30d), `audit_deletions`: 11 (~11 deletions in 30d), 5 users. Revisit when total audit rows exceed 10K or user count exceeds 500. | R |

## Phase R close count

- Backend HEAD: `d3423cc`
- Frontend HEAD: `6750e1d`
- Coverage: 95.20% (pytest — single-file runs excluded)
- pyright: 0 errors
- tsc: 0, lint: 0
- R.3: `latest_reply`/`reply_count` wiring confirmed working
- R.4: agent personal stats deployed + tested
- R.5: unblock endpoint + frontend CTA validated on staging (blocked → inactive → reapply)
