import { test } from 'node:test';
import assert from 'node:assert/strict';
import { listPage, productDetail } from '../src/presentation.js';

const good = overrides => ({ id: '8013804', name: '【Philips 飛利浦】咖啡機(EP2220) ☆☆☆限時加碼贈咖啡豆', price: 11900,
  original_price: 16900, stock_state: 1, last_success: 1735689600, ...overrides });

test('compact list links product titles, formats price changes and labels Taiwan observation time', () => {
  const page = listPage([good()]);
  assert.equal(page.parse_mode, 'HTML');
  assert.match(page.text, /<a href="https:\/\/www.momoshop.com.tw\/product\/8013804">【Philips 飛利浦】咖啡機\(EP2220\)<\/a>/);
  assert.match(page.text, /<b>\$11,900<\/b> · 加入時 \$16,900 · 📉 降 \$5,000/);
  assert.match(page.text, /最後成功查價：2025\/01\/01 08:00（台灣）/);
  assert.doesNotMatch(page.text, /加碼贈|☆☆☆/);
  assert.equal(page.reply_markup.inline_keyboard[0][0].callback_data, 'detail:8013804:0');
});

test('unavailable and failed prices clearly remain historical observations', () => {
  const unavailable = listPage([good({ last_error: 'product_unavailable' })]).text;
  assert.match(unavailable, /⚠️ 目前查無商品\n最後紀錄 \$11,900/);
  assert.doesNotMatch(unavailable, /📉|📈/);
  assert.match(listPage([good({ last_error: 'timeout' })]).text, /最近查價失敗，顯示最後紀錄/);
  assert.match(listPage([good({ last_success: null, stock_state: 0 })]).text, /目前缺貨\n最後成功查價：尚無成功查價時間/);
  assert.match(listPage([good({ stock_state: 2 })]).text, /庫存狀態未知/);
});

test('list pages contain five goods, clamp removed pages, and navigate both ways', () => {
  const goods = Array.from({ length: 11 }, (_, i) => good({ id: String(i + 1), name: `商品${i + 1}` }));
  const first = listPage(goods);
  assert.match(first.text, /11 件 · 第 1\/3 頁/);
  assert.equal((first.text.match(/<a /g) || []).length, 5);
  assert.deepEqual(first.reply_markup.inline_keyboard.at(-1), [{ text: '下一頁 →', callback_data: 'page:1' }]);
  const middle = listPage(goods, 1);
  assert.match(middle.text, /6\. <a /);
  assert.deepEqual(middle.reply_markup.inline_keyboard.at(-1).map(b => b.callback_data), ['page:0', 'page:2']);
  assert.match(listPage(goods, 999999).text, /第 3\/3 頁/);
  assert.match(listPage(goods.slice(0, 4), 2).text, /第 1\/1 頁/);
  assert.deepEqual(listPage([]).reply_markup.inline_keyboard, []);
});

test('HTML, very long titles, and emoji remain safe within Telegram limits', () => {
  const hostile = good({ name: '<b>A&B</b>" 🧋'.repeat(100) });
  const page = listPage(Array.from({ length: 5 }, () => hostile));
  assert.match(page.text, /&lt;b&gt;A&amp;B&lt;\/b&gt;&quot;/);
  assert.doesNotMatch(page.text, /<b>A&B/);
  // Even the escaped payload stays below the limit, before Telegram parses entities.
  assert.ok(page.text.length < 4096);
  assert.ok(productDetail(hostile).text.length < 4096);
  for (const row of page.reply_markup.inline_keyboard) for (const button of row) assert.ok(Buffer.byteLength(button.callback_data) <= 64);
});

test('details preserve the full title and distinguish higher, unchanged and live prices', () => {
  const detail = productDetail(good(), 2);
  assert.match(detail.text, /加碼贈咖啡豆/);
  assert.deepEqual(detail.reply_markup.inline_keyboard[0].map(b => b.callback_data), ['refresh:8013804:2', 'remove:8013804:2']);
  assert.equal(detail.reply_markup.inline_keyboard.at(-1)[0].callback_data, 'page:2');
  assert.match(productDetail(good({ price: 17000 }), 0, true).text, /📈 漲 \$100[\s\S]*即時查價：/);
  assert.match(productDetail(good({ price: 16900 })).text, /價格持平/);
});
