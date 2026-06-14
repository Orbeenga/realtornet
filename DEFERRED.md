# Deferred Items — Backend

## Phase N

| ID | Item | Phase |
|---|---|---|
| DEF-N-ENDPOINTS-001 | Missing agency owner read endpoints — `GET /api/v1/properties/agency-queue/` (listings at `agency_review` for requesting agency_owner's agency), `GET /api/v1/properties/agency-inventory/` (live listings for requesting user's agency), `GET /api/v1/properties/pending-admin/` (`admin_review` listings for requesting agency_owner's agency). Currently the dashboard uses filtered versions of the general properties endpoint. | N |
| DEF-N-TRANSITIONS-001 | Missing transition `revoked → admin_rejected` — workbook Section 1.2 specifies admin can permanently reject a revoked listing. Endpoint `PATCH /api/v1/properties/{id}/reject-permanently/` not yet implemented. | N |
| DEF-N-NOTIFICATIONS-001 | Missing notification emails — `agency_review → agency_rejected` (agent email with reason), `draft → agency_review` (submission, no notification currently), `agency_review → admin_review` (approval, no notification currently). These fire points are specified in workbook Section 1.6 but not yet wired. | N |
| DEF-M-NOTIF-001 | In-platform notifications (notification bell, badge count, notification list, notification table). Deferred from Phase M. Phase N scoping decision: deferred to Phase O. Real-time push is Phase O; poll-based at 60s was Phase N MVP scope. Deferred because N.9 exit gates (mediation lifecycle, build) do not depend on it and clean scoping avoids mid-phase scope creep. | O |
