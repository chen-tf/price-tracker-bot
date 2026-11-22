import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync, readdirSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { Miniflare, convertV4MiniflareOptions } from 'miniflare';

test('real workerd and D1 commit price notifications and enforce route authentication', async t => {
  const root = new URL('../src/', import.meta.url);
  const runtime = new Miniflare(convertV4MiniflareOptions({
    name: 'worker-test', compatibilityDate: '2026-11-01',
    modules: ['worker.js', 'sync.js', 'momo.js', 'links.js', 'momo-api.js'].map(name => ({
      type: 'ESModule', path: fileURLToPath(new URL(name, root)), contents: readFileSync(new URL(name, root), 'utf8'),
    })),
    d1Databases: ['DB'], bindings: { SYNC_SECRET: 'test-secret', WEBHOOK_SECRET: 'webhook-secret' },
  }));
  t.after(() => runtime.dispose());
  const db = await runtime.getD1Database('DB');
  const migrations = new URL('../migrations/', import.meta.url);
  for (const name of readdirSync(migrations).filter(f => f.endsWith('.sql')).sort()) {
    for (const sql of readFileSync(new URL(name, migrations), 'utf8').replace(/^--.*$/gm, '').split(/;(?!\s*END\b)/).filter(s => s.trim())) await db.prepare(sql).run();
  }
  await db.batch([
    db.prepare(`INSERT INTO "user"(id,chat_id) VALUES ('10','10')`),
    db.prepare(`INSERT INTO good_info(id,name,price,stock_state) VALUES ('123','商品',1000,0)`),
    db.prepare(`INSERT INTO user_sub_good(id,user_id,good_id,price) VALUES ('s','10','123',1000)`),
  ]);
  assert.equal((await runtime.dispatchFetch('https://test/internal/tracked-goods')).status, 401);
  const response = await runtime.dispatchFetch('https://test/internal/prices', { method: 'POST',
    headers: { Authorization: 'Bearer test-secret' }, body: JSON.stringify({ run_id: '1', goods: [
      { id: '123', name: '商品', price: 900, stock_state: 1, observed_at: Math.floor(Date.now() / 1000) },
    ] }) });
  assert.equal(response.status, 200);
  assert.equal((await db.prepare('SELECT price FROM good_info').first()).price, 900);
  assert.equal((await db.prepare('SELECT COUNT(*) AS n FROM outbox').first()).n, 1);
  assert.equal((await runtime.dispatchFetch('https://test/health')).status, 200);
  await assert.rejects(db.batch([
    db.prepare("UPDATE good_info SET price=1 WHERE id='123'"),
    db.prepare("INSERT INTO good_info(id,name,price,stock_state) VALUES ('bad','invalid',0,1)"),
  ]));
  assert.equal((await db.prepare('SELECT price FROM good_info').first()).price, 900);
});
