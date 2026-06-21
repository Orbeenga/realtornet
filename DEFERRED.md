# Deferred Items — Backend

## Phase N

| ID | Item | Phase |
|---|---|---|
| DEF-N-ENDPOINTS-001 | Missing agency owner read endpoints — `GET /api/v1/properties/agency-queue/` (listings at `agency_review` for requesting agency_owner's agency), `GET /api/v1/properties/agency-inventory/` (live listings for requesting user's agency), `GET /api/v1/properties/pending-admin/` (`admin_review` listings for requesting agency_owner's agency). **Closed Phase Q** — all three endpoints implemented at commit `ac5546b`. pyright 0, pytest passing. | N ✗ |
| DEF-N-TRANSITIONS-001 | Missing transition `revoked → admin_rejected` — `PATCH /api/v1/properties/{id}/reject-permanent/`. **Closed Phase N** — endpoint already existed at HEAD `2aeddc2`, committed as part of Phase N post-close fixes. | N ✗ |
| DEF-N-NOTIFICATIONS-001 | Missing notification emails — `agency_review → agency_rejected` (agent email with reason), `draft → agency_review` (submission, no notification currently), `agency_review → admin_review` (approval, no notification currently). **Closed Phase O** — all three fire points wired and tested: `send_submission_notification_email`, `send_agency_approval_notification_email`, `send_property_moderation_email`. Verified at HEAD `2aeddc2`, 11 passing tests in `test_phase_n4_notifications.py`. | N ✗ |
| DEF-M-NOTIF-001 | In-platform notifications (notification bell, badge count, notification list, notification table). **Closed Phase O** — poll-based at 60s implemented, 7 fire points wired, NotificationBell in Navbar. Real-time push remains deferred. | O ✗ |

## Phase Q

| ID | Item | Phase |
|---|---|---|
| DEF-P-BLOCK-001 | `blocked` membership status: block endpoint existed, join request guard added for blocked users (403 on join request). UI for Blocked tabs and restricted CTA deferred to Q.4 frontend. **Closed backend Q.4** — `PATCH /block/` existed at HEAD `2aeddc2`; join request guard added at commit `ac5546b`. | Q |
| DEF-P-RECONSIDER-001 | Reconsider CTA for rejected agency join requests. **Closed Q.5** — `PATCH /{agency_id}/join-requests/{request_id}/reconsider/` endpoint added at commit `ac5546b`. | Q ✗ |
| DEF-K-AUDIT-FK-001 | Smoke-user hard-delete blocked by audit FK. **Closed Q.7** — FK design is correct (CASCADE for user_id, SET NULL for actor_id). Cleanup scripts exist in `scripts/`. Soft-delete pattern recommended. | Q ✗ |
| DEF-006 | Storage bucket provisioning automation. **Closed Q.7** — bootstrap wired into startup, fail-open, three buckets provisioned, tested. Optional Railway `preDeployCommand` enhancement deferred to Phase R. | Q ✗ |
| DEF-007 | psycopg3 prepared statement corruption in dev. **Closed Q.7** — `prepare_threshold=None` already set in `app/core/database.py:35`. Fix is deployed and stable. | Q ✗ |
| DEF-FE-004A | Residual core-js dependency audit. **Closed Q.7** — `core-js` npm package is NOT in the dependency tree. The `__core-js_shared__` reference is Next.js 16's internal polyfill runtime. No action needed. | Q ✗ |
| DEF-L-ADMIN-AUDIT-001 | Admin audit UI section (frontend). **Closed Phase L** — UI section already exists at frontend HEAD `b04601d` in `AdminAnalyticsClient.tsx`. | L ✗ |
| DEF-002 | Audit log retention policy. **Deferred to Phase R** — no `audit_logs` table exists; audit data lives in per-table columns and DB views (`audit_creations`, `audit_deletions`, `audit_recent_changes`). Trigger condition (10K rows or 500 users) not yet reached (~4 users). | R |
