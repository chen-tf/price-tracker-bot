import { chromium } from 'playwright';
const browser = await chromium.launch({headless:true});
try {
 const page = await browser.newPage({ locale: 'zh-TW' });
 for(const url of ['https://www.momoshop.com.tw/product/4811545','https://m.momoshop.com.tw/goods.momo?i_code=4811545']) {
  try {
   const response=await page.goto(url,{waitUntil:'domcontentloaded',timeout:20000});
   console.log(JSON.stringify({url,status:response.status(),title:await page.title(),meta:await page.locator('meta[property^="product:"],meta[property="og:title"]').evaluateAll(nodes=>nodes.map(n=>[n.getAttribute('property'),n.getAttribute('content')]))}));
   const api=await page.evaluate(async()=>{
    const r=await fetch('/api/moecapp/getInstantGoodsStatus',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({columnType:'',priceDescrip:true,implementTypes:['price'],goodsCodes:['4811545'],host:'momoshop'})});
    return {status:r.status,body:(await r.text()).slice(0,700)};
   });console.log(JSON.stringify({api}));
  }catch(e){console.log(e.message);}
 }
} finally {await browser.close();}
