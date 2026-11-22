import { getPrices } from './momo-api.js';
import { productUrl } from './links.js';

const now = () => Math.floor(Date.now() / 1000);
const statement = (env, sql, ...args) => env.DB.prepare(sql).bind(...args);

export async function trackedGoods(request, env) {
  const cursor = new URL(request.url).searchParams.get('cursor') || '';
  const rows = await statement(env, `SELECT g.id FROM good_info g WHERE g.state = 1 AND g.id > ?
    AND EXISTS (SELECT 1 FROM user_sub_good s JOIN "user" u ON u.id = s.user_id
      WHERE s.good_id = g.id AND s.state = 1 AND u.state = 1)
    ORDER BY g.id LIMIT 200`, cursor).all();
  return Response.json({ goods: rows.results.map(g => ({ id: g.id, product_id: g.id.replace(/\s+\/add$/, '') })),
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
  const writes = [];
  const seen = new Set();
  for (const good of body.goods) {
    if (!good || !/^\d+(?:\s+\/add)?$/.test(good.id || '') || seen.has(good.id)) {
      return new Response('Invalid product ID', { status: 400 });
    }
    seen.add(good.id);
    if (good.unavailable === true) {
      if (!Number.isSafeInteger(good.observed_at) || good.observed_at > now() + 60 || good.observed_at < now() - 86400) return new Response('Invalid product timestamp', { status: 400 });
      writes.push(statement(env, `UPDATE good_info SET last_error = 'product_unavailable', last_checked = ?, next_check = ?
        WHERE id = ? AND (last_checked IS NULL OR last_checked < ?)`, good.observed_at, now() + 86400, good.id, good.observed_at));
      continue;
    }
    if (good.error) {
      writes.push(statement(env, 'UPDATE good_info SET last_error = ?, next_check = ? WHERE id = ?', String(good.error).slice(0, 300), now() + 14400, good.id));
      continue;
    }
    if (typeof good.name !== 'string' || !good.name.trim() || good.name.length > 500 ||
        !Number.isSafeInteger(good.price) || good.price <= 0 || ![0, 1].includes(good.stock_state) ||
        !Number.isSafeInteger(good.observed_at) || good.observed_at > now() + 60 || good.observed_at < now() - 86400) {
      return new Response('Invalid product data', { status: 400 });
    }
    const discount = 'g.price != ? AND s.price > ?';
    const restock = 'g.stock_state = 0 AND ? = 1';
    writes.push(statement(env, `INSERT OR IGNORE INTO outbox(id, user_id, payload, created_at)
      SELECT ? || ':' || s.id, s.user_id,
        json_object('text', ? || char(10) ||
          CASE WHEN ${discount} THEN '目前價格為 ' || CAST(? AS INTEGER) || '，低於加入追蹤時的 ' || s.price || char(10) ELSE '' END ||
          CASE WHEN ${restock} THEN '目前已經可購買！' || char(10) ELSE '' END || char(10) || ?,
          'link_preview_options', json_object('is_disabled', json('true'))), ?
      FROM user_sub_good s JOIN "user" u ON u.id = s.user_id JOIN good_info g ON g.id = s.good_id
      WHERE g.id = ? AND s.state = 1 AND u.state = 1
        AND (g.last_success IS NULL OR g.last_success < ?) AND ((${discount}) OR (${restock}))`,
    `sync:${body.run_id}:${good.id}`, good.name, good.price, good.price, good.price, good.stock_state,
    productUrl(good.id), now(), good.id, good.observed_at, good.price, good.price, good.stock_state));
    writes.push(statement(env, `UPDATE good_info SET name = ?, price = ?, stock_state = ?, version = version + 1,
      last_success = ?, last_checked = ?, next_check = ?, last_error = NULL, update_time = CURRENT_TIMESTAMP WHERE id = ?
      AND (last_success IS NULL OR last_success < ?)`,
    good.name, good.price, good.stock_state, good.observed_at, good.observed_at, now() + 14400, good.id, good.observed_at));
  }
  if (writes.length) await env.DB.batch(writes);
  return Response.json({ accepted: body.goods.length });
}

export async function readPrices(ids, _env, fetcher) {
  return getPrices(ids.map(id => ({ id, product_id: id })), fetcher);
}

export async function pollPrices(env, fetcher = fetch) {
  const timestamp = now();
  const due = await statement(env, `UPDATE good_info SET next_check = ? WHERE id IN (
    SELECT g.id FROM good_info g WHERE g.state = 1 AND g.next_check <= ?
    AND EXISTS (SELECT 1 FROM user_sub_good s JOIN "user" u ON u.id = s.user_id
      WHERE s.good_id = g.id AND s.state = 1 AND u.state = 1)
    ORDER BY g.next_check, g.id LIMIT 8) RETURNING id`, timestamp + 14400, timestamp).all();
  if (!due.results.length) return;
  const ids = [...new Set(due.results.map(g => g.id.replace(/\s+\/add$/, '')))];
  let results;
  try {
    const prices = await readPrices(ids, env, fetcher);
    results = due.results.map(g => ({ ...prices.find(p => p.id === g.id.replace(/\s+\/add$/, '')), id: g.id }));
  } catch (error) { results = due.results.map(g => ({ id: g.id, error: error.message })); }
  const response = await acceptPrices(new Request('https://internal/prices', { method: 'POST',
    body: JSON.stringify({ run_id: String(timestamp), goods: results }) }), env);
  if (!response.ok) throw new Error('Invalid price source response');
}
