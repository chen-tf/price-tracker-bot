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

async function requestJson(url, options = {}, fetcher = fetch) {
  const response = await fetcher(url, { ...options, signal: AbortSignal.timeout(10000) });
  if (!response.ok) {
    await response.body?.cancel();
    throw new Error(`HTTP ${response.status}`);
  }
  return response.json();
}

async function momo(method, payload, fetcher) {
  const data = await requestJson(api + method, {
    method: 'POST', headers: { 'Content-Type': 'application/json', 'User-Agent': 'price-tracker-bot/1.0' }, body: JSON.stringify(payload),
  }, fetcher);
  if (data.success !== true) throw new Error(data.resultMessage === '查無商品' ? 'product_unavailable' : 'momo API did not return success');
  return data;
}

export function resolveProductCode(id, html) {
  for (const match of html.matchAll(/<script\b[^>]*type=["']application\/ld\+json["'][^>]*>([\s\S]*?)<\/script>/gi)) {
    let data;
    try { data = JSON.parse(match[1]); } catch { continue; }
    const nodes = data['@graph'] || (Array.isArray(data) ? data : [data]);
    for (const product of nodes) {
      if (!['Product', 'ProductGroup'].includes(product['@type']) || !/^\d+$/.test(String(product.sku))) continue;
      const variants = product.hasVariant || [product];
      const matches = variants.some(v => (Array.isArray(v.offers) ? v.offers : [v.offers]).some(o => {
        try { const u = new URL(o.url); return u.origin === 'https://www.momoshop.com.tw' && u.pathname === `/product/${id}`; }
        catch { return false; }
      }));
      if (matches) return String(product.sku);
    }
  }
  throw new Error('missing verified product code');
}

async function readReplacementCode(id, response) {
  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let html = '', bytes = 0;
  try {
    while (bytes < 262144) {
      const { done, value } = await reader.read();
      if (done) break;
      bytes += value.byteLength;
      if (bytes > 262144) break;
      html += decoder.decode(value, { stream: true });
      try { return resolveProductCode(id, html); } catch { /* The JSON-LD script may span chunks. */ }
    }
    throw new Error('missing verified product code');
  } finally { await reader.cancel(); }
}

export async function getPrices(goods, fetcher = fetch, { maxResolutions = 1 } = {}) {
  if (!goods.length) return [];
  const timestamp = Math.floor(Date.now() / 1000);
  let prices;
  try {
    prices = await momo('getInstantGoodsStatus', { columnType: '', priceDescrip: true,
      implementTypes: ['price'], goodsCodes: [...new Set(goods.map(g => g.product_id))], host: 'momoshop' }, fetcher);
  } catch (error) {
    return goods.map(g => ({ id: g.id, error: `price fetch: ${error.message}`, observed_at: timestamp }));
  }
  const result = [];
  let resolutions = 0;
  const stockRequests = new Map();
  const getStock = code => {
    if (!stockRequests.has(code)) stockRequests.set(code, momo('getGoodsRealTimeInfo', {
      goodsCode: code, fsCode: '', hour: '', addressData: {}, categoryCode: '', host: 'momoshop',
    }, fetcher));
    return stockRequests.get(code);
  };
  // Known unavailable items share the price request and need no individual stock request until they return.
  // Bounded concurrency controls the shop load; network waits do not consume Worker CPU time.
  for (let i = 0; i < goods.length; i += 4) {
    result.push(...await Promise.all(goods.slice(i, i + 4).map(async good => {
      try {
        let fresh;
        try { fresh = parsePrice(good.id, prices.rtnGoods?.[good.product_id]); } catch { /* Check live stock before using the product page fallback. */ }
        const entry = prices.rtnGoods?.[good.product_id];
        if (!fresh && good.unavailable && entry?.goodsName === '' && entry.goodsPriceModel?.basePrice?.price === '0') {
          return { id: good.id, unavailable: true, observed_at: timestamp };
        }
        if (!entry) throw new Error('missing batch product data');
        let stock = await getStock(good.product_id);
        let sourceId = good.product_id;
        if (!fresh) {
          if (resolutions >= maxResolutions) throw new Error('product code resolution deferred');
          resolutions++;
          const page = await fetcher(`https://www.momoshop.com.tw/product/${good.product_id}`, {
            headers: { 'User-Agent': 'price-tracker-bot/1.0' }, redirect: 'error', signal: AbortSignal.timeout(10000),
          });
          if (!page.ok) { await page.body?.cancel(); throw new Error(`product page HTTP ${page.status}`); }
          sourceId = await readReplacementCode(good.product_id, page);
          if (sourceId === good.product_id) throw new Error('missing valid price');
          const replacement = await momo('getInstantGoodsStatus', { columnType: '', priceDescrip: true,
            implementTypes: ['price'], goodsCodes: [sourceId], host: 'momoshop' }, fetcher);
          fresh = parsePrice(good.id, replacement.rtnGoods?.[sourceId]);
          stock = await getStock(sourceId);
        }
        return { ...fresh, id: good.id, source_id: sourceId, stock_state: parseStock(stock.rtnGoodsData), observed_at: timestamp };
      } catch (error) { return error.message === 'product_unavailable' ? { id: good.id, unavailable: true, observed_at: timestamp } : { id: good.id, error: error.message, observed_at: timestamp }; }
    })));
  }
  return result;
}
