import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { Miniflare, convertV4MiniflareOptions } from 'miniflare';

test('the real Workers HTMLRewriter parses both momo metadata formats', async t => {
  const parser = readFileSync(new URL('../src/momo.js', import.meta.url), 'utf8');
  const runtime = new Miniflare(convertV4MiniflareOptions({
    name: 'parser-test',
    modules: true,
    compatibilityDate: '2026-11-01',
    script: `${parser}\nexport default { async fetch(request) {
      const html = await request.text();
      return Response.json(await fetchProduct('123', async () => new Response(html)));
    } };`,
  }));
  t.after(() => runtime.dispose());
  const fixtures = [
    `<meta property="og:title" content="商品 &amp; 特價"><meta property="product:price:amount" content="1,234"><meta property="product:availability" content="in stock">`,
    `<script type="application/ld+json">{"@context":"https://schema.org","@type":"Product","name":"商品 & 特價","offers":{"price":1234,"availability":"https://schema.org/InStock"}}</script>`,
    `<script type="application/ld+json">{"@graph":[{"@type":"Product","name":"商品 & 特價","offers":[{"price":1234,"availability":"https://schema.org/InStock"}]}]}</script>`,
  ];
  for (const html of fixtures) {
    const response = await runtime.dispatchFetch('https://local.test/', { method: 'POST', body: html });
    assert.equal(response.status, 200);
    assert.deepEqual(await response.json(), { id: '123', name: '商品 & 特價', price: 1234, stock_state: 1 });
  }
});
