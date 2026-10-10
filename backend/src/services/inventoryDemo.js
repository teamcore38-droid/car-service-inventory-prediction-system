const fs=require('node:fs');
const path=require('node:path');
const Stock=require('../models/Stock');
async function seedInventoryDemo() {
  if (process.env.SEED_INVENTORY_DEMO!=='1' || await Stock.countDocuments()) return;
  const items=JSON.parse(fs.readFileSync(path.resolve(__dirname,'../../../inventory-ml/data/demo_stock.json'),'utf8'));
  await Stock.insertMany(items);
  console.log('Seeded 20 clearly marked simulation inventory items in the isolated local database.');
}
module.exports={seedInventoryDemo};
