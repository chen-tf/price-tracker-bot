import { pathToFileURL } from 'node:url';

const pause = ms => new Promise(resolve => setTimeout(resolve, ms));
const api = 'https://www.momoshop.com.tw/api/moecapp/';

export function parsePrice(id, data) {
  if (!data?.goodsName) throw new Error('missing product name');
  const raw = String(data.goodsPriceModel?.basePrice?.price ?? '').replaceAll(',', '');
  const price = Number(raw);
  if (!/^\d+$/.test(raw) || !Number.isSafeInteger(price) || price <= 0) throw new Error('missing valid price');
  return { id, name: data.goodsName.slice(0, 500), price };
}

export function parseStock(data) {
  const value = String(data?.goodsStock);
  if (!['0', '1'].includes(value)) throw new Error('unknown stock state');
  return Number(value);
}

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

async function momo(method, payload) {
  const data = await requestJson(api + method, {
    method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload),
  });
  if (data.success !== true) throw new Error('momo API did not return success');
  return data;
}

export async function getPrices(goods) {
  const timestamp = Math.floor(Date.now() / 1000);
  let prices;
  try {
    prices = await momo('getInstantGoodsStatus', { columnType: '', priceDescrip: true,
      implementTypes: ['price'], goodsCodes: [...new Set(goods.map(g => g.product_id))], host: 'momoshop' });
  } catch (error) {
    return goods.map(g => ({ id: g.id, error: `price fetch: ${error.message}` }));
  }
  const result = [];
  // Four requests per second at most, without overwhelming the public shop API.
  for (let i = 0; i < goods.length; i += 4) {
    result.push(...await Promise.all(goods.slice(i, i + 4).map(async good => {
      try {
        const fresh = parsePrice(good.id, prices.rtnGoods?.[good.product_id]);
        const stock = await momo('getGoodsRealTimeInfo', { goodsCode: good.product_id,
          fsCode: '', hour: '', addressData: {}, categoryCode: '', host: 'momoshop' });
        return { ...fresh, stock_state: parseStock(stock.rtnGoodsData), observed_at: timestamp };
      } catch (error) { return { id: good.id, error: error.message }; }
    })));
    if (i + 4 < goods.length) await pause(1000);
  }
  return result;
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
    const page = await requestJson(url, { headers });
    goods.push(...page.goods);
    if (page.next_cursor && page.next_cursor <= cursor) throw new Error('Invalid pagination');
    cursor = page.next_cursor;
  } while (cursor);
  let success = 0, failed = 0, consecutiveFailed = 0;
  for (let i = 0; i < goods.length; i += 20) {
    const results = await getPrices(goods.slice(i, i + 20));
    const errors = results.filter(g => g.error);
    await requestJson(new URL('/internal/prices', base), { method: 'POST', headers,
      body: JSON.stringify({ run_id: runId, goods: results }) });
    success += results.length - errors.length;
    failed += errors.length;
    console.log(JSON.stringify({ processed: i + results.length, total: goods.length, success, failed,
      errors: errors.map(g => ({ id: g.id, error: g.error })) }));
    consecutiveFailed = errors.length === results.length ? consecutiveFailed + 1 : 0;
    // Stop quickly when the entire API is unavailable; retain all previous values.
    if (consecutiveFailed >= 3) throw new Error('Three entire batches failed; stopping until next run');
    await pause(1000);
  }
  if (failed) process.exitCode = 1;
}

if (process.argv[1] && import.meta.url === pathToFileURL(process.argv[1]).href) {
  main().catch(error => { console.error(error.message); process.exitCode = 1; });
}
