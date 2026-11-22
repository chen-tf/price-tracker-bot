import { readPrices } from './sync.js';
import { allowedFetch, parseLink } from './links.js';
export { parseLink, productUrl } from './links.js';
const PRODUCT_HOSTS = new Set(['m.momoshop.com.tw', 'www.momoshop.com.tw']);

export async function fetchProduct(input, fetcher = fetch, env) {
  input = String(input).replace(/\s+\/add$/, '');
  let id;
  if (/^\d+$/.test(input)) id = input;
  else {
    let url = parseLink(input);
    if (url.hostname === 'momo.dm') {
      const resolved = await allowedFetch(url, fetcher);
      url = resolved.url;
      await resolved.response?.body?.cancel();
    }
    if (!PRODUCT_HOSTS.has(url.hostname)) throw new Error('分享連結未指向 momo 商品。');
    id = url.searchParams.get('i_code') || url.pathname.match(/^\/product\/(\d+)\/?$/)?.[1];
    if (!id || !/^\d+$/.test(id)) throw new Error('商品網址缺少 i_code。');
  }
  {
    const known = env?.DB ? await env.DB.prepare('SELECT source_id FROM good_info WHERE id = ?').bind(id).first() : null;
    const [good] = await readPrices([{ id, product_id: known?.source_id || id }], env, fetcher);
    if (good.unavailable) throw new Error('momo 目前查無這件商品，請確認網址或稍後重試。');
    if (good.error) throw new Error('momo 商品資料暫時無法讀取，請稍後重試。');
    if (typeof good.name !== 'string' || !good.name.trim() || !Number.isSafeInteger(good.price) || good.price <= 0 || ![0, 1].includes(good.stock_state)) throw new Error('momo 商品資料不完整。');
    return { id, name: good.name, price: good.price, stock_state: good.stock_state, source_id: good.source_id };
  }
}
