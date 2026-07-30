/**
 * Client-side allow-list for the dropzone, mirroring the backend's
 * `ALLOWED_TYPES` / `MIME_EXTENSION_MAP` in
 * `services/api/app/service/upload.py`. The server re-validates every upload —
 * this only gives instant feedback and filters the OS file picker. Keep the two
 * in sync when adding or removing a type.
 *
 * Shape matches react-dropzone's `accept`: MIME type → matching extensions.
 */
// Dataset ingest accepts training files only (JSONL / CSV / JSON). The backend
// remains a general B2 writer for the whole-bucket Files explorer, but the
// ingest picker is scoped to the formats a run can train on.
export const ACCEPTED_FILE_TYPES: Record<string, string[]> = {
  "application/jsonl": [".jsonl"],
  "application/x-ndjson": [".jsonl", ".ndjson"],
  "application/json": [".json", ".jsonl"],
  "text/csv": [".csv"],
};
