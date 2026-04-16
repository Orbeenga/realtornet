"""Deploy-time Supabase Storage bucket validation/provisioning."""

from __future__ import annotations

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.services.storage_bucket_bootstrap import ensure_required_storage_buckets


def main() -> int:
    try:
        results = ensure_required_storage_buckets()
    except Exception as exc:
        print(f"Storage bucket bootstrap failed: {exc}", file=sys.stderr)
        return 1

    for result in results:
        print(
            f"{result.name}: {result.action} "
            f"(public={result.public}, mime_types={list(result.allowed_mime_types)})"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
