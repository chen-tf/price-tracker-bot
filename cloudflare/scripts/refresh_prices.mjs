import { pathToFileURL } from 'node:url';
import { getPrices } from '../src/momo-api.js';
export { parsePrice, parseStock } from '../src/momo-api.js';
const pause = ms => new Promise(resolve => setTimeout(resolve, ms));
async function requestJson(url, options = {}) {
  // Avoid logging URLs or headers: internal requests carry a shared secret.
  for (let attempt = 0; ; attempt++) {
    try {
      const response = await fetch(url, { ...options, signal: AbortSignal.timeout(12000) });
      if (!response.ok) {
        await response.body?.cancel();
        const error = new Error(`HTTP ${response.status}`);
        error.retryable = response.status === 429 || response.status >= 500;
        throw error;
      }
      return await response.json();
    } catch (error) {
      if (attempt >= 2 || error.retryable === false) throw error;
      await pause(1000 * 2 ** attempt);
    }
  }
}

async function main() {
  if (process.argv.includes('--probe')) {
    const goods = await getPrices([{ id: '4811545', product_id: '4811545' }]);
    console.log(JSON.stringify({ probe: goods }));
    if (goods[0].error) process.exitCode = 1;
    return;
  }
  const worker = process.env.WORKER_URL;
  const secret = process.env.SYNC_SECRET;
  const runId = process.env.GITHUB_RUN_ID;
  if (!worker || !secret || !/^\d+$/.test(runId || '')) throw new Error('Missing sync configuration');
  const base = new URL(worker);
  if (base.protocol !== 'https:') throw new Error('WORKER_URL must use HTTPS');
  const headers = { Authorization: `Bearer ${secret}`, 'Content-Type': 'application/json' };
  let cursor = '';
  const goods = [];
  do {
    const url = new URL('/internal/tracked-goods', base);
    url.searchParams.set('cursor', cursor);
    if (process.argv.includes('--retry-errors')) url.searchParams.set('errors', '1');
    else if (!process.argv.includes('--all')) url.searchParams.set('due', '1');
    const page = await requestJson(url, { headers });
    goods.push(...page.goods);
    if (page.next_cursor && page.next_cursor <= cursor) throw new Error('Invalid pagination');
    cursor = page.next_cursor;
  } while (cursor);
  let success = 0, failed = 0, unavailable = 0, consecutiveFailed = 0, rowsRead = 0, rowsWritten = 0, sqlStatements = 0;
  const started = Date.now();
  for (let i = 0; i < goods.length; i += 100) {
    const results = await getPrices(goods.slice(i, i + 100), fetch, { maxResolutions: Infinity });
    const errors = results.filter(g => g.error);
    for (let j = 0; j < results.length; j += 20) {
      const usage = await requestJson(new URL('/internal/prices', base), { method: 'POST', headers,
        body: JSON.stringify({ run_id: runId, goods: results.slice(j, j + 20) }) });
      rowsRead += usage.rows_read || 0; rowsWritten += usage.rows_written || 0; sqlStatements += usage.sql_statements || 0;
    }
    const missing = results.filter(g => g.unavailable).length;
    unavailable += missing;
    success += results.length - errors.length - missing;
    failed += errors.length;
    console.log(JSON.stringify({ processed: i + results.length, total: goods.length, success, unavailable, failed,
      errors: errors.map(g => ({ id: g.id, error: g.error })) }));
    consecutiveFailed = errors.length === results.length ? consecutiveFailed + 1 : 0;
    // Stop quickly when the entire API is unavailable; retain all previous values.
    if (consecutiveFailed >= 3) throw new Error('Three entire batches failed; stopping until next run');
  }
  console.log(JSON.stringify({ summary: true, total: goods.length, success, unavailable, failed,
    elapsed_ms: Date.now() - started, sql_statements: sqlStatements, rows_read: rowsRead, rows_written: rowsWritten }));
  if (failed) process.exitCode = 1;
}

if (process.argv[1] && import.meta.url === pathToFileURL(process.argv[1]).href) {
  main().catch(error => { console.error(error.message); process.exitCode = 1; });
}
