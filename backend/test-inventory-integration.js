// Against the isolated local server; no actual station inventory is modified.
const assert=require('node:assert/strict');
const base='http://127.0.0.1:5008/api';
async function request(path,{token,data}={}) {
  const response=await fetch(base+path,{method:data?'POST':'GET',headers:{'Content-Type':'application/json',...(token?{Authorization:`Bearer ${token}`}:{})},...(data?{body:JSON.stringify(data)}:{})});
  return {status:response.status,body:await response.json()};
}
async function main(){
  assert.equal((await request('/inventory-predictions/config')).status,401);
  const manager=await request('/auth/login',{data:{email:'manager@servicecenter.dev',password:'Manager123!'}});assert.equal(manager.status,200);
  const token=manager.body.token;
  const cashier=await request('/auth/login',{data:{email:'cashier@servicecenter.dev',password:'Cashier123!'}});
  assert.equal((await request('/inventory-predictions/config',{token:cashier.body.token})).status,403);
  const config=await request('/inventory-predictions/config',{token});assert.equal(config.status,200);assert.equal(config.body.items.length,20);
  const stocks=await request('/stocks',{token});const stock=stocks.body.stocks.find(s=>s.forecastItemId==='EO020');assert.ok(stock);
  const payload={stock_id:stock.id,item_id:'EO020',start_date:'2027-04-05',end_date:'2027-04-20',stock_qty:stock.quantity};
  const result=await request('/inventory-predictions/forecast',{token,data:payload});assert.equal(result.status,200,JSON.stringify(result.body));assert.equal(result.body.daily.length,16);assert.equal(result.body.daily.at(-1).date,'2027-04-20');
  assert.equal((await request('/inventory-predictions/forecast',{token,data:{...payload,item_id:'OF-A'}})).status,422);
  assert.equal((await request('/inventory-predictions/forecast',{token,data:{...payload,stock_qty:-1}})).status,422);
  const after=await request('/stocks',{token});assert.deepEqual(after.body.stocks,stocks.body.stocks);
  console.log('PASS: authenticated dashboard API, manager access, cashier denial, live stock mapping/unit contract, date-selected model result, invalid requests and unchanged inventory.');
}
main().catch(e=>{console.error(e);process.exit(1);});
