const PRODUCT_HOSTS = new Set(['m.momoshop.com.tw', 'www.momoshop.com.tw']);
const LINK_HOSTS = new Set([...PRODUCT_HOSTS, 'momo.dm']);

function decodeAttribute(value) {
  const named = { amp: '&', lt: '<', gt: '>', quot: '"', apos: "'", nbsp: ' ' };
  return value?.replace(/&(#x[\da-f]+|#\d+|amp|lt|gt|quot|apos|nbsp);/gi, (entity, code) => {
    if (!code.startsWith('#')) return named[code.toLowerCase()];
    const point = code[1].toLowerCase() === 'x' ? parseInt(code.slice(2), 16) : parseInt(code.slice(1), 10);
    return point > 0 && point <= 0x10ffff && !(point >= 0xd800 && point <= 0xdfff) ? String.fromCodePoint(point) : entity;
  });
}

export function productUrl(id) {
  const canonical = String(id).replace(/\s+\/add$/, '');
  return `https://www.momoshop.com.tw/product/${encodeURIComponent(canonical)}`;
}

export function parseLink(text) {
  const match = text.match(/https:\/\/[^\s<>]+/i);
  if (!match) throw new Error('請提供 momo 商品網址。');
  let url;
  try { url = new URL(match[0]); } catch { throw new Error('商品網址格式錯誤。'); }
  if (url.protocol !== 'https:' || !LINK_HOSTS.has(url.hostname) || url.port || url.username || url.password) {
    throw new Error('只接受 momo 商品網址或 momo.dm 分享連結。');
  }
  return url;
}

export function parseMetadata(id, meta, jsonProducts = []) {
  const product = jsonProducts.find(p => p && (p['@type'] === 'Product' || p['@type']?.includes?.('Product')));
  const offer = Array.isArray(product?.offers) ? product.offers[0] : product?.offers;
  const name = (meta['og:title'] || product?.name || '').trim();
  const rawPrice = String(meta['product:price:amount'] ?? offer?.price ?? '').replace(/,/g, '').trim();
  const price = Number(rawPrice);
  const rawAvailability = String(meta['product:availability'] || offer?.availability || '').toLowerCase();
  const availability = rawAvailability.split('/').pop();
  const stocks = { 'in stock': 1, instock: 1, 'out of stock': 0, outofstock: 0, soldout: 0, discontinued: 0 };
  if (!name || !/^\d+(\.0+)?$/.test(rawPrice) || !Number.isSafeInteger(price) || price <= 0 || !(availability in stocks)) {
    throw new Error('momo 商品資料不完整，保留原價格並稍後重試。');
  }
  return { id: String(id), name: name.slice(0, 500), price, stock_state: stocks[availability] };
}

async function allowedFetch(url, fetcher) {
  // Validate every redirect before sending a request, including short links.
  for (let redirects = 0; redirects <= 5; redirects++) {
    parseLink(url.href);
    const response = await fetcher(url.href, {
      redirect: 'manual', signal: AbortSignal.timeout(12000),
      headers: { 'User-Agent': 'price-tracker-bot/1.0', 'Accept-Language': 'zh-TW,zh;q=0.9' },
    });
    if (response.status >= 300 && response.status < 400 && response.headers.has('location')) {
      await response.body?.cancel();
      url = new URL(response.headers.get('location'), url);
      continue;
    }
    if (!response.ok) {
      await response.body?.cancel();
      throw new Error(`momo 回傳 HTTP ${response.status}，保留原價格並稍後重試。`);
    }
    return { response, url };
  }
  throw new Error('momo 分享網址轉址次數過多。');
}

export async function fetchProduct(input, fetcher = fetch, env) {
  input = String(input).replace(/\s+\/add$/, '');
  let id;
  if (/^\d+$/.test(input)) id = input;
  else {
    let url = parseLink(input);
    if (url.hostname === 'momo.dm') {
      const resolved = await allowedFetch(url, fetcher);
      url = resolved.url;
      await resolved.response.body?.cancel();
    }
    if (!PRODUCT_HOSTS.has(url.hostname)) throw new Error('分享連結未指向 momo 商品。');
    id = url.searchParams.get('i_code') || url.pathname.match(/^\/product\/(\d+)\/?$/)?.[1];
    if (!id || !/^\d+$/.test(id)) throw new Error('商品網址缺少 i_code。');
  }
  if (env?.BROWSER) return fetchRenderedProduct(id, env);
  const { response } = await allowedFetch(new URL(productUrl(id)), fetcher);
  const meta = {};
  const products = [];
  let script = '';
  const parser = new HTMLRewriter()
    .on('meta', { element(e) { meta[e.getAttribute('property') || e.getAttribute('name')] = decodeAttribute(e.getAttribute('content')); } })
    .on('script[type="application/ld+json"]', {
      element() { script = ''; },
      text(chunk) {
        script += chunk.text;
        if (script.length > 100000) throw new Error('momo 結構化資料過大。');
        if (chunk.lastInTextNode) {
          try {
            const parsed = JSON.parse(script);
            const objects = Array.isArray(parsed) ? parsed : [parsed];
            products.push(...objects.flatMap(p => p?.['@graph'] || [p]));
          } catch { /* Other valid metadata may still identify the product. */ }
          script = '';
        }
      },
    });
  // Stream the HTML to avoid buffering a potentially large product page.
  await parser.transform(response).body.pipeTo(new WritableStream({ write() {} }));
  return parseMetadata(id, meta, products);
}

export async function fetchRenderedProduct(id, env) {
  const day = new Date().toISOString().slice(0, 10);
  // Reserve more than the 10s navigation timeout before spending any browser time.
  // Keep a one-minute margin below the account's 10 minute Free daily allowance.
  const reservation = 15000;
  await env.DB.prepare('INSERT OR IGNORE INTO browser_budget(day) VALUES (?)').bind(day).run();
  const budget = await env.DB.prepare(`UPDATE browser_budget SET used_ms = used_ms + ?
    WHERE day = ? AND used_ms <= ? RETURNING used_ms`).bind(reservation, day, 540000 - reservation).first();
  if (!budget) {
    const error = new Error('今日免費抓價額度已用完，將於明日繼續查價。');
    error.retryAt = Math.floor(Date.parse(`${day}T00:00:00Z`) / 1000) + 86400;
    throw error;
  }
  let response;
  try {
    response = await env.BROWSER.quickAction('scrape', {
      url: productUrl(id),
      elements: [{ selector: 'meta[property="og:title"],meta[name="og:title"],meta[property^="product:"],meta[name^="product:"]' }],
      gotoOptions: { waitUntil: 'domcontentloaded', timeout: 10000 },
    });
    const result = await response.json();
    if (!response.ok || result.success === false) throw new Error('momo 免費瀏覽器抓價暫時失敗，保留原價格並稍後重試。');
    const meta = {};
    const groups = result.result || result;
    if (!Array.isArray(groups)) throw new Error('momo 瀏覽器資料格式不符。');
    for (const group of groups) {
      for (const element of group.results || []) {
        const attributes = Object.fromEntries((element.attributes || []).map(a => [a.name, a.value]));
        meta[attributes.property || attributes.name] = attributes.content;
      }
    }
    return parseMetadata(id, meta);
  } finally {
    const used = Number(response?.headers.get('X-Browser-Ms-Used'));
    // Missing usage headers keep the full reservation; unknown usage never becomes free credit.
    if (Number.isFinite(used) && used > 0) {
      await env.DB.prepare('UPDATE browser_budget SET used_ms = MAX(0, used_ms + ?) WHERE day = ?')
        .bind(Math.ceil(used) - reservation, day).run();
    }
  }
}
