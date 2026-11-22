export const profiles = [
  ['default', {}],
  ['chrome-user-agent', { 'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/156.0.0.0 Safari/537.36' }],
  ['node-user-agent', { 'User-Agent': 'node' }],
  ['curl-user-agent', { 'User-Agent': 'curl/8.7.1' }],
  ['python-user-agent', { 'User-Agent': 'Python-urllib/3.9' }],
  ['bot-user-agent', { 'User-Agent': 'price-tracker-bot/1.0' }],
  ['version', { version: '999999' }],
  ['accept', { Accept: 'application/json, text/plain, */*' }],
  ['language', { 'Accept-Language': 'zh-TW,zh;q=0.9,en-US;q=0.8' }],
  ['origin', { Origin: 'https://www.momoshop.com.tw' }],
  ['referer', { Referer: 'https://www.momoshop.com.tw/product/4811545' }],
  ['sec-fetch', { 'Sec-Fetch-Site': 'same-origin', 'Sec-Fetch-Mode': 'cors', 'Sec-Fetch-Dest': 'empty' }],
];
export async function matrix() {
  const results = [];
  for (const [profile, extra] of profiles) {
    try {
      const r = await fetch('https://www.momoshop.com.tw/api/moecapp/getInstantGoodsStatus', { method: 'POST',
        headers: { 'Content-Type': 'application/json', ...extra },
        body: JSON.stringify({ columnType: '', priceDescrip: true, implementTypes: ['price'], goodsCodes: ['4811545'], host: 'momoshop' }),
        signal: AbortSignal.timeout(10000) });
      const body = await r.text();
      let valid = false;
      try { const d = JSON.parse(body); valid = d.success === true && !!d.rtnGoods?.['4811545']?.goodsName; } catch {}
      results.push({ profile, status: r.status, valid });
    } catch (e) { results.push({ profile, error: e.message }); }
    await new Promise(resolve => setTimeout(resolve, 250));
  }
  return results;
}
if (typeof process !== 'undefined' && process.argv[1]?.endsWith('header_matrix.mjs')) console.log(JSON.stringify(await matrix()));
