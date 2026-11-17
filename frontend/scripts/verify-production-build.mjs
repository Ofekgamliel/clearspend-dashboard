import { existsSync, readdirSync, readFileSync } from 'node:fs';
import { join, resolve } from 'node:path';

const dist = resolve('../dist');
if (existsSync(join(dist, 'gallery.html'))) throw new Error('Development gallery was emitted into production.');
for (const name of readdirSync(join(dist, 'assets'))) {
  const content = readFileSync(join(dist, 'assets', name), 'utf8');
  if (content.includes('ClearSpend UI gallery') || content.includes('Synthetic development states only')) {
    throw new Error(`Development gallery content leaked into ${name}.`);
  }
}
