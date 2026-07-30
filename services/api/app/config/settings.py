from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # --- Backblaze B2 (S3-compatible API, standardized env var names) ---
    b2_application_key_id: str = ""
    b2_application_key: str = ""
    b2_bucket_name: str = ""
    # Region drives the S3 endpoint (see `s3_endpoint`). No default region is
    # hardcoded here on purpose — it is a required credential-adjacent setting,
    # supplied via .env (see .env.example) and validated at startup.
    b2_region: str = ""
    # Optional public base URL for building object URLs on a public bucket. The
    # app runs without it (download links use presigned URLs instead).
    b2_public_url_base: str = ""

    # --- Fine-tuning (local, no external provider) ---
    # Optional Hugging Face token. Public open models (the CPU demo model,
    # Qwen) need none; gated models (Llama 3.x, Gemma) require a token to accept
    # their license AND a CUDA GPU. Kept optional so the default demo is keyless.
    hf_token: str = ""
    # Device override for the trainer. Empty ("") means runtime auto-detect:
    # first available of CUDA -> CPU (Apple MPS is unsupported by the ML stack
    # used here, so Apple Silicon falls back to the CPU path). Set to "cpu" to
    # force the portable path even when a GPU is present.
    training_device: str = ""
    # Bound the CPU-demo fine-tune so a keyless, GPU-less run stays fast and
    # cheap: cap the training rows read from the dataset and the optimizer steps
    # taken per epoch. The GPU/Unsloth path uses the full dataset.
    max_train_rows: int = 64
    max_steps_per_epoch: int = 8
    max_epochs: int = 5
    # Seed one tiny sample dataset under `datasets/` at startup if the prefix is
    # empty, so a fresh clone has a selectable default dataset and the whole
    # ingest -> train -> version loop is exercisable without a manual upload.
    seed_sample_dataset: bool = True

    api_port: int = 8000
    # Interactive API docs (/docs, /redoc, /openapi.json). On by default for
    # local dev and exploration; set false to hide the full API surface in
    # production.
    enable_docs: bool = True
    # Explicit allowlist by default — covers Next on :3000 and the
    # fallback :3001 it picks if 3000 is busy. Production deploys should
    # override with the exact frontend origin.
    api_cors_origins: str = "http://localhost:3000,http://localhost:3001"
    # Optional dev-only escape hatch: a regex that matches additional
    # allowed origins. Empty by default — set this to e.g.
    # `^http://localhost:\d+$` to accept any localhost port without
    # listing each one. NEVER ship this to production.
    api_cors_origin_regex: str = ""

    # Upload limits (dataset ingest — JSONL/CSV training files).
    max_file_size: int = 100 * 1024 * 1024  # 100MB

    # Optional confinement for key-addressed reads/deletes. Empty by default so
    # the by-key routes accept any key shape (they deliberately support nested
    # folders and reserved-word segments). Point a fork at a bucket shared with
    # other data? Set to e.g. "runs/" to restrict all key ops to app artifacts.
    allowed_key_prefix: str = ""

    # Full-bucket listing cache (repo/list_cache.py). Both /files and
    # /files/stats need every object, and paginating a large bucket takes
    # ~8-20s, so one scan is shared. Entries older than the TTL are still
    # served *immediately* while a background thread refreshes them
    # (stale-while-revalidate), so only the very first scan can make a user
    # wait. Uploads and deletes invalidate the cache outright, so the app's own
    # writes are never served stale — only bucket changes made elsewhere can lag
    # by up to this TTL.
    list_cache_ttl_seconds: float = 300.0
    # Scan the bucket once at startup so the first page view doesn't pay for the
    # cold scan. Set false for offline dev or when startup must not touch B2.
    warm_list_cache_on_startup: bool = True

    # Rate limiting (per client IP, per 60s window). In-process per replica —
    # documented in docs/RELIABILITY.md; horizontal scaling needs a shared
    # store (e.g. Redis). Writes/downloads get the tighter cap.
    rate_limit_per_minute: int = 120
    # Covers uploads, deletes, downloads, previews and run mutations — kept
    # generous enough that a normal browsing/training session doesn't trip it.
    rate_limit_write_per_minute: int = 60

    # Small durable counters (downloads, etc). Relative paths resolve against
    # the repo root (see repo/counter.py). Point at a persistent volume in
    # production if you care about surviving restarts.
    #
    # It must stay OUTSIDE services/api/: that is the directory `uvicorn
    # --reload` watches in dev, so a counter file there means every download
    # writes into the reloader's watch tree. Today uvicorn only restarts for
    # `*.py`, so the writes surface as misleading "N changes detected" log noise
    # on every download — but a single added `--reload-include` would turn a
    # normal user action into an API restart that drops in-flight requests.
    download_count_file: str = ".data/download_count.json"

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}

    @property
    def cors_origins(self) -> list[str]:
        # Drop empties so a trailing comma or API_CORS_ORIGINS="" doesn't yield
        # a stray "" origin.
        return [o.strip() for o in self.api_cors_origins.split(",") if o.strip()]

    @property
    def s3_endpoint(self) -> str:
        """S3 endpoint for the B2 client, derived from `b2_region`
        (`https://s3.<region>.backblazeb2.com`). No region string is hardcoded
        in source — the region comes from configuration.
        """
        return f"https://s3.{self.b2_region}.backblazeb2.com"


settings = Settings()
