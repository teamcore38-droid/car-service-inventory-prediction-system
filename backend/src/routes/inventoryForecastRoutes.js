const express = require('express');
const Stock = require('../models/Stock');
const { authenticate, requireRole } = require('../middlewares/authMiddleware');
const router = express.Router();
router.use(authenticate, requireRole('admin', 'manager'));
const base = process.env.INVENTORY_ML_URL || 'http://127.0.0.1:8770';

async function forward(path, options = {}) {
  const response = await fetch(`${base}${path}`, { ...options, signal: AbortSignal.timeout(30000) });
  const body = await response.json();
  if (!response.ok) {
    const detail = typeof body.detail === 'string' ? body.detail : body.detail?.map(e => `${e.loc.slice(1).join('.')}: ${e.msg}`).join('; ');
    const error = new Error(detail || 'Forecast request failed.'); error.status = response.status; throw error;
  }
  return body;
}
function failure(res, error) {
  res.status(error.status || 503).json({error: error.status ? error.message : 'Inventory model service is unavailable. Start all services using Start-System.cmd.'});
}
router.get('/config', async (req,res) => {try {res.json(await forward('/config'));} catch(e) {failure(res,e);}});
router.get('/history/:item', async (req,res) => {try {res.json(await forward(`/history/${encodeURIComponent(req.params.item)}`));} catch(e) {failure(res,e);}});
router.post('/forecast', async (req,res) => {
  try {
    const {stock_id, ...payload} = req.body || {};
    let stock = null;
    if (stock_id) {
      if (!/^[a-f0-9]{24}$/i.test(stock_id)) return res.status(422).json({error:'Invalid inventory record.'});
      stock = await Stock.findById(stock_id);
      if (!stock) return res.status(404).json({error:'Inventory record was not found.'});
      const config = await forward('/config');
      const item = config.items.find(i => i.item_id === payload.item_id);
      if (!item || stock.forecastItemId !== item.item_id || stock.unit !== item.unit) return res.status(422).json({error:'Save a compatible model item mapping and matching quantity unit before forecasting this stock item.'});
    }
    const result = await forward('/forecast',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(payload)});
    result.inventory_record = stock ? {id:stock.id,partNumber:stock.partNumber,quantity:stock.quantity,unit:stock.unit,updatedAt:stock.updatedAt,dataOrigin:stock.dataOrigin} : null;
    result.stock_source = stock ? 'User-entered start stock; inventory snapshot supplied for comparison.' : 'Model demonstration item; user scenario.';
    res.json(result);
  } catch(e) {failure(res,e);}
});
module.exports = router;
