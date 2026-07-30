export type FileStatus = "uploading" | "complete" | "error";

export interface FileMetadata {
  key: string;
  filename: string;
  folder: string;
  size_bytes: number;
  size_human: string;
  content_type: string;
  uploaded_at: string;
  url: string | null;
}

export interface FileMetadataDetail {
  filename: string;
  size_bytes: number;
  size_human: string;
  mime_type: string;
  extension: string;
  md5: string;
  sha256: string;
  uploaded_at: string;
  /** Set when a format-specific extractor was skipped or failed (e.g. an image
   *  above the decompression-bomb decode limit). Core fields stay exact. */
  metadata_warning: string | null;
  // Image-specific
  image_width: number | null;
  image_height: number | null;
  exif: Record<string, string> | null;
  // PDF-specific
  pdf_pages: number | null;
  pdf_author: string | null;
  pdf_title: string | null;
  // Audio/Video
  duration_seconds: number | null;
  codec: string | null;
  bitrate: number | null;
}

export interface FileUploadResponse {
  key: string;
  filename: string;
  size_bytes: number;
  size_human: string;
  content_type: string;
  uploaded_at: string;
  url: string | null;
  metadata: FileMetadataDetail | null;
}

export interface DailyUploadCount {
  date: string;
  uploads: number;
}

export interface UploadStats {
  total_files: number;
  total_size_bytes: number;
  total_size_human: string;
  uploads_today: number;
  total_downloads: number;
}

// --- Runs (the primary entity) ---
export type RunStatus = "queued" | "running" | "completed" | "failed";
export type TrainingMethod = "LoRA" | "QLoRA";

export interface BaseModelOption {
  value: string;
  label: string;
  gated: boolean;
  requires_gpu: boolean;
}

export interface RunConfig {
  base_model: string;
  dataset_id: string;
  method: TrainingMethod;
  epochs: number;
  learning_rate: number;
  lora_rank: number;
}

export interface CreateRunRequest {
  name: string;
  notes: string;
  tags: string[];
  config: RunConfig;
}

export interface UpdateRunRequest {
  name?: string | null;
  notes?: string | null;
  tags?: string[] | null;
}

export interface EpochMetric {
  epoch: number;
  loss: number;
  checkpoint_key: string | null;
}

export interface RunProgress {
  current_epoch: number;
  total_epochs: number;
  latest_loss: number | null;
  message: string;
}

export interface Artifact {
  key: string;
  filename: string;
  kind: string;
  size_bytes: number;
  size_human: string;
  last_modified: string;
  download_url: string | null;
}

export interface RunSummary {
  id: string;
  name: string;
  status: RunStatus;
  base_model: string;
  dataset_id: string;
  method: TrainingMethod;
  epochs: number;
  final_loss: number | null;
  artifact_count: number;
  size_bytes: number;
  size_human: string;
  created_at: string;
  updated_at: string;
}

export interface RunDetail {
  id: string;
  name: string;
  notes: string;
  tags: string[];
  config: RunConfig;
  status: RunStatus;
  device: string;
  base_model_resolved: string;
  epoch_metrics: EpochMetric[];
  final_loss: number | null;
  error: string | null;
  progress: RunProgress | null;
  artifacts: Artifact[];
  artifact_count: number;
  size_bytes: number;
  size_human: string;
  created_at: string;
  updated_at: string;
  started_at: string | null;
  completed_at: string | null;
}

export interface DatasetOption {
  id: string;
  filename: string;
  rows: number | null;
  size_bytes: number;
  size_human: string;
}

export interface RunOptions {
  base_models: BaseModelOption[];
  methods: string[];
  learning_rates: number[];
  lora_ranks: number[];
  epochs_min: number;
  epochs_max: number;
  datasets: DatasetOption[];
  default_dataset_id: string | null;
  gpu_available: boolean;
}

export interface CumulativePoint {
  date: string;
  artifacts: number;
  size_bytes: number;
}

export interface RunStats {
  total_runs: number;
  queued: number;
  running: number;
  completed: number;
  failed: number;
  total_artifacts: number;
  total_size_bytes: number;
  total_size_human: string;
  cumulative: CumulativePoint[];
}

export interface DeleteResponse {
  deleted: boolean;
  id: string;
}
