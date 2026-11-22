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

export async function getPrices(goods, fetcher = fetch) {
  const timestamp = Math.floor(Date.now() / 1000);
  let prices;
  try {
    prices = await momo('getInstantGoodsStatus', { columnType: '', priceDescrip: true,
      implementTypes: ['price'], goodsCodes: [...new Set(goods.map(g => g.product_id))], host: 'momoshop' }, fetcher);
  } catch (error) {
    return goods.map(g => ({ id: g.id, error: `price fetch: ${error.message}` }));
  }
  const result = [];
  // Four requests per second at most, without overwhelming the public shop API.
  for (let i = 0; i < goods.length; i += 4) {
    result.push(...await Promise.all(goods.slice(i, i + 4).map(async good => {
      try {
        const stock = await momo('getGoodsRealTimeInfo', { goodsCode: good.product_id,
          fsCode: '', hour: '', addressData: {}, categoryCode: '', host: 'momoshop' }, fetcher);
        const fresh = parsePrice(good.id, prices.rtnGoods?.[good.product_id]);
        return { ...fresh, stock_state: parseStock(stock.rtnGoodsData), observed_at: timestamp };
      } catch (error) { return error.message === 'product_unavailable' ? { id: good.id, unavailable: true, observed_at: timestamp } : { id: good.id, error: error.message }; }
    })));
    if (i + 4 < goods.length) await pause(1000);
  }
  return result;
}

