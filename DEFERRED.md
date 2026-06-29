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

## Phase S (Closed)

| ID | Item | Closure |
|---|---|---|
| DEF-S-SMOKE-001 | Staging smoke data cleanup. Assessed: staging has 5 real users, 0 agencies, 0 memberships — no smoke data present. **Closed — no action needed.** Production gate added: `app/utils/validation.py` with placeholder name/test email rejection on all creation endpoints + schemas. | S ✗ |

## Phase T (Deferred)

| ID | Item | Scope |
|---|---|---|
| DEF-S-ADMIN-MEM-001 | Admin membership view endpoint — `GET /api/v1/admin/users/{id}/memberships/` to let admin view any user's agency memberships without being logged in as that user. Frontend "View agency membership" link currently shows logged-in user's memberships. | Backend endpoint + frontend wiring |
| DEF-Q-UNBLOCK-002 | `_apply_membership_role_after_status_change` multi-membership edge case. When N>1 active memberships exist and one is blocked then unblocked (→ inactive), `_first_active_membership_agency_for_user` picks the first remaining membership, not necessarily the preferred one. | Backend fix |
| DEF-R-MSG-001 | In-app messaging — full conversational UI beyond basic reply threading. | Frontend |
| DEF-R-DUAL-MEMBERSHIP-001 | Dual-membership data cleanup: yahoo staging agent (`user_id=76` on staging) has `users.agency_id=1` + active membership in agency 9. Single operator DB query. | Operator SQL |
| T.2 — Conversational Reply Threading | WhatsApp-style quoted replies with `parent_reply_id` FK, quote preview chip, reply action on message bubbles, visual indentation, 10s polling. Full schema below. | Backend + Frontend |

### T.2 — Conversational Reply Threading Design

| Layer | Change |
|---|---|
| Backend migration | `parent_reply_id BIGINT NULL FK → inquiry_replies.reply_id` |
| Backend schema | `InquiryReplyResponse` gains `parent_reply: InquiryReplyResponse \| null` (one level, no recursion) |
| Backend CRUD | `joinedload parent` on `GET /inquiries/{id}/replies/` |
| Backend endpoint | `POST /reply/` accepts optional `parent_reply_id` |
| Frontend | Quote preview chip showing sender name + truncated body above the text input |
| Frontend | Hover/tap → "Reply" action visible on any message bubble |
| Frontend | Visual connector or indentation tying reply to parent |
| Polling | Move from 30s → 10s for chat feel |

True real-time (Supabase Realtime or SSE) is the correct long-term answer for any chat feature but remains deferred from the poll-based approach.

## Phase S close count

- Backend HEAD: `1b9d4e8`
- Frontend HEAD: `e1d2f04`
- Coverage: ≥95% (confirmed S.6 inquiry tests 89/89 passing, pyright 0)
- pyright: 0 errors
- tsc: 0 (pre-existing Phase R stats page errors only), lint 0, build 0
- S.1: Internal schema migration — three trigger functions moved from `public` to `internal`
- S.2: `last_login` + `is_active` fields, login tracking, deactivation endpoints
- S.3: Admin user segmentation backend — role/activity_state filters, counts endpoint
- S.4: Admin user segmentation frontend — six tabs, deactivate/reactivate UI
- S.5: Agency owner Inactive agent tab — client-side filter on roster `last_login`
- S.6: Multi-turn reply threading backend — seeker reply, `author_role`, edit endpoint
- S.7: Multi-turn reply thread UI — ReplyThread component, full thread for both parties
- S.8: Production gating — `app/utils/validation.py`, placeholder name/test email rejection on all creation schemas. DEF-S-SMOKE-001 closed.