import { getJson, postForm, postJson } from './client.ts';
import type { CancelImportResponse, CommitImportRequest, CommitImportResponse, MappingReferenceResponse, StagedImportBatch } from './contracts.ts';

export function analyzeImport(files: File[]): Promise<StagedImportBatch> {
  const form = new FormData();
  files.forEach((file) => form.append('files', file));
  return postForm<StagedImportBatch>('/api/import/analyze', form, 'Could not analyze files');
}

export function commitImport(request: CommitImportRequest): Promise<CommitImportResponse> {
  return postJson<CommitImportResponse, CommitImportRequest>('/api/import/commit', request, 'Import failed');
}
export function cancelImport(batchId: string): Promise<CancelImportResponse> {
  return postJson<CancelImportResponse, { batch_id: string }>('/api/import/cancel', { batch_id: batchId }, 'Could not discard staged files');
}
export function getImportAudit(): Promise<MappingReferenceResponse> { return getJson<MappingReferenceResponse>('/api/mapping','Could not load import history'); }
