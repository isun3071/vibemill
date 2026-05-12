"""Supabase client.

The orchestrator pushes state to Supabase after each cron tick. SQLite is
the source of truth; Supabase is the public mirror.

Two surfaces:
- Tables: PostgREST upserts via /rest/v1/{table}, with the service role key.
- Storage: screenshot bytes via /storage/v1/object/{bucket}/{path}.

The 'screenshots' storage bucket must exist in the Supabase project. If it
does not, upload_screenshot raises with a clear message. Bucket creation
is a one-time manual step: Supabase dashboard -> Storage -> New bucket
-> 'screenshots' -> public.
"""

from __future__ import annotations

import logging
from typing import Any

import httpx
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from ..config import get_settings

log = logging.getLogger(__name__)

_TIMEOUT_S = 30
SCREENSHOT_BUCKET = "screenshots"


class SupabaseError(RuntimeError):
    pass


def _rest_headers(*, prefer: str | None = None) -> dict[str, str]:
    s = get_settings()
    key = s.SUPABASE_SERVICE_ROLE_KEY.get_secret_value()
    h = {
        "apikey": key,
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json",
    }
    if prefer:
        h["Prefer"] = prefer
    return h


def _storage_headers(*, content_type: str | None = None) -> dict[str, str]:
    s = get_settings()
    key = s.SUPABASE_SERVICE_ROLE_KEY.get_secret_value()
    h = {"apikey": key, "Authorization": f"Bearer {key}"}
    if content_type:
        h["Content-Type"] = content_type
    return h


def _base() -> str:
    return get_settings().SUPABASE_URL.rstrip("/")


@retry(
    reraise=True,
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=1, max=4),
    retry=retry_if_exception_type((httpx.TransportError,)),
)
def _request(method: str, url: str, **kwargs: Any) -> httpx.Response:
    return httpx.request(method, url, timeout=_TIMEOUT_S, **kwargs)


def upsert_rows(table: str, rows: list[dict[str, Any]], *, on_conflict: str = "id") -> None:
    """Upsert a batch of rows into `table`. No-op on empty input."""
    if not rows:
        return
    url = f"{_base()}/rest/v1/{table}?on_conflict={on_conflict}"
    r = _request(
        "POST",
        url,
        headers=_rest_headers(prefer="resolution=merge-duplicates,return=minimal"),
        json=rows,
    )
    if r.status_code not in (200, 201, 204):
        raise SupabaseError(f"upsert {table} ({len(rows)} rows): HTTP {r.status_code}: {r.text[:400]}")


def assert_verifier_columns() -> None:
    """Verify migration 002 has been applied to the Supabase apps table.

    PostgREST has no information_schema endpoint, so we probe the columns by
    attempting a select. If verifier_verdict + verifier_notes exist, returns
    200 with an empty body. If either is missing, returns 400 with the
    column name in the error.
    """
    url = f"{_base()}/rest/v1/apps?select=verifier_verdict,verifier_notes&limit=0"
    r = _request("GET", url, headers=_rest_headers())
    if r.status_code in (200, 206):
        return
    raise SupabaseError(
        "migration 002 (verifier_verdict + verifier_notes) is missing on the "
        f"Supabase apps table. HTTP {r.status_code}: {r.text[:200]}. "
        "Apply migrations/supabase/002_add_verifier_columns_supabase.sql "
        "manually in the Supabase SQL editor."
    )


def assert_model_rotation_columns() -> None:
    """Verify migration 003 has been applied to the Supabase apps table.

    Same probe pattern as assert_verifier_columns. If generator_model +
    readme_model exist, returns 200 with an empty body. If either is missing,
    returns 400 with the column name in the error.
    """
    url = f"{_base()}/rest/v1/apps?select=generator_model,readme_model&limit=0"
    r = _request("GET", url, headers=_rest_headers())
    if r.status_code in (200, 206):
        return
    raise SupabaseError(
        "migration 003 (generator_model + readme_model) is missing on the "
        f"Supabase apps table. HTTP {r.status_code}: {r.text[:200]}. "
        "Apply migrations/supabase/003_add_model_rotation_columns.sql "
        "manually in the Supabase SQL editor."
    )


def assert_committed_path_column() -> None:
    """Verify migration 004 (committed_path boolean) has been applied to
    the Supabase apps table. Same probe pattern as the others."""
    url = f"{_base()}/rest/v1/apps?select=committed_path&limit=0"
    r = _request("GET", url, headers=_rest_headers())
    if r.status_code in (200, 206):
        return
    raise SupabaseError(
        "migration 004 (committed_path) is missing on the Supabase apps "
        f"table. HTTP {r.status_code}: {r.text[:200]}. Apply "
        "migrations/supabase/004_add_committed_path_column.sql manually "
        "in the Supabase SQL editor."
    )


def assert_readme_persona_column() -> None:
    """Verify migration 005 (readme_persona text) has been applied to the
    Supabase apps table."""
    url = f"{_base()}/rest/v1/apps?select=readme_persona&limit=0"
    r = _request("GET", url, headers=_rest_headers())
    if r.status_code in (200, 206):
        return
    raise SupabaseError(
        "migration 005 (readme_persona) is missing on the Supabase apps "
        f"table. HTTP {r.status_code}: {r.text[:200]}. Apply "
        "migrations/supabase/005_add_readme_persona_column.sql manually "
        "in the Supabase SQL editor."
    )


def assert_tier_columns() -> None:
    """Verify migration 006 (tier + web_searched + search_queries_count +
    search_total_cost) has been applied to the Supabase apps table."""
    url = (
        f"{_base()}/rest/v1/apps"
        "?select=tier,web_searched,search_queries_count,search_total_cost&limit=0"
    )
    r = _request("GET", url, headers=_rest_headers())
    if r.status_code in (200, 206):
        return
    raise SupabaseError(
        "migration 006 (tier columns) is missing on the Supabase apps "
        f"table. HTTP {r.status_code}: {r.text[:200]}. Apply "
        "migrations/supabase/006_add_tier_columns.sql manually in the "
        "Supabase SQL editor."
    )


def assert_file_count_column() -> None:
    """Verify migration 007 (file_count integer) has been applied to the
    Supabase apps table."""
    url = f"{_base()}/rest/v1/apps?select=file_count&limit=0"
    r = _request("GET", url, headers=_rest_headers())
    if r.status_code in (200, 206):
        return
    raise SupabaseError(
        "migration 007 (file_count) is missing on the Supabase apps "
        f"table. HTTP {r.status_code}: {r.text[:200]}. Apply "
        "migrations/supabase/007_add_file_count_column.sql manually in the "
        "Supabase SQL editor."
    )


def assert_layout_archetype_column() -> None:
    """Verify migration 008 (layout_archetype text) has been applied to the
    Supabase apps table. Bundle C: layout-archetype rotation within Tracker."""
    url = f"{_base()}/rest/v1/apps?select=layout_archetype&limit=0"
    r = _request("GET", url, headers=_rest_headers())
    if r.status_code in (200, 206):
        return
    raise SupabaseError(
        "migration 008 (layout_archetype) is missing on the Supabase apps "
        f"table. HTTP {r.status_code}: {r.text[:200]}. Apply "
        "migrations/supabase/008_add_layout_archetype_column.sql manually in "
        "the Supabase SQL editor."
    )


def assert_synthetic_blend_columns() -> None:
    """Verify migration 009 (synthetic_track + blend_partner_archetype) has
    been applied to the Supabase apps table. Bundle G."""
    url = (
        f"{_base()}/rest/v1/apps"
        "?select=synthetic_track,blend_partner_archetype&limit=0"
    )
    r = _request("GET", url, headers=_rest_headers())
    if r.status_code in (200, 206):
        return
    raise SupabaseError(
        "migration 009 (synthetic_track + blend_partner_archetype) is missing "
        f"on the Supabase apps table. HTTP {r.status_code}: {r.text[:200]}. "
        "Apply migrations/supabase/009_add_synthetic_blend_columns.sql "
        "manually in the Supabase SQL editor."
    )


def assert_deploy_target_columns() -> None:
    """Verify migration 010 (deploy_target + hf_space_url) has been applied
    to the Supabase apps table. Bundle H: Python rail via HF Spaces."""
    url = f"{_base()}/rest/v1/apps?select=deploy_target,hf_space_url&limit=0"
    r = _request("GET", url, headers=_rest_headers())
    if r.status_code in (200, 206):
        return
    raise SupabaseError(
        "migration 010 (deploy_target + hf_space_url) is missing on the "
        f"Supabase apps table. HTTP {r.status_code}: {r.text[:200]}. "
        "Apply migrations/supabase/010_add_deploy_target_columns.sql "
        "manually in the Supabase SQL editor."
    )


def upload_screenshot(app_id: str, jpeg_bytes: bytes) -> str:
    """Upload a JPEG to the screenshots bucket. Returns the public URL.

    Path layout: {bucket}/{app_id}.jpg. Re-uploads overwrite (upsert=true).
    """
    object_path = f"{app_id}.jpg"
    url = f"{_base()}/storage/v1/object/{SCREENSHOT_BUCKET}/{object_path}"
    r = _request(
        "POST",
        url,
        headers={**_storage_headers(content_type="image/jpeg"), "x-upsert": "true"},
        content=jpeg_bytes,
    )
    if r.status_code in (200, 201):
        return f"{_base()}/storage/v1/object/public/{SCREENSHOT_BUCKET}/{object_path}"
    if r.status_code == 404:
        raise SupabaseError(
            f"upload_screenshot: bucket '{SCREENSHOT_BUCKET}' not found. "
            "Create it in the Supabase dashboard (Storage -> New bucket -> public)."
        )
    raise SupabaseError(f"upload_screenshot {app_id}: HTTP {r.status_code}: {r.text[:300]}")
