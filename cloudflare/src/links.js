const PRODUCT_HOSTS = new Set(['m.momoshop.com.tw', 'www.momoshop.com.tw']);
const LINK_HOSTS = new Set([...PRODUCT_HOSTS, 'momo.dm']);

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

export async function allowedFetch(url, fetcher) {
  // Validate every redirect before sending a request, including short links.
  for (let redirects = 0; redirects <= 5; redirects++) {
    parseLink(url.href);
    if (PRODUCT_HOSTS.has(url.hostname) && (/^\d+$/.test(url.searchParams.get('i_code') || '') || /^\/product\/\d+\/?$/.test(url.pathname))) return { url };
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

