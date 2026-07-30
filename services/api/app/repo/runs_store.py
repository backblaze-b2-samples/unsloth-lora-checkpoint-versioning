"""B2 persistence for runs and ingested datasets, scoped to the app's prefixes.

Uses the shared, custom-user-agent S3 client from `b2_client` (no separate
boto3 client is constructed here). Every run write and delete is confined to
`runs/<run_id>/`, so nothing this module does can touch objects belonging to
other apps in a shared bucket. Datasets live under `datasets/`.

The versioning story lives in the prefix structure — there is no dependency on
bucket-level S3 versioning being enabled:

    datasets/<dataset_id>                        # ingested JSONL/CSV training file
    runs/<run_id>/run.json                       # manifest (source of truth)
    runs/<run_id>/config.json                    # frozen training config
    runs/<run_id>/checkpoints/epoch-<n>/...      # per-epoch adapter snapshot
    runs/<run_id>/adapter/...                    # final LoRA adapter
    runs/<run_id>/metrics.json                   # loss curve + summary
"""

from __future__ import annotations

from collections import defaultdict

from botocore.exceptions import ClientError

from app.config import settings
from app.repo.b2_client import _public_url, get_presigned_url, get_s3_client
from app.repo.list_cache import invalidate as _invalidate_list_cache
from app.types.runs import RunManifest

RUNS_PREFIX = "runs/"
DATASETS_PREFIX = "datasets/"


def _bucket() -> str:
    return settings.b2_bucket_name


def run_dir(run_id: str) -> str:
    return f"{RUNS_PREFIX}{run_id}/"


def object_key(run_id: str, name: str) -> str:
    return f"{run_dir(run_id)}{name}"


def put_object(key: str, data: bytes, content_type: str) -> None:
    client = get_s3_client()
    try:
        client.put_object(Bucket=_bucket(), Key=key, Body=data, ContentType=content_type)
    except ClientError as e:
        raise RuntimeError(f"B2 put failed for '{key}': {e}") from e
    _invalidate_list_cache()


def get_bytes(key: str) -> bytes | None:
    client = get_s3_client()
    try:
        return client.get_object(Bucket=_bucket(), Key=key)["Body"].read()
    except ClientError as e:
        code = e.response.get("Error", {}).get("Code", "")
        if code in ("404", "NoSuchKey"):
            return None
        raise RuntimeError(f"B2 get failed for '{key}': {e}") from e


def _list_under(prefix: str) -> list[dict]:
    client = get_s3_client()
    contents: list[dict] = []
    kwargs: dict = {"Bucket": _bucket(), "Prefix": prefix, "MaxKeys": 1000}
    try:
        while True:
            response = client.list_objects_v2(**kwargs)
            contents.extend(response.get("Contents", []))
            if not response.get("IsTruncated"):
                break
            kwargs["ContinuationToken"] = response["NextContinuationToken"]
    except ClientError as e:
        raise RuntimeError(f"B2 list failed for '{prefix}': {e}") from e
    return contents


# --- Runs ---------------------------------------------------------------


def write_manifest(manifest: RunManifest) -> None:
    put_object(
        object_key(manifest.id, "run.json"),
        manifest.model_dump_json(indent=2).encode("utf-8"),
        "application/json",
    )


def read_manifest(run_id: str) -> RunManifest | None:
    data = get_bytes(object_key(run_id, "run.json"))
    if data is None:
        return None
    return RunManifest.model_validate_json(data)


def list_run_ids() -> list[str]:
    ids: set[str] = set()
    for obj in _list_under(RUNS_PREFIX):
        rest = obj["Key"][len(RUNS_PREFIX) :]
        if "/" not in rest:
            continue
        ids.add(rest.split("/", 1)[0])
    return sorted(ids)


def list_run_objects(run_id: str) -> list[dict]:
    """Objects under one run's prefix (key, filename, size, last_modified)."""
    prefix = run_dir(run_id)
    out: list[dict] = []
    for obj in _list_under(prefix):
        out.append(
            {
                "key": obj["Key"],
                "filename": obj["Key"][len(prefix) :],
                "size_bytes": int(obj.get("Size", 0)),
                "last_modified": obj["LastModified"],
            }
        )
    out.sort(key=lambda o: o["filename"])
    return out


def list_all_run_objects() -> dict[str, list[dict]]:
    """Every run's objects from a SINGLE `runs/` scan, grouped by run_id.

    The list/stats read models need each run's objects (artifact counts + sizes).
    Fetching them with `list_run_objects` per run issued one LIST per run on top
    of the full `runs/` scan already done to enumerate ids — an O(N) redundant
    re-enumeration whose latency grew with the run count. This scans once and
    buckets by run_id. Each row matches `list_run_objects`' shape (`filename`
    relative to the run prefix), so the read models are unchanged.
    """
    grouped: dict[str, list[dict]] = defaultdict(list)
    for obj in _list_under(RUNS_PREFIX):
        rest = obj["Key"][len(RUNS_PREFIX) :]
        if "/" not in rest:
            continue
        run_id, filename = rest.split("/", 1)
        grouped[run_id].append(
            {
                "key": obj["Key"],
                "filename": filename,
                "size_bytes": int(obj.get("Size", 0)),
                "last_modified": obj["LastModified"],
            }
        )
    for objs in grouped.values():
        objs.sort(key=lambda o: o["filename"])
    return dict(grouped)


def run_size_bytes(run_id: str) -> int:
    return sum(int(o.get("Size", 0)) for o in _list_under(run_dir(run_id)))


def delete_run(run_id: str) -> int:
    """Delete every object under one run prefix. Scoped — never bucket-wide."""
    prefix = run_dir(run_id)
    keys = [obj["Key"] for obj in _list_under(prefix)]
    if not keys:
        return 0
    client = get_s3_client()
    deleted = 0
    try:
        for i in range(0, len(keys), 1000):
            batch = [{"Key": k} for k in keys[i : i + 1000]]
            client.delete_objects(Bucket=_bucket(), Delete={"Objects": batch})
            deleted += len(batch)
    except ClientError as e:
        raise RuntimeError(f"B2 delete failed for '{prefix}': {e}") from e
    _invalidate_list_cache()
    return deleted


def presign(key: str, filename: str | None = None) -> str:
    return get_presigned_url(key, filename=filename, disposition="attachment")


def public_url(key: str) -> str | None:
    return _public_url(key)


# --- Datasets -----------------------------------------------------------


def list_datasets() -> list[dict]:
    """Ingested training datasets (objects directly under `datasets/`)."""
    out: list[dict] = []
    for obj in _list_under(DATASETS_PREFIX):
        rel = obj["Key"][len(DATASETS_PREFIX) :]
        if not rel or rel.endswith("/"):
            continue
        out.append(
            {
                "id": rel,
                "filename": rel,
                "size_bytes": int(obj.get("Size", 0)),
                "last_modified": obj["LastModified"],
            }
        )
    out.sort(key=lambda o: o["filename"])
    return out


def dataset_key(dataset_id: str) -> str:
    return f"{DATASETS_PREFIX}{dataset_id}"


def get_dataset_bytes(dataset_id: str) -> bytes | None:
    return get_bytes(dataset_key(dataset_id))


def datasets_prefix_empty() -> bool:
    return len(list_datasets()) == 0
