import { getJson } from './client.ts';

export const EXPECTED_API_COMPATIBILITY = 'clearspend-vue-api-v1';

export type RuntimeHealth = {
  status: string;
  mode: string;
  database: boolean;
  api_compatibility?: string;
};

export function runtimeCompatibilityError(health: RuntimeHealth): string {
  if (health.status !== 'ok') return 'The local ClearSpend server is not ready.';
  if (!health.database) return 'The local ClearSpend database is unavailable.';
  if (health.api_compatibility !== EXPECTED_API_COMPATIBILITY) {
    return 'The dashboard and local server are from different builds. Restart the Python server from this branch, then try again.';
  }
  return '';
}

export function getRuntimeHealth(): Promise<RuntimeHealth> {
  return getJson<RuntimeHealth>('/api/health', 'Could not verify the local ClearSpend server');
}
