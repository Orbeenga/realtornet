# RealtorNet — Backend Phase K Remaining Items

**Phase:** K — active
**Pre-flight law:** Read CLAUDE.md (root + backend) before starting. List what is locked. No workarounds.

## Production guardrails (non-negotiable)

- **Production Supabase project:** `avkhpachzsbgmbnkfnhu` — all production DB work targets this project only.
- **Dev project `umhtnqxdvffpifqbdtjs` is deprecated** — do not use it for any production work.
- **Railway backend:** live at `https://realtornet-production.up.railway.app`
- **Real production accounts — DO NOT TOUCH:** `user_id` **5, 74, 76, 85, 89**

## Context files

| File | Purpose |
|---|---|
| `CLAUDE.md` (root + `backend/`) | Locked decisions and phase state |
| `RealtorNet_Phase_K_Opening_Brief.md` | Phase K scope and relationship model |
| `docs/DEFERRED.md` | Open vs closed deferred items |
| This file | Backend dispatch tasks A–C |

## Quality gates (before any push)

- `pyright` → 0 errors
- `pytest -q` → all passing, coverage ≥ 95%
- `GET /healthz` → 200 on Railway

---

## Immediate — Commit CLAUDE.md Files

**Status:** Completed in commit `937ee42` (`Close Phase J docs and open Phase K`). Root `CLAUDE.md` states Phase K active; Phase J closed except `DEF-J-EMAIL-DOMAIN-001`.

**Remaining doc hygiene (optional):** commit `docs/DEFERRED.md` and `RealtorNet_Phase_J_Workbook.md` when ready — not blocking backend Tasks A–C.

---

## Task A — Admin Analytics Integrity Contradiction

**Problem:** Admin analytics summary shows `Health score: 100`, `Total issues: 0`, `High severity: 0` while the detail section lists high-severity integrity categories (`missing_created_by`, `missing_deleted_by`).

**Root cause:** Health score / issue counts computed independently from the integrity detail list.

**Fix:**

1. Find endpoints powering admin analytics health score and integrity issue list.
2. Confirm both use the same underlying integrity check results.
3. Summary must be a mathematical summary of the detail.

**Done-when:** Summary counts match detail list. pyright 0, pytest ≥ 95%.

---

## Task B — Smoke Agencies in Admin Queue

**Problem:** Admin agency approval queue still shows Codex smoke/nav agencies after user cleanup.

**Check:**

```sql
SELECT a.agency_id, a.name, a.status, a.created_at, a.owner_id
FROM agencies a
WHERE a.deleted_at IS NULL
ORDER BY a.agency_id;
```

Soft-delete smoke agencies (name contains Codex/Smoke/Nav/Test/Demo, numeric-only, or created by deleted users) when they have no real members or verified listings.

**Do not touch:** Agency 1 (Default Agency), Agency 9 (Apine), any agency with real active members or verified listings.

**Done-when:** Admin queue shows only real agencies. Report before/after agency count.

---

## Task C — Backend Support for My Listings by Agency

Frontend needs `GET /api/v1/properties/?agency_id={id}` for agency_owner "My Listings".

If missing:

- Add `agency_id: Optional[int] = None` to properties list query params
- Filter `WHERE properties.agency_id = agency_id` when present
- Role gate: agent / agency_owner / admin only (not seekers)
- Add test

**Done-when:** `GET /api/v1/properties/?agency_id=9` returns only Agency 9 listings. Frontend Task 9 can proceed.

---

## Execution order

1. ~~CLAUDE.md commit~~ — done (`937ee42`)
2. **Task B** — smoke agency cleanup (data only)
3. **Task C** — `agency_id` filter on properties list
4. **Task A** — admin analytics integrity fix

**Frontend dependency:** Frontend Task 9 is blocked until Task C is confirmed live on production.
