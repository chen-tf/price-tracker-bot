import { getPrices } from './momo-api.js';
import { productUrl } from './links.js';

const now = () => Math.floor(Date.now() / 1000);
const statement = (env, sql, ...args) => env.DB.prepare(sql).bind(...args);

export async function trackedGoods(request, env) {
  const params = new URL(request.url).searchParams;
  const cursor = params.get('cursor') || '';
  const filter = params.get('errors') === '1' ? "AND g.last_error IS NOT NULL AND g.last_error != 'product_unavailable'" :
    params.get('due') === '1' ? 'AND g.next_check <= unixepoch()' : '';
  const rows = await statement(env, `SELECT g.id, g.source_id, g.last_error, g.next_check FROM good_info g WHERE g.state = 1 AND g.id > ?
    ${filter}
    AND EXISTS (SELECT 1 FROM user_sub_good s JOIN "user" u ON u.id = s.user_id
      WHERE s.good_id = g.id AND s.state = 1 AND u.state = 1)
    ORDER BY g.id LIMIT 200`, cursor).all();
  return Response.json({ goods: rows.results.map(g => ({ id: g.id, product_id: g.source_id || g.id.replace(/\s+\/add$/, ''), unavailable: g.last_error === 'product_unavailable' })),
    next_cursor: rows.results.length === 200 ? rows.results.at(-1).id : null });
}

export async function acceptPrices(request, env) {
  if (Number(request.headers.get('content-length')) > 65536) return new Response('Too large', { status: 413 });
  const raw = await request.text();
  if (new TextEncoder().encode(raw).length > 65536) return new Response('Too large', { status: 413 });
  let body;
  try { body = JSON.parse(raw); } catch { return new Response('Invalid JSON', { status: 400 }); }
  if (!body || !/^\d+$/.test(String(body.run_id)) || !Array.isArray(body.goods) || body.goods.length > 20) {
    return new Response('Invalid batch', { status: 400 });
  }
  const valid = [], unavailable = [], errors = [];
  const seen = new Set();
  const timestamp = now();
  for (const good of body.goods) {
    if (!good || !/^\d+(?:\s+\/add)?$/.test(good.id || '') || seen.has(good.id)) {
      return new Response('Invalid product ID', { status: 400 });
    }
    seen.add(good.id);
    if (good.unavailable === true) {
      if (!Number.isSafeInteger(good.observed_at) || good.observed_at > timestamp + 60 || good.observed_at < timestamp - 86400) return new Response('Invalid product timestamp', { status: 400 });
      unavailable.push({ id: good.id, observed_at: good.observed_at });
      continue;
    }
    if (good.error) {
      errors.push({ id: good.id, error: String(good.error).slice(0, 300) });
      continue;
    }
    if ((good.source_id !== undefined && !/^\d+$/.test(good.source_id)) || typeof good.name !== 'string' || !good.name.trim() || good.name.length > 500 ||
        !Number.isSafeInteger(good.price) || good.price <= 0 || ![0, 1].includes(good.stock_state) ||
        !Number.isSafeInteger(good.observed_at) || good.observed_at > timestamp + 60 || good.observed_at < timestamp - 86400) {
      return new Response('Invalid product data', { status: 400 });
    }
    valid.push({ id: good.id, name: good.name, price: good.price, stock_state: good.stock_state,
      observed_at: good.observed_at, source_id: good.source_id || null, url: productUrl(good.id) });
  }
  const writes = [];
  // One JSON table per batch keeps SQL preparation and round trips independent of item count.
  if (valid.length) {
    const data = JSON.stringify(valid);
    writes.push(statement(env, `INSERT OR IGNORE INTO outbox(id, user_id, payload, created_at)
      SELECT ? || g.id || ':' || s.id, s.user_id,
        json_object('text', j.value ->> '$.name' || char(10) ||
          CASE WHEN g.price != j.value ->> '$.price' AND s.price > j.value ->> '$.price'
            THEN '目前價格為 ' || CAST(j.value ->> '$.price' AS INTEGER) || '，低於加入追蹤時的 ' || s.price || char(10) ELSE '' END ||
          CASE WHEN g.stock_state = 0 AND j.value ->> '$.stock_state' = 1
            THEN '目前已經可購買！' || char(10) ELSE '' END || char(10) || (j.value ->> '$.url'),
          'link_preview_options', json_object('is_disabled', json('true'))), ?
      FROM json_each(?) j JOIN good_info g ON g.id = j.value ->> '$.id'
        JOIN user_sub_good s ON s.good_id = g.id JOIN "user" u ON u.id = s.user_id
      WHERE s.state = 1 AND u.state = 1 AND (g.last_success IS NULL OR g.last_success < j.value ->> '$.observed_at')
        AND ((g.price != j.value ->> '$.price' AND s.price > j.value ->> '$.price')
          OR (g.stock_state = 0 AND j.value ->> '$.stock_state' = 1))`, `sync:${body.run_id}:`, timestamp, data));
    writes.push(statement(env, `UPDATE good_info AS g SET name = j.value ->> '$.name', price = j.value ->> '$.price',
      stock_state = j.value ->> '$.stock_state', source_id = COALESCE(j.value ->> '$.source_id', g.source_id), version = g.version + 1,
      last_success = j.value ->> '$.observed_at', last_checked = j.value ->> '$.observed_at', next_check = ?,
      last_error = NULL, update_time = CURRENT_TIMESTAMP
      FROM json_each(?) j WHERE g.id = j.value ->> '$.id'
        AND (g.last_success IS NULL OR g.last_success < j.value ->> '$.observed_at')`, timestamp + 14400, data));
  }
  if (unavailable.length) writes.push(statement(env, `UPDATE good_info AS g SET last_error = 'product_unavailable',
    last_checked = j.value ->> '$.observed_at', next_check = ? FROM json_each(?) j
    WHERE g.id = j.value ->> '$.id' AND (g.last_checked IS NULL OR g.last_checked < j.value ->> '$.observed_at')`,
  timestamp + 86400, JSON.stringify(unavailable)));
  if (errors.length) writes.push(statement(env, `UPDATE good_info AS g SET last_error = j.value ->> '$.error', next_check = ?
    FROM json_each(?) j WHERE g.id = j.value ->> '$.id'`, timestamp + 14400, JSON.stringify(errors)));
  const results = writes.length ? await env.DB.batch(writes) : [];
  const usage = { sql_statements: writes.length,
    rows_read: results.reduce((sum, r) => sum + (r.meta?.rows_read || 0), 0),
    rows_written: results.reduce((sum, r) => sum + (r.meta?.rows_written || 0), 0) };
  return Response.json({ accepted: body.goods.length, ...usage });
}

export async function readPrices(ids, _env, fetcher) {
  return getPrices(ids.map(id => typeof id === 'string' ? { id, product_id: id } : id), fetcher);
}

export async function pollPrices(env, fetcher = fetch) {
  const timestamp = now();
  const due = await statement(env, `UPDATE good_info SET next_check = ? WHERE id IN (
    SELECT g.id FROM good_info g WHERE g.state = 1 AND g.next_check <= ?
    AND EXISTS (SELECT 1 FROM user_sub_good s JOIN "user" u ON u.id = s.user_id
      WHERE s.good_id = g.id AND s.state = 1 AND u.state = 1)
    ORDER BY g.next_check, g.id LIMIT 20) RETURNING id, source_id, last_error`, timestamp + 14400, timestamp).all();
  if (!due.results.length) return;
  const ids = due.results.map(g => ({ id: g.id.replace(/\s+\/add$/, ''),
    product_id: g.source_id || g.id.replace(/\s+\/add$/, ''), unavailable: g.last_error === 'product_unavailable' }));
  let results;
  try {
    const prices = await readPrices(ids, env, fetcher);
    results = due.results.map(g => ({ ...prices.find(p => p.id === g.id.replace(/\s+\/add$/, '')), id: g.id }));
  } catch (error) { results = due.results.map(g => ({ id: g.id, error: error.message })); }
  const response = await acceptPrices(new Request('https://internal/prices', { method: 'POST',
    body: JSON.stringify({ run_id: String(timestamp), goods: results }) }), env);
  if (!response.ok) throw new Error('Invalid price source response');
}
