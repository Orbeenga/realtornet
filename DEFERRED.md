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

## Phase R (Closed)

| ID | Item | Phase |
|---|---|---|
| DEF-J-EMAIL-DOMAIN-001 | Real-user email delivery blocked until a verified sender domain is configured in Resend and Railway `MAIL_FROM` is updated. Operator action only — no code changes needed. **Carried forward — operator action.** | R ✗ |
| DEF-J-LOC-001 | Location breadth/quality monitoring. Self-populating system live and working since Phase J. Production count: 63 locations (confirmed Phase R). No monitoring tooling warranted until user volume makes location data quality a reported user friction point. **Closed — no action needed.** | R ✗ |
| DEF-R-MSG-001 | In-app messaging + auto Mark Responded on reply. Manual Mark Responded button is correct MVP behavior until this lands. | S |
| DEF-R-NOM-001 | Nominatim self-hosted instance. Public API sufficient at current scale (1 req/sec throttle, 5-min cache, Nigeria-first filtering all in place). No rate limiting errors in Railway logs since Phase J (confirmed Phase R). **Closed — no action needed.** | R ✗ |
| DEF-002 | Audit log retention policy. Trigger not reached: production counts at Phase R close — `agent_membership_audit`: 4 rows, `audit_creations`: 31 (~31 creations in 30d), `audit_deletions`: 11 (~11 deletions in 30d), 5 users. **Deferred** — revisit when total audit rows exceed 10K or user count exceeds 500. | R ✗ |
| DEF-R-DUAL-MEMBERSHIP-001 | Dual-membership data cleanup: yahoo staging agent (`user_id=76`) has `users.agency_id=1` (Default Agency) + active membership in agency 9 (Apine). Listings created by this user auto-assign to Default Agency (no owner), blocking the N.9 agency-review transition. Root cause: R.5 unblock → `_first_active_membership_agency_for_user` returns Default Agency membership (the only remaining active after block/inactive of membership 9). No API path exists to update `users.agency_id` (UserUpdate schema omits it; Supabase service key blocked from `public` schema). **Operator action** — direct DB update via alembic migration or SQL console to set `users.agency_id=9 WHERE user_id=76`. | S |

## Phase S (Deferred)

| ID | Item | Phase |
|---|---|---|
| DEF-R-MSG-001 | In-app messaging + auto Mark Responded on reply. Manual Mark Responded button is correct MVP behavior until this lands. | S |
| DEF-R-DUAL-MEMBERSHIP-001 | Dual-membership data cleanup (see Phase R block above). No code changes needed — single operator DB query. | S |
| DEF-S-SMOKE-001 | Staging smoke data cleanup. Assessed S.8: staging has 5 real users, 0 agencies, 0 memberships — no smoke data present. **Closed — no action needed.** Validation gate added: `app/utils/validation.py` with placeholder name/test email rejection on all creation endpoints + schemas. | S ✗ |
| DEF-Q-UNBLOCK-002 | `_apply_membership_role_after_status_change` does not handle multi-membership edge case correctly: when a user has N>1 active memberships and one is blocked then unblocked (→ inactive), `_first_active_membership_agency_for_user` picks the first remaining active membership regardless of which one the user prefers. Consider adding a `preferred_agency_id` column to users table, or having `_apply_membership_role_after_status_change` prefer the membership being acted upon. | S |

## Phase R close count

- Backend HEAD: `ee0806c`
- Frontend HEAD: `6750e1d`
- Coverage: 95.16% (pytest — single-file runs excluded, no production code changes in Phase R)
- pyright: 0 errors
- tsc: 0, lint: 0
- R.3: `latest_reply`/`reply_count` wiring — inquiry reply lifecycle confirmed working on staging (create inquiry → reply → verify `reply_count=1` and `latest_reply.body`)
- R.4: agent personal stats endpoint + `/account/stats` page — renders 2 live listings, 1 inquiry received, 100% response rate (user-confirmed screenshot)
- R.5: unblock endpoint + frontend CTA — staging validated via curl: block (status=blocked) → unblock (status=inactive) → reapply (404, user can submit new join request). Pre-existing bug fixes: block `status_value="active"`→`"blocked"`; `_first_active_membership_agency_for_user` `.scalar_one_or_none()`→`.scalars().first()`.
- R.6: Operational closure documented — production audit counts verified, Nominatim rate limit confirmed clean, DEFERRED.md updated with evidence. Both PRs merged to main.
- R.7: Integration validation — Part A (inquiry reply lifecycle) PASS, Part C (unblock regression) PASS. Part B (N.9 12-step lifecycle) partially tested: listing creation + submit-for-review + events audit trail + admin historical views all work. Full N.9 cycle gated by dual-membership data issue (DEF-R-DUAL-MEMBERSHIP-001).