import { existsSync } from 'node:fs';
import { tmpdir } from 'node:os';
import path from 'node:path';
import { defineConfig, devices } from '@playwright/test';

const repository = path.resolve(import.meta.dirname, '..');
const localPython = path.join(repository, '.venv', 'bin', 'python');
const python = process.env.CLEARSPEND_PYTHON || (existsSync(localPython) ? localPython : 'python');
const database = path.join(tmpdir(), 'clearspend-browser-e2e.db');
const quoted = (value: string) => JSON.stringify(value);
const serverCommand = [
  `cd ${quoted(repository)}`,
  `PYTHONPATH=src:. ${quoted(python)} tests/synthetic/browser_seed.py ${quoted(database)}`,
  `PYTHONPATH=src:. ${quoted(python)} -m clearspend.server --port 8785 --database ${quoted(database)} --static-dir ${quoted(path.join(repository, 'dist'))}`,
].join(' && ');

export default defineConfig({
  testDir: './e2e',
  snapshotPathTemplate: '{testDir}/__screenshots__/{arg}{ext}',
  fullyParallel: false,
  workers: 1,
  retries: process.env.CI ? 1 : 0,
  reporter: process.env.CI ? [['html', { open: 'never' }], ['list']] : 'list',
  use: {
    baseURL: 'http://127.0.0.1:8785',
    trace: 'retain-on-failure',
    screenshot: 'only-on-failure',
    locale: 'en-US',
    timezoneId: 'Asia/Jerusalem',
  },
  webServer: {
    command: serverCommand,
    url: 'http://127.0.0.1:8785/api/health',
    reuseExistingServer: false,
    timeout: 30_000,
  },
  projects: [{ name: 'chromium', use: { ...devices['Desktop Chrome'] } }],
});
