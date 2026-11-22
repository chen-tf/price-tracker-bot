import { fetchProduct, productUrl } from './momo.js';
import { acceptPrices, pollPrices, trackedGoods } from './sync.js';

const now = () => Math.floor(Date.now() / 1000);
const statement = (env, sql, ...args) => env.DB.prepare(sql).bind(...args);
const help = '/my 顯示追蹤清單\n/add 貼上 momo 商品網址加入追蹤\n/price 商品網址：即時查價\n/clear 刪除指定商品\n/clearall 清空追蹤清單\n/cancel 放棄操作';

function messagePayload(text, extra = {}) {
  return { text, link_preview_options: { is_disabled: true }, ...extra };
}

function reply(env, updateId, userId, text, extra = {}, suffix = 'reply') {
  return statement(env, `INSERT OR IGNORE INTO outbox(id, user_id, payload, created_at, priority) VALUES (?, ?, ?, ?, 0)`,
    `update:${updateId}:${suffix}`, userId, JSON.stringify(messagePayload(text, extra)), now());
}

async function telegram(env, method, payload, fetcher = fetch) {
  const response = await fetcher(`https://api.telegram.org/bot${env.BOT_TOKEN}/${method}`, {
    method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload), signal: AbortSignal.timeout(12000),
  });
  const result = await response.json();
  if (!response.ok || !result.ok) {
    // Never log request URLs: Telegram embeds the bot token in the path.
    const error = new Error('Telegram API request failed');
    error.code = result.error_code || response.status;
    error.retryAfter = result.parameters?.retry_after;
    throw error;
  }
  return result.result;
}

export async function drainOutbox(env, fetcher = fetch, limit = 6) {
  let attempted = 0;
  for (let i = 0; i < limit; i++) {
    const timestamp = now();
    const item = await statement(env, `UPDATE outbox SET next_attempt = ?, attempts = attempts + 1
      WHERE id = (SELECT o.id FROM outbox o JOIN "user" u ON u.id = o.user_id
        WHERE o.sent_at IS NULL AND o.next_attempt <= ? AND u.state = 1
        AND (o.subscription_id IS NULL OR EXISTS (SELECT 1 FROM user_sub_good s WHERE s.id = o.subscription_id AND s.state = 1))
        ORDER BY o.priority, o.created_at, o.id LIMIT 1)
      RETURNING *, (SELECT chat_id FROM "user" WHERE id = outbox.user_id) AS chat_id`, timestamp + 120, timestamp).first();
    if (!item) break;
    attempted++;
    try {
      await telegram(env, 'sendMessage', { ...JSON.parse(item.payload), chat_id: item.chat_id }, fetcher);
      await statement(env, 'UPDATE outbox SET sent_at = ? WHERE id = ?', now(), item.id).run();
    } catch (error) {
      if (error.code === 403) {
        await env.DB.batch([
          statement(env, 'UPDATE "user" SET state = 0 WHERE id = ?', item.user_id),
          statement(env, 'UPDATE user_sub_good SET state = 0 WHERE user_id = ?', item.user_id),
          statement(env, 'UPDATE outbox SET sent_at = ? WHERE user_id = ? AND sent_at IS NULL', now(), item.user_id),
        ]);
      } else if (error.code === 400) {
        // A permanently invalid payload must not starve later messages.
        await statement(env, 'UPDATE outbox SET sent_at = -1 WHERE id = ?', item.id).run();
        console.error(JSON.stringify({ event: 'telegram_payload_rejected', outboxId: item.id }));
      } else {
        const delay = Math.max(Number(error.retryAfter) || 0, Math.min(3600, 30 * 2 ** Math.min(item.attempts, 7)));
        await statement(env, 'UPDATE outbox SET next_attempt = ? WHERE id = ?', now() + delay, item.id).run();
      }
    }
  }
  return attempted;
}

async function planUpdate(env, update, getProduct) {
  const callback = update.callback_query;
  const message = update.message || callback?.message;
  const actor = callback?.from || message?.from;
  // Personal lists are only exposed in a private chat with their owner.
  if (!message || !actor || message.chat?.type !== 'private' || String(message.chat.id) !== String(actor.id)) return [];
  const userId = String(actor.id);
  const writes = [];
  writes.push(statement(env, `INSERT INTO "user"(id, chat_id) VALUES (?, ?)
    ON CONFLICT(id) DO UPDATE SET chat_id = excluded.chat_id, state = 1, update_time = CURRENT_TIMESTAMP`,
  userId, String(message.chat.id)));
  const respond = (text, extra, suffix) => writes.push(reply(env, update.update_id, userId, text, extra, suffix));
  if (callback) {
    if (/^(?:clear:)?\d+(?:\s+\/add)?$/.test(callback.data || '')) {
      const goodId = callback.data.replace(/^clear:/, '');
      writes.push(statement(env, `UPDATE outbox SET sent_at = -1 WHERE sent_at IS NULL AND user_id = ?
        AND subscription_id IN (SELECT id FROM user_sub_good WHERE user_id = ? AND good_id = ?)`, userId, userId, goodId));
      writes.push(statement(env, 'UPDATE user_sub_good SET state = 0, update_time = CURRENT_TIMESTAMP WHERE user_id = ? AND good_id = ?',
        userId, goodId));
      respond('已移除該追蹤商品。');
    }
    return writes;
  }
  const text = message.text?.trim() || '';
  const [rawCommand] = text.split(/\s/);
  const command = rawCommand.split('@')[0].toLowerCase();
  const argument = text.slice(rawCommand.length).trim();
  if (command === '/start' || command === '/help') respond(help);
  else if (command === '/price') {
    if (!argument) respond('請輸入 /price momo商品網址，即時查詢價格與庫存。');
    else {
      try {
        const good = await getProduct(argument);
        respond(`${good.name}\n即時價格：${good.price}\n${good.stock_state === 1 ? '目前可購買' : '目前缺貨'}\n${productUrl(good.id)}`);
      } catch (error) { respond(error.message); }
    }
  }
  else if (command === '/line') respond('LINE Notify 已於 2025/03/31 終止服務，目前透過 Telegram 發送通知。');
  else if (command === '/cancel') {
    writes.push(statement(env, 'UPDATE "user" SET pending_action = NULL WHERE id = ?', userId));
    respond('已放棄動作。');
  } else if (command === '/add' && !argument) {
    writes.push(statement(env, 'UPDATE "user" SET pending_action = ? WHERE id = ?', 'add', userId));
    respond('貼上 momo 商品網址加入追蹤，或輸入 /cancel。');
  } else if (command === '/my' || command === '/clear') {
    const rows = await statement(env, `SELECT g.*, s.price AS original_price FROM user_sub_good s
      JOIN good_info g ON g.id = s.good_id WHERE s.user_id = ? AND s.state = 1 ORDER BY s.create_time, s.id`, userId).all();
    if (!rows.results.length) respond('目前沒有追蹤商品。');
    else if (command === '/clear') {
      respond('請點選要刪除的商品', { reply_markup: { inline_keyboard: rows.results.map(g =>
        [{ text: g.name.slice(0, 60), callback_data: `clear:${g.id}` }]) } });
    } else {
      // One message per five products stays below Telegram's 4096-character limit.
      for (let i = 0; i < rows.results.length; i += 5) {
        respond(rows.results.slice(i, i + 5).map(g => `${g.name}\n目前紀錄價格：${g.price}；加入時：${g.original_price}${g.last_error === 'product_unavailable' ? '\nmomo 目前查無商品，保留最後紀錄。' : ''}\n${productUrl(g.id)}`).join('\n\n'),
          {}, `list:${i}`);
      }
    }
  } else if (command === '/clearall') {
    writes.push(statement(env, 'UPDATE outbox SET sent_at = -1 WHERE sent_at IS NULL AND user_id = ? AND subscription_id IS NOT NULL', userId));
    writes.push(statement(env, 'UPDATE user_sub_good SET state = 0, update_time = CURRENT_TIMESTAMP WHERE user_id = ?', userId));
    respond('已清空追蹤清單。');
  } else if (command === '/add' || /https:\/\//i.test(text)) {
    try {
      const fresh = await getProduct(command === '/add' ? argument : text);
      // The conditional insert enforces the limit even with simultaneous updates.
      writes.push(statement(env, `INSERT INTO good_info(id, name, price, stock_state, next_check, source_id)
        VALUES (?, ?, ?, ?, ?, ?) ON CONFLICT(id) DO UPDATE SET state = 1, next_check = 0, source_id = COALESCE(excluded.source_id, good_info.source_id)`,
      fresh.id, fresh.name, fresh.price, fresh.stock_state, now() + 14400, fresh.source_id || null));
      writes.push(statement(env, `UPDATE outbox SET sent_at = -1 WHERE sent_at IS NULL AND subscription_id IN
        (SELECT id FROM user_sub_good WHERE user_id = ? AND good_id = ?)`, userId, fresh.id));
      writes.push(statement(env, `INSERT INTO user_sub_good(id, user_id, good_id, price)
        SELECT ?, ?, ?, ? WHERE
          (SELECT COUNT(*) FROM user_sub_good WHERE user_id = ? AND state = 1) < 20
          OR EXISTS (SELECT 1 FROM user_sub_good WHERE user_id = ? AND good_id = ? AND state = 1)
        ON CONFLICT(user_id, good_id) DO UPDATE SET price = excluded.price, state = 1,
          is_notified = 0, update_time = CURRENT_TIMESTAMP`,
      crypto.randomUUID(), userId, fresh.id, fresh.price, userId, userId, fresh.id));
      writes.push(statement(env, `INSERT OR IGNORE INTO outbox(id, user_id, payload, created_at, priority)
        SELECT ?, ?, CASE WHEN EXISTS (SELECT 1 FROM user_sub_good WHERE user_id = ? AND good_id = ? AND state = 1)
          THEN ? ELSE ? END, ?, 0`, `update:${update.update_id}:reply`, userId, userId, fresh.id,
      JSON.stringify(messagePayload(`已追蹤 ${fresh.name}\n加入時價格：${fresh.price}\n${productUrl(fresh.id)}`)),
      JSON.stringify(messagePayload('最多可追蹤 20 件商品，請先移除部分商品。')), now()));
      writes.push(statement(env, 'UPDATE "user" SET pending_action = NULL WHERE id = ?', userId));
    } catch (error) {
      respond(error.message);
    }
  } else respond(help);
  return writes;
}

export async function processOneUpdate(env, getProduct = input => fetchProduct(input, fetch, env)) {
  const timestamp = now();
  const item = await statement(env, `UPDATE telegram_update SET lease_until = ?, attempts = attempts + 1
    WHERE id = (SELECT candidate.id FROM telegram_update candidate WHERE candidate.status = 'pending' AND candidate.lease_until <= ?
      AND candidate.attempts < 10 AND NOT EXISTS (SELECT 1 FROM telegram_update prior
        WHERE prior.actor_id = candidate.actor_id AND prior.id < candidate.id AND prior.status = 'pending'
        AND (prior.attempts < 10 OR prior.lease_until > ?))
      ORDER BY candidate.id LIMIT 1) RETURNING *`, timestamp + 300, timestamp, timestamp).first();
  if (!item) return false;
  const writes = await planUpdate(env, JSON.parse(item.payload), getProduct);
  writes.push(statement(env, `UPDATE telegram_update SET status = 'done', payload = '{}', attempts = ? WHERE id = ?`, item.attempts, item.id));
  await env.DB.batch(writes);
  return true;
}

export default {
  async fetch(request, env, ctx) {
    const url = new URL(request.url);
    if (url.pathname.startsWith('/internal/')) {
      if (!env.SYNC_SECRET || request.headers.get('Authorization') !== `Bearer ${env.SYNC_SECRET}`) {
        return new Response('Unauthorized', { status: 401 });
      }
      if (url.pathname === '/internal/tracked-goods' && request.method === 'GET') return trackedGoods(request, env);
      if (url.pathname === '/internal/prices' && request.method === 'POST') return acceptPrices(request, env);
    if (url.pathname === '/internal/health' && request.method === 'GET') {
      try {
        const health = await statement(env, `WITH tracked AS (
          SELECT g.* FROM good_info g WHERE g.state = 1 AND EXISTS (
            SELECT 1 FROM user_sub_good s JOIN "user" u ON u.id = s.user_id
            WHERE s.good_id = g.id AND s.state = 1 AND u.state = 1))
          SELECT (SELECT MAX(last_success) FROM tracked) AS last_price_success,
          (SELECT COUNT(*) FROM tracked WHERE last_error = 'product_unavailable') AS unavailable_products,
          (SELECT COUNT(*) FROM tracked WHERE COALESCE(last_error, '') != 'product_unavailable'
            AND (last_success IS NULL OR last_success < unixepoch() - 28800)) AS stale_products,
          (SELECT COUNT(*) FROM tracked WHERE last_error IS NOT NULL AND last_error != 'product_unavailable') AS failed_products,
          (SELECT COUNT(*) FROM telegram_update WHERE status = 'pending') AS pending_updates,
          (SELECT COUNT(*) FROM outbox WHERE sent_at IS NULL) AS pending_messages`).first();
        return Response.json({ status: 'ok', price_source: 'cloudflare-native-http', ...health });
      } catch { return Response.json({ status: 'database_unavailable' }, { status: 503 }); }
    }
      return new Response('Not found', { status: 404 });
    }
    if (url.pathname === '/health' && request.method === 'GET') {
      try {
        await statement(env, 'SELECT 1 AS ok').first();
        return Response.json({ status: 'ok', price_source: 'cloudflare-native-http' });
      } catch { return Response.json({ status: 'database_unavailable' }, { status: 503 }); }
    }
    if (url.pathname !== '/webhook' || request.method !== 'POST') return new Response('Not found', { status: 404 });
    if (!env.WEBHOOK_SECRET || request.headers.get('X-Telegram-Bot-Api-Secret-Token') !== env.WEBHOOK_SECRET) {
      return new Response('Unauthorized', { status: 401 });
    }
    if (!env.BOT_TOKEN) return new Response('Bot not configured', { status: 503 });
    if (Number(request.headers.get('content-length')) > 65536) return new Response('Too large', { status: 413 });
    const body = await request.text();
    if (new TextEncoder().encode(body).length > 65536) return new Response('Too large', { status: 413 });
    let update;
    try { update = JSON.parse(body); } catch { return new Response('Invalid JSON', { status: 400 }); }
    if (!update || !Number.isSafeInteger(update.update_id)) return new Response('Invalid update', { status: 400 });
    // Acknowledge only after durable storage. Duplicate Telegram deliveries share one row.
    await statement(env, 'INSERT OR IGNORE INTO telegram_update(id, payload, created_at) VALUES (?, ?, ?)',
      update.update_id, body, now()).run();
    ctx.waitUntil((async () => {
      if (update.callback_query?.id) {
        try { await telegram(env, 'answerCallbackQuery', { callback_query_id: update.callback_query.id }); }
        catch { /* Expired callback acknowledgments do not prevent processing a deletion. */ }
      }
      await processOneUpdate(env);
      await drainOutbox(env, fetch, 1);
    })().catch(() => {
      console.error(JSON.stringify({ event: 'update_deferred_to_cron' }));
    }));
    return new Response('OK');
  },

  async scheduled(controller, env, _ctx) {
    // Three of every four minutes are reserved for prices, even with a message backlog.
    // Separate price and Telegram work keeps each invocation within the Free CPU budget.
    const minute = new Date(controller.scheduledTime ?? Date.now()).getUTCMinutes();
    if (minute % 4 !== 0) { await pollPrices(env); return; }
    try { await processOneUpdate(env); } catch { console.error(JSON.stringify({ event: 'update_processing_failed' })); }
    await drainOutbox(env, fetch, 3);
    if (minute !== 0) return;
    const cutoff = now() - 7 * 86400;
    await env.DB.batch([
      statement(env, "UPDATE telegram_update SET status = 'failed', payload = '{}' WHERE status = 'pending' AND attempts >= 10 AND lease_until <= ?", now()),
      statement(env, "DELETE FROM telegram_update WHERE status IN ('done', 'failed') AND created_at < ?", cutoff),
      statement(env, 'DELETE FROM outbox WHERE sent_at IS NOT NULL AND created_at < ?', cutoff),
    ]);
  },
};
