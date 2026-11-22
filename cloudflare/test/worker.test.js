import { test } from 'node:test';
import assert from 'node:assert/strict';
import { DatabaseSync } from 'node:sqlite';
import { readFileSync, readdirSync } from 'node:fs';
import worker, { drainOutbox, processOneUpdate } from '../src/worker.js';
import { acceptPrices, trackedGoods, pollPrices, readPrices } from '../src/sync.js';
import { parsePrice, parseStock } from '../scripts/refresh_prices.mjs';
import { getPrices, resolveProductCode } from '../src/momo-api.js';
import { fetchProduct, parseLink } from '../src/momo.js';

function setup(t) {
  const db = new DatabaseSync(':memory:');
  const migrations = new URL('../migrations/', import.meta.url);
  for (const file of readdirSync(migrations).filter(f => f.endsWith('.sql')).sort()) {
    db.exec(readFileSync(new URL(file, migrations), 'utf8'));
  }
  t.after(() => db.close());
  const prepare = (sql, values = []) => ({
    bind(...args) { return prepare(sql, args); },
    async first() { return db.prepare(sql).get(...values) || null; },
    async all() { return { results: db.prepare(sql).all(...values) }; },
    async run() { return db.prepare(sql).run(...values); },
  });
  const env = {
    DB: {
      prepare,
      async batch(writes) {
        db.exec('BEGIN');
        try {
          const results = [];
          for (const write of writes) results.push(await write.run());
          db.exec('COMMIT');
          return results;
        } catch (error) { db.exec('ROLLBACK'); throw error; }
      },
    },
    BOT_TOKEN: 'fake', WEBHOOK_SECRET: 'local-secret', SYNC_SECRET: 'sync-secret',
  };
  return { db, env };
}

function seed(db) {
  db.exec(`INSERT INTO "user"(id, chat_id) VALUES ('10','10'), ('20','20');
    INSERT INTO good_info(id, name, price, stock_state) VALUES ('123', '商品', 1000, 0);
    INSERT INTO user_sub_good(id, user_id, good_id, price) VALUES ('sub-10','10','123',1000),('sub-20','20','123',800);`);
}

function incoming(db, id, text, userId = 10, extra = {}) {
  const update = { update_id: id, message: { from: { id: userId }, chat: { id: userId, type: 'private' }, text }, ...extra };
  db.prepare('INSERT OR IGNORE INTO telegram_update(id,payload,created_at) VALUES (?,?,?)').run(id, JSON.stringify(update), Math.floor(Date.now() / 1000));
  return update;
}

test('only exact momo hosts are accepted, including on each redirect', async () => {
  for (const url of ['http://momo.dm/a', 'https://momo.dm.evil.test/a', 'https://evil.test/?x=https://momo.dm/a', 'https://x:m@momo.dm/a', 'https://momo.dm:8443/a']) {
    assert.throws(() => parseLink(url));
  }
  let calls = 0;
  await assert.rejects(fetchProduct('https://momo.dm/a', async () => {
    calls++;
    return new Response('', { status: 302, headers: { location: 'https://127.0.0.1/private' } });
  }), /只接受/);
  assert.equal(calls, 1);
});

test('duplicate Telegram updates produce one durable response', async t => {
  const { db, env } = setup(t);
  incoming(db, 1, '/start'); incoming(db, 1, '/start');
  await processOneUpdate(env); await processOneUpdate(env);
  assert.equal(db.prepare('SELECT COUNT(*) AS n FROM outbox').get().n, 1);
  assert.equal(db.prepare('SELECT status FROM telegram_update').get().status, 'done');
});

test('direct product links work without /add and keep other subscribers baseline unchanged', async t => {
  const { db, env } = setup(t); seed(db);
  incoming(db, 1, 'https://m.momoshop.com.tw/goods.momo?i_code=123');
  await processOneUpdate(env, async () => ({ id: '123', name: '商品', price: 950, stock_state: 1 }));
  assert.equal(db.prepare("SELECT price FROM user_sub_good WHERE user_id = '10'").get().price, 950);
  assert.equal(db.prepare("SELECT price FROM user_sub_good WHERE user_id = '20'").get().price, 800);
  // Scheduled price checks still see the previous global price and can alert other users.
  assert.equal(db.prepare('SELECT price FROM good_info').get().price, 1000);
});

test('the 20 item limit is enforced in SQL; existing subscriptions can be refreshed', async t => {
  const { db, env } = setup(t); seed(db);
  for (let i = 1; i <= 19; i++) {
    db.prepare('INSERT INTO good_info(id,name,price,stock_state) VALUES (?,?,100,1)').run(String(i), '商品');
    db.prepare('INSERT INTO user_sub_good(id,user_id,good_id,price) VALUES (?,?,?,100)').run(`s${i}`, '10', String(i));
  }
  incoming(db, 1, '/add https://m.momoshop.com.tw/goods.momo?i_code=999');
  await processOneUpdate(env, async () => ({ id: '999', name: '新商品', price: 50, stock_state: 1 }));
  assert.equal(db.prepare("SELECT COUNT(*) AS n FROM user_sub_good WHERE user_id='10' AND state=1").get().n, 20);
  assert.match(db.prepare('SELECT payload FROM outbox').get().payload, /最多/);
  incoming(db, 2, '/add https://m.momoshop.com.tw/goods.momo?i_code=123');
  await processOneUpdate(env, async () => ({ id: '123', name: '商品', price: 700, stock_state: 1 }));
  assert.equal(db.prepare("SELECT price FROM user_sub_good WHERE user_id='10' AND good_id='123'").get().price, 700);
});

test('a deletion callback changes only the requesting user subscription', async t => {
  const { db, env } = setup(t); seed(db);
  incoming(db, 1, '', 10, { message: undefined, callback_query: { id: 'c', from: { id: 10 }, data: 'clear:123', message: { chat: { id: 10, type: 'private' } } } });
  await processOneUpdate(env);
  assert.equal(db.prepare("SELECT state FROM user_sub_good WHERE user_id='10'").get().state, 0);
  assert.equal(db.prepare("SELECT state FROM user_sub_good WHERE user_id='20'").get().state, 1);
});

test('group messages cannot expose a private tracking list', async t => {
  const { db, env } = setup(t); seed(db);
  incoming(db, 1, '/my', 10, { message: { from: { id: 10 }, chat: { id: -100, type: 'group' }, text: '/my' } });
  await processOneUpdate(env);
  assert.equal(db.prepare('SELECT COUNT(*) AS n FROM outbox').get().n, 0);
});

test('Telegram 429 retries the same notification; successful delivery is recorded', async t => {
  const { db, env } = setup(t);
  incoming(db, 1, '/start'); await processOneUpdate(env);
  await drainOutbox(env, async () => Response.json({ ok: false, error_code: 429, parameters: { retry_after: 120 } }), 1);
  let item = db.prepare('SELECT * FROM outbox').get();
  assert.equal(item.sent_at, null);
  assert.ok(item.next_attempt >= Math.floor(Date.now() / 1000) + 119);
  db.exec('UPDATE outbox SET next_attempt = 0');
  await drainOutbox(env, async () => Response.json({ ok: true, result: {} }), 1);
  item = db.prepare('SELECT * FROM outbox').get();
  assert.ok(item.sent_at > 0);
  assert.equal(item.attempts, 2);
});

test('Telegram 403 disables the blocked user and their subscriptions', async t => {
  const { db, env } = setup(t); seed(db);
  incoming(db, 1, '/start'); await processOneUpdate(env);
  await drainOutbox(env, async () => Response.json({ ok: false, error_code: 403 }), 1);
  assert.equal(db.prepare('SELECT state FROM "user" WHERE id=?').get('10').state, 0);
  assert.equal(db.prepare('SELECT state FROM user_sub_good WHERE user_id=?').get('10').state, 0);
  assert.equal(db.prepare('SELECT state FROM "user" WHERE id=?').get('20').state, 1);
});

test('webhook validates its secret and malformed bodies before durable storage', async t => {
  const { db, env } = setup(t);
  const url = 'https://worker.example/webhook';
  assert.equal((await worker.fetch(new Request(url, { method: 'POST', body: '{}' }), env, {})).status, 401);
  for (const body of ['{', '{}', 'null', '{"update_id":"1"}']) {
    assert.equal((await worker.fetch(new Request(url, { method: 'POST', body, headers: { 'X-Telegram-Bot-Api-Secret-Token': 'local-secret' } }), env, {})).status, 400);
  }
  assert.equal(db.prepare('SELECT COUNT(*) AS n FROM telegram_update').get().n, 0);
});

test('webhook persists before ACK; health tests D1 and reports backlogs', async t => {
  const { db, env } = setup(t);
  let background;
  const response = await worker.fetch(new Request('https://worker.example/webhook', {
    method: 'POST', body: JSON.stringify({ update_id: 1 }),
    headers: { 'X-Telegram-Bot-Api-Secret-Token': 'local-secret' },
  }), env, { waitUntil(promise) { background = promise; } });
  assert.equal(response.status, 200);
  assert.equal(db.prepare('SELECT COUNT(*) AS n FROM telegram_update').get().n, 1);
  await background;
  const health = await worker.fetch(new Request('https://worker.example/health'), env, {});
  assert.equal((await health.json()).status, 'ok');
  assert.equal((await worker.fetch(new Request('https://worker.example/health'), { DB: { prepare() { throw new Error('offline'); } } }, {})).status, 503);
});

const priceRequest = (goods, run = '123') => new Request('https://local.test/internal/prices', {
  method: 'POST', headers: { Authorization: 'Bearer sync-secret' }, body: JSON.stringify({ run_id: run, goods }),
});
const fresh = (overrides = {}) => ({ id: '123', name: '新商品', price: 900, stock_state: 1,
  observed_at: Math.floor(Date.now() / 1000), ...overrides });

test('sync commits price and subscriber-specific alerts atomically and rejects stale or duplicate deliveries', async t => {
  const { db, env } = setup(t); seed(db);
  await acceptPrices(priceRequest([fresh()]), env);
  assert.equal(db.prepare('SELECT price FROM good_info').get().price, 900);
  const alerts = db.prepare('SELECT * FROM outbox ORDER BY user_id').all();
  assert.equal(alerts.length, 2);
  assert.match(JSON.parse(alerts[0].payload).text, /低於加入追蹤時的 1000/);
  assert.doesNotMatch(JSON.parse(alerts[1].payload).text, /低於/);
  assert.match(JSON.parse(alerts[1].payload).text, /已經可購買/);
  await acceptPrices(priceRequest([fresh()]), env);
  await acceptPrices(priceRequest([fresh({ price: 1, observed_at: fresh().observed_at - 5 })], '124'), env);
  assert.equal(db.prepare('SELECT COUNT(*) AS n FROM outbox').get().n, 2);
  assert.equal(db.prepare('SELECT price FROM good_info').get().price, 900);
  assert.equal(db.prepare("SELECT price FROM user_sub_good WHERE user_id='10'").get().price, 1000);
});

test('failed sync and invalid values preserve old prices; notification failure rolls back all changes', async t => {
  const { db, env } = setup(t); seed(db);
  await acceptPrices(priceRequest([{ id: '123', error: 'HTTP 403' }]), env);
  assert.equal(db.prepare('SELECT price FROM good_info').get().price, 1000);
  assert.equal(db.prepare('SELECT last_error FROM good_info').get().last_error, 'HTTP 403');
  assert.equal((await acceptPrices(priceRequest([fresh({ price: 0 })]), env)).status, 400);
  db.exec(`CREATE TRIGGER reject_outbox BEFORE INSERT ON outbox BEGIN SELECT RAISE(ABORT, 'failure'); END;`);
  await assert.rejects(acceptPrices(priceRequest([fresh()]), env), /failure/);
  assert.equal(db.prepare('SELECT price FROM good_info').get().price, 1000);
});

test('tracked goods paginate and exclude blocked or inactive subscriptions from sync and alerts', async t => {
  const { db, env } = setup(t); seed(db);
  db.exec(`UPDATE "user" SET state=0 WHERE id='10'; UPDATE user_sub_good SET state=0 WHERE user_id='20';`);
  assert.deepEqual((await (await trackedGoods(new Request('https://local.test/'), env)).json()).goods, []);
  await acceptPrices(priceRequest([fresh()]), env);
  assert.equal(db.prepare('SELECT COUNT(*) AS n FROM outbox').get().n, 0);
  db.exec(`UPDATE "user" SET state=1 WHERE id='10';`);
  for (let i = 1000; i < 1200; i++) {
    db.prepare('INSERT INTO good_info(id,name,price,stock_state) VALUES (?, ?, 1, 1)').run(String(i), '商品');
    db.prepare('INSERT INTO user_sub_good(id,user_id,good_id,price) VALUES (?, ?, ?, 1)').run(String(i), '10', String(i));
  }
  const page = await (await trackedGoods(new Request('https://local.test/'), env)).json();
  assert.equal(page.goods.length, 200);
  const next = await (await trackedGoods(new Request(`https://local.test/?cursor=${page.next_cursor}`), env)).json();
  assert.equal(next.goods.length, 1);
  assert.equal(next.next_cursor, null);
});

test('internal routes reject unauthorized and malformed uploads', async t => {
  const { env } = setup(t);
  const noAuth = await worker.fetch(new Request('https://local.test/internal/tracked-goods'), env, {});
  assert.equal(noAuth.status, 401);
  for (const body of ['null', '{}', '{', JSON.stringify({ run_id: '1', goods: Array(21).fill(fresh()) })]) {
    const r = await worker.fetch(new Request('https://local.test/internal/prices', { method: 'POST',
      headers: { Authorization: 'Bearer sync-secret' }, body }), env, {});
    assert.equal(r.status, 400);
  }
});

test('command replies are delivered before queued price alerts', async t => {
  const { db, env } = setup(t); seed(db);
  await acceptPrices(priceRequest([fresh()]), env);
  incoming(db, 1, '/start'); await processOneUpdate(env);
  const sent = [];
  await drainOutbox(env, async (_url, options) => {
    sent.push(JSON.parse(options.body).text);
    return Response.json({ ok: true, result: {} });
  }, 1);
  assert.match(sent[0], /\/my 顯示追蹤清單/);
});

test('runner parsers reject absent or ambiguous product data', () => {
  assert.equal(parsePrice('123', { goodsName: '商品', goodsPriceModel: { basePrice: { price: '1,111' } } }).price, 1111);
  for (const data of [null, { goodsName: '商品' }, { goodsName: '商品', goodsPriceModel: { basePrice: { price: '0' } } }]) {
    assert.throws(() => parsePrice('123', data));
  }
  assert.equal(parseStock({ goodsStock: '0' }), 0);
  assert.equal(parseStock({ goodsStock: '1' }), 1);
  assert.throws(() => parseStock({}));
});

test('cloud poll updates due goods once and waits four hours before repeating', async t => {
  const { db, env } = setup(t); seed(db);
  let calls = 0;
  const source = async (_url, options) => {
    calls++; assert.equal(options.headers['User-Agent'], 'price-tracker-bot/1.0');
    return Response.json(String(_url).endsWith('getInstantGoodsStatus')
      ? { success: true, rtnGoods: { '123': { goodsName: '商品', goodsPriceModel: { basePrice: { price: '900' } } } } }
      : { success: true, rtnGoodsData: { goodsStock: '1' } });
  };
  await pollPrices(env, source); await pollPrices(env, source);
  assert.equal(calls, 2);
  assert.equal(db.prepare('SELECT price FROM good_info').get().price, 900);
  assert.ok(db.prepare('SELECT next_check FROM good_info').get().next_check >= Date.now() / 1000 + 14390);
});

test('unavailable goods retain history and user lists, with daily retries', async t => {
  const { db, env } = setup(t); seed(db);
  await acceptPrices(priceRequest([{ id: '123', unavailable: true, observed_at: Math.floor(Date.now() / 1000) }]), env);
  const row = db.prepare('SELECT * FROM good_info').get();
  assert.equal(row.price, 1000); assert.equal(row.last_error, 'product_unavailable');
  assert.ok(row.next_check > Date.now() / 1000 + 86390);
  incoming(db, 1, '/my'); await processOneUpdate(env);
  assert.match(db.prepare('SELECT payload FROM outbox').get().payload, /查無商品/);
});

test('source failures preserve prices and malformed source results are rejected', async t => {
  const { db, env } = setup(t); seed(db);
  await pollPrices(env, async () => new Response('blocked', { status: 403 }));
  assert.equal(db.prepare('SELECT price FROM good_info').get().price, 1000);
  assert.match(db.prepare('SELECT last_error FROM good_info').get().last_error, /403/);
  const bad = await readPrices(['123'], env, async () => Response.json({ goods: [{ id: '999' }] }));
  assert.ok(bad[0].error);
});

test('instant price query displays live data without changing subscriptions or baselines', async t => {
  const { db, env } = setup(t); seed(db);
  incoming(db, 1, '/price https://www.momoshop.com.tw/product/123');
  await processOneUpdate(env, async () => ({ id: '123', name: '即時商品', price: 950, stock_state: 1 }));
  assert.match(db.prepare('SELECT payload FROM outbox').get().payload, /即時價格：950/);
  assert.equal(db.prepare("SELECT price FROM user_sub_good WHERE user_id='10'").get().price, 1000);
  assert.equal(db.prepare('SELECT price FROM good_info').get().price, 1000);
});


test('one batch request rechecks 100 known unavailable products and detects their return', async () => {
  const goods = Array.from({ length: 100 }, (_, i) => ({ id: String(i + 1), product_id: String(i + 1), unavailable: true }));
  let calls = 0;
  const fetcher = async url => {
    calls++;
    assert.match(String(url), /getInstantGoodsStatus$/);
    return Response.json({ success: true, rtnGoods: Object.fromEntries(goods.map(g => [g.id,
      { goodsName: '', goodsPriceModel: { basePrice: { price: '0' } } }])) });
  };
  const result = await getPrices(goods, fetcher);
  assert.equal(calls, 1);
  assert.equal(result.filter(g => g.unavailable).length, 100);
  const returned = await getPrices([goods[0]], async url => String(url).endsWith('getInstantGoodsStatus') ?
    Response.json({ success: true, rtnGoods: { '1': { goodsName: '回架商品', goodsPriceModel: { basePrice: { price: '100' } } } } }) :
    Response.json({ success: true, rtnGoodsData: { goodsStock: '1' } }));
  assert.equal(returned[0].price, 100);
  assert.equal(returned[0].stock_state, 1);
  const failed = await getPrices(goods, async () => new Response('', { status: 403 }));
  assert.equal(failed.filter(g => g.error && !g.unavailable).length, 100);
});

test('verified replacement codes keep the original subscription key and deduplicate stock calls', async t => {
  const html = '<script type="application/ld+json">' + JSON.stringify({ '@graph': [{ '@type': 'ProductGroup',
    sku: '999', hasVariant: [{ offers: { url: 'https://www.momoshop.com.tw/product/123' } }] }] }) + '</script>';
  assert.equal(resolveProductCode('123', html), '999');
  assert.throws(() => resolveProductCode('456', html), /missing verified/);
  assert.throws(() => resolveProductCode('123', html.replace('www.momoshop.com.tw', 'evil.test')), /missing verified/);
  let calls = 0;
  const source = await getPrices([{ id: '123', product_id: '999' }, { id: '999', product_id: '999' }], async url => {
    calls++;
    return String(url).endsWith('getInstantGoodsStatus') ? Response.json({ success: true, rtnGoods: {
      '999': { goodsName: '商品', goodsPriceModel: { basePrice: { price: '900' } } },
    } }) : Response.json({ success: true, rtnGoodsData: { goodsStock: '1' } });
  });
  assert.equal(calls, 2);
  const { db, env } = setup(t); seed(db);
  await acceptPrices(new Request('https://test', { method: 'POST', body: JSON.stringify({ run_id: '5', goods: [source[0]] }) }), env);
  assert.equal(db.prepare("SELECT source_id FROM good_info WHERE id='123'").get().source_id, '999');
  assert.equal(db.prepare("SELECT price FROM user_sub_good WHERE id='sub-10'").get().price, 1000);
  const page = await (await trackedGoods(new Request('https://test'), env)).json();
  assert.equal(page.goods[0].product_id, '999');
});

test('twenty price updates use two SQL statements and only due or failed goods are selected for manual refresh', async t => {
  const { db, env } = setup(t); seed(db);
  const timestamp = Math.floor(Date.now() / 1000);
  const goods = Array.from({ length: 20 }, (_, i) => ({ id: String(i + 1000), name: '商品', price: 900, stock_state: 1, observed_at: timestamp }));
  for (const g of goods) db.prepare('INSERT INTO good_info(id,name,price,stock_state) VALUES (?,?,1000,1)').run(g.id, g.name);
  const response = await acceptPrices(new Request('https://test', { method: 'POST', body: JSON.stringify({ run_id: '6', goods }) }), env);
  assert.equal((await response.json()).sql_statements, 2);
  assert.equal(db.prepare('SELECT COUNT(*) AS n FROM good_info WHERE price=900').get().n, 20);
  db.exec("UPDATE good_info SET next_check=unixepoch()+3600, last_error='HTTP 503' WHERE id='123'");
  assert.equal((await (await trackedGoods(new Request('https://test/?due=1'), env)).json()).goods.length, 0);
  assert.equal((await (await trackedGoods(new Request('https://test/?errors=1'), env)).json()).goods[0].id, '123');
});


test('native scheduled polling bounds each invocation to ten due products', async t => {
  const { db, env } = setup(t); seed(db);
  for (let i = 1; i < 20; i++) {
    db.prepare('INSERT INTO good_info(id,name,price,stock_state) VALUES (?, ?,1000,1)').run(String(i), '商品');
    db.prepare('INSERT INTO user_sub_good(id,user_id,good_id,price) VALUES (?, ?, ?,1000)').run(`budget-${i}`, '10', String(i));
  }
  let requested = [];
  await pollPrices(env, async (url, options) => {
    if (String(url).endsWith('getInstantGoodsStatus')) {
      requested = JSON.parse(options.body).goodsCodes;
      return Response.json({ success: true, rtnGoods: Object.fromEntries(requested.map(id => [id,
        { goodsName: '商品', goodsPriceModel: { basePrice: { price: '1000' } } }])) });
    }
    return Response.json({ success: true, rtnGoodsData: { goodsStock: '1' } });
  });
  assert.equal(requested.length, 10);
  assert.equal(db.prepare('SELECT COUNT(*) AS n FROM good_info WHERE last_success IS NOT NULL').get().n, 10);
  assert.equal(db.prepare('SELECT COUNT(*) AS n FROM good_info WHERE next_check=0').get().n, 10);
});
