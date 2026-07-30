import { describe, expect, it } from "vitest";

import { ACCEPTED_FILE_TYPES } from "./upload-file-types";

// Mirror of the backend `ALLOWED_TYPES` set in
// services/api/app/service/upload.py. The dataset-ingest dropzone is scoped to
// the training-file formats (a subset), while the backend stays a general B2
// writer for the whole-bucket Files explorer. Every type the picker offers must
// still be one the server accepts — this fails loudly if the picker drifts
// outside the backend allow-list.
const BACKEND_ALLOWED_TYPES = new Set([
  "application/jsonl",
  "application/x-ndjson",
  "text/plain",
  "text/csv",
  "application/json",
  "image/jpeg",
  "image/png",
  "image/gif",
  "image/webp",
  "application/pdf",
  "application/zip",
  "video/mp4",
  "audio/mpeg",
  "audio/wav",
]);

describe("ACCEPTED_FILE_TYPES", () => {
  it("offers only types the backend accepts (a scoped subset)", () => {
    for (const type of Object.keys(ACCEPTED_FILE_TYPES)) {
      expect(BACKEND_ALLOWED_TYPES.has(type)).toBe(true);
    }
  });

  it("scopes the ingest picker to the training-file formats", () => {
    expect(new Set(Object.keys(ACCEPTED_FILE_TYPES))).toEqual(
      new Set(["application/jsonl", "application/x-ndjson", "application/json", "text/csv"])
    );
  });

  it("maps every type to at least one dot-prefixed extension", () => {
    for (const exts of Object.values(ACCEPTED_FILE_TYPES)) {
      expect(exts.length).toBeGreaterThan(0);
      for (const ext of exts) {
        expect(ext.startsWith(".")).toBe(true);
      }
    }
  });
});
