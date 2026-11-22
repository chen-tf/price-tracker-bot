import { productUrl } from './links.js';

const PAGE_SIZE = 5;
const escape = text => String(text).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
const money = value => `$${String(value).replace(/\B(?=(\d{3})+(?!\d))/g, ',')}`;
const shorten = (text, length) => {
  const chars = Array.from(text);
  return chars.length > length ? `${chars.slice(0, length - 1).join('')}…` : text;
};

function title(name) {
  return shorten(String(name).replace(/(?:[☆★]+\s*)?限時加碼贈[\s\S]*$/, '').replace(/[☆★]+/g, ' ').replace(/\s+/g, ' ').trim(), 60);
}

function checkedAt(timestamp) {
  if (!timestamp) return '尚無成功查價時間';
  // A fixed UTC+8 offset avoids loading locale data on Workers Free.
  const date = new Date(timestamp * 1000 + 8 * 3600000);
  const pad = n => String(n).padStart(2, '0');
  return `${date.getUTCFullYear()}/${pad(date.getUTCMonth() + 1)}/${pad(date.getUTCDate())} ${pad(date.getUTCHours())}:${pad(date.getUTCMinutes())}（台灣）`;
}

function priceLines(good) {
  const baseline = `加入時 ${money(good.original_price)}`;
  if (good.last_error === 'product_unavailable') return `⚠️ 目前查無商品\n最後紀錄 ${money(good.price)} · ${baseline}`;
  const diff = good.original_price - good.price;
  const change = diff > 0 ? ` · 📉 降 ${money(diff)}` : diff < 0 ? ` · 📈 漲 ${money(-diff)}` : ' · 價格持平';
  const status = good.last_error ? '\n⚠️ 最近查價失敗，顯示最後紀錄' : good.stock_state === 0 ? '\n目前缺貨' : good.stock_state === 2 ? '\n庫存狀態未知' : '';
  return `<b>${money(good.price)}</b> · ${baseline}${change}${status}`;
}

export const backToList = page => ({ inline_keyboard: [[{ text: '返回清單', callback_data: `page:${page}` }]] });

export function listPage(goods, requestedPage = 0) {
  if (!goods.length) return { text: '目前沒有追蹤商品。', reply_markup: { inline_keyboard: [] } };
  const pages = Math.ceil(goods.length / PAGE_SIZE);
  const page = Math.max(0, Math.min(requestedPage, pages - 1));
  const visible = goods.slice(page * PAGE_SIZE, (page + 1) * PAGE_SIZE);
  const items = visible.map((good, i) => `${page * PAGE_SIZE + i + 1}. <a href="${productUrl(good.id)}">${escape(title(good.name))}</a>\n${priceLines(good)}\n最後成功查價：${checkedAt(good.last_success)}`);
  const keyboard = visible.map((good, i) => [{ text: `${page * PAGE_SIZE + i + 1}. ${shorten(title(good.name), 28)} · 詳情`, callback_data: `detail:${good.id}:${page}` }]);
  const navigation = [];
  if (page > 0) navigation.push({ text: '← 上一頁', callback_data: `page:${page - 1}` });
  if (page < pages - 1) navigation.push({ text: '下一頁 →', callback_data: `page:${page + 1}` });
  if (navigation.length) keyboard.push(navigation);
  return { text: `<b>我的追蹤</b> · ${goods.length} 件 · 第 ${page + 1}/${pages} 頁\n\n${items.join('\n\n')}`, parse_mode: 'HTML', reply_markup: { inline_keyboard: keyboard } };
}

export function productDetail(good, page = 0, live = false) {
  return {
    text: `<a href="${productUrl(good.id)}">${escape(shorten(good.name, 500))}</a>\n${priceLines(good)}\n${live ? '即時查價' : '最後成功查價'}：${checkedAt(good.last_success)}`,
    parse_mode: 'HTML',
    reply_markup: { inline_keyboard: [
      [{ text: '立即查價', callback_data: `refresh:${good.id}:${page}` }, { text: '取消追蹤', callback_data: `remove:${good.id}:${page}` }],
      ...backToList(page).inline_keyboard,
    ] },
  };
}
