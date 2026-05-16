import { apiPost, mediaUrl, ssePost } from "./client";

export interface ListResponse {
  ok: boolean;
  encoding: string | null;
  names: string[];
}

export interface InfoResponse {
  format_name: string;
  file_count: number;
  compressed_size: number;
  uncompressed_size: number;
  is_encrypted: boolean;
  comment: string;
}

export interface DetectEncodingResponse {
  encoding: string | null;
  confidence: number;
}

export interface TestResponse {
  ok: boolean;
  failed: string[];
}

export interface PreviewResponse {
  temp_id: string;
  file_path: string;
}

export function listArchive(params: {
  archive_path: string;
  password?: string;
  filename_encoding?: string | null;
  password_encoding?: string | null;
}): Promise<ListResponse> {
  return apiPost("/archives/list", params);
}

export function getArchiveInfo(params: {
  archive_path: string;
  password?: string;
}): Promise<InfoResponse> {
  return apiPost("/archives/info", params);
}

export function detectEncoding(params: { archive_path: string }): Promise<DetectEncodingResponse> {
  return apiPost("/archives/detect-encoding", params);
}

export function testArchive(params: {
  archive_path: string;
  password?: string;
  filename_encoding?: string | null;
  password_encoding?: string | null;
}): Promise<TestResponse> {
  return apiPost("/archives/test", params);
}

export function extractArchive(
  params: {
    archive_path: string;
    password?: string;
    output_dir?: string | null;
    filename_encoding?: string | null;
    password_encoding?: string | null;
    names?: string[] | null;
    smart?: boolean;
  },
  handlers: Record<string, (data: unknown) => void>
): Promise<void> {
  return ssePost("/archives/extract", params, handlers);
}

export function batchExtract(
  params: {
    archives: string[];
    output_dir?: string | null;
    password?: string;
    filename_encoding?: string | null;
    password_encoding?: string | null;
  },
  handlers: Record<string, (data: unknown) => void>
): Promise<void> {
  return ssePost("/archives/batch", params, handlers);
}

export function createArchive(params: {
  output_path: string;
  files: string[];
  format?: string;
  password?: string | null;
  compression_level?: number;
  filename_encoding?: string | null;
}): Promise<{ ok: boolean }> {
  return apiPost("/archives/create", params);
}

export function convertArchive(params: {
  input_path: string;
  output_path: string;
  output_format: string;
  password?: string | null;
  output_password?: string | null;
  filename_encoding?: string | null;
  password_encoding?: string | null;
}): Promise<{ ok: boolean }> {
  return apiPost("/archives/convert", params);
}

export function updateArchive(params: {
  archive_path: string;
  files_to_add?: string[];
  paths_to_remove?: string[];
}): Promise<{ ok: boolean }> {
  return apiPost("/archives/update", params);
}

export function extractPreview(params: {
  archive_path: string;
  entry_name: string;
  password?: string;
  filename_encoding?: string | null;
  password_encoding?: string | null;
}): Promise<PreviewResponse> {
  return apiPost("/preview/", params);
}

export function cleanupPreview(temp_id: string): Promise<{ ok: boolean }> {
  return apiPost(`/preview/${temp_id}`, {});
}

export function getPreviewServeUrl(filePath: string): Promise<string> {
  return mediaUrl("/preview/serve", filePath);
}
