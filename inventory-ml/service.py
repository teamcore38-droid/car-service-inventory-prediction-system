"""Local daily calendar inference used through the authenticated Node API."""
from datetime import date, timedelta
from pathlib import Path
import math
import json
import joblib
import numpy as np
import pandas as pd
import sklearn
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field, ConfigDict, model_validator
import uvicorn
from features import ROOT, HOLIDAYS, features, calendar

class Receipt(BaseModel):
    model_config=ConfigDict(extra='forbid')
    date:date
    quantity:float=Field(ge=0,allow_inf_nan=False)

class Override(BaseModel):
    model_config=ConfigDict(extra='forbid')
    date:date
    planned_open_hours:float|None=Field(default=None,ge=0,le=24,allow_inf_nan=False)
    is_public_holiday:int|None=Field(default=None,ge=0,le=1)
    travel_window_proxy:int|None=Field(default=None,ge=0,le=1)
    wet_season_proxy:int|None=Field(default=None,ge=0,le=1)

class ForecastRequest(BaseModel):
    model_config=ConfigDict(extra='forbid')
    item_id:str
    start_date:date
    end_date:date
    stock_qty:float=Field(ge=0,allow_inf_nan=False)
    on_order_qty:float=Field(default=0,ge=0,allow_inf_nan=False)
    buffer_days:int=Field(default=3,ge=0,le=30)
    demand_factor:float=Field(default=1,ge=0,le=3,allow_inf_nan=False)
    opening_hours:list[float]=Field(default_factory=lambda:[9,9,9,9,9,9,7],min_length=7,max_length=7)
    holiday_hours:float=Field(default=5,ge=0,le=24,allow_inf_nan=False)
    receipts:list[Receipt]=Field(default_factory=list,max_length=50)
    overrides:list[Override]=Field(default_factory=list,max_length=366)
    @model_validator(mode='after')
    def validate_range(self):
        if not 0 <= (self.end_date-self.start_date).days <=365:raise ValueError('Choose a range of 1 to 366 days.')
        if self.end_date.year>2100:raise ValueError('Choose a year no later than 2100.')
        if any(not math.isfinite(h) or not 0<=h<=24 for h in self.opening_hours):raise ValueError('Daily opening hours must be between 0 and 24.')
        if sum(r.quantity for r in self.receipts)>self.on_order_qty+1e-8:raise ValueError('Confirmed receipts cannot exceed outstanding orders.')
        if any(not self.start_date<=r.date<=self.end_date for r in self.receipts):raise ValueError('Receipt dates must fall inside the forecast range.')
        if any(not self.start_date<=r.date<=self.end_date for r in self.overrides):raise ValueError('Override dates must fall inside the forecast range.')
        if len({r.date for r in self.overrides})!=len(self.overrides):raise ValueError('Use one override per date.')
        return self

class Forecaster:
    def __init__(self):
        self.bundle=joblib.load(ROOT/'artifacts/daily_model.joblib')
        self.metadata=self.bundle['metadata']
        if sklearn.__version__!=self.metadata['versions']['scikit-learn']:raise ValueError('Install the pinned scikit-learn version.')
        self.catalog=pd.read_csv(ROOT/'data/item_catalog.csv').set_index('item_id')
        self.history=pd.read_csv(ROOT/'data/daily_inventory_ledger.csv')
        self.cutoff=date.fromisoformat(self.metadata['history_through'])

    def predict_frame(self,item,rows,factor):
        frame=pd.DataFrame(rows).assign(item_id=item)
        model=self.bundle['model']
        if model is None:
            predicted=np.array([self.bundle['rates'][(item,date.fromisoformat(r['date']).weekday())]*r['planned_open_hours'] for r in rows])
        else:predicted=np.maximum(0,model.predict(features(frame))*self.bundle['scales'][item])
        predicted=np.where(frame.planned_open_hours==0,0,predicted)*factor
        return predicted

    def config(self):
        return dict(items=self.catalog.reset_index().to_dict('records'),history_through=self.cutoff.isoformat(),
                    min_date=(self.cutoff+timedelta(days=1)).isoformat(),calendar_years=sorted(HOLIDAYS),
                    default_opening_hours=[9,9,9,9,9,9,7],metadata=self.metadata,
                    calendar_sources=[f'https://www.cbsl.gov.lk/en/about/about-the-bank/bank-holidays-{y}' for y in HOLIDAYS])

    def forecast(self,request):
        if request.item_id not in self.catalog.index:raise ValueError('Unsupported model SKU. Map to a compatible trained item or retrain.')
        if request.start_date<=self.cutoff:raise ValueError(f'Forecast dates must be after recorded history ({self.cutoff}).')
        item=request.item_id;info=self.catalog.loc[item];discrete=info.unit!='litre'
        if discrete and any(q%1 for q in [request.stock_qty,request.on_order_qty,*[r.quantity for r in request.receipts]]):raise ValueError('Stock and receipts must be whole units for this item.')
        overrides={o.date.isoformat():o.model_dump(exclude={'date'},exclude_none=True) for o in request.overrides}
        days=[request.start_date+timedelta(days=n) for n in range((request.end_date-request.start_date).days+1)]
        rows=[calendar(d,request.opening_hours,request.holiday_hours,overrides) for d in days]
        values=self.predict_frame(item,rows,request.demand_factor)
        residual_low,residual_high=self.bundle['envelopes'][item]
        receipt_map={}
        for r in request.receipts:receipt_map[r.date.isoformat()]=receipt_map.get(r.date.isoformat(),0)+r.quantity
        balance=request.stock_qty;records=[]
        for row,value in zip(rows,values):
            received=receipt_map.get(row['date'],0);balance+=received-float(value)
            open_day=row['planned_open_hours']>0
            records.append({**row,'predicted_qty':round(float(value),4),
                'lower_qty':round(max(0,float(value)+residual_low*request.demand_factor),4) if open_day else 0,
                'upper_qty':round(max(0,float(value)+residual_high*request.demand_factor),4) if open_day else 0,
                'confirmed_receipt_qty':received,'net_balance_qty':round(balance,4),'source':'forecast'})
        # Reorder policy uses a delivery + 7-day review + buffer coverage window,
        # independent of how many days the chart displays.
        coverage_days=int(info.normal_lead_time_days)+7+request.buffer_days
        cover_rows=[calendar(request.start_date+timedelta(days=n),request.opening_hours,request.holiday_hours,overrides) for n in range(coverage_days)]
        cover=float(self.predict_frame(item,cover_rows,request.demand_factor).sum())
        pack=float(info.order_pack_qty)
        order=math.ceil(max(0,cover-request.stock_qty-request.on_order_qty)/pack)*pack
        first_shortage=next((r['date'] for r in records if r['net_balance_qty']<0),None)
        total=float(values.sum());warnings=[]
        if (request.start_date-self.cutoff).days>90:warnings.append('History is more than 90 days behind this forecast. This is a calendar scenario, not a forecast updated with current station demand.')
        unknown=sorted({str(d.year) for d in days if str(d.year) not in HOLIDAYS})
        if unknown:warnings.append(f'Official holiday calendar missing for {", ".join(unknown)}. Enter date overrides; unknown holidays are assumed absent.')
        if request.demand_factor!=1:warnings.append('Demand multiplier is a user scenario; evaluation metrics apply to the original scenario only.')
        return dict(item_id=item,item_name=info.item_name,unit=info.unit,start_date=request.start_date.isoformat(),end_date=request.end_date.isoformat(),
                    days=len(days),daily=records,total_expected_demand=round(total,2),planning_demand_qty=math.ceil(total) if discrete else round(total,2),
                    recommended_order_qty=order,order_pack_qty=pack,normal_lead_time_days=int(info.normal_lead_time_days),
                    first_shortage_date=first_shortage,max_cumulative_shortfall=round(max(0,-min(r['net_balance_qty'] for r in records)),2),
                    coverage_days=coverage_days,coverage_expected_demand=round(cover,2),warnings=warnings,
                    assumptions=request.model_dump(mode='json'),model_name=self.metadata['model_name'],history_through=self.cutoff.isoformat(),
                    data_origin=self.metadata['data_origin'],method='direct_daily_calendar',
                    note='Expected demand changes with known calendar and user inputs. No random noise is added. Net balance assumes unmet demand is a cumulative deficit. Receipts arrive at the start of their date. The shaded range is a validation-residual daily envelope, not guaranteed coverage or a period-total interval.')

app=FastAPI(title='Integrated inventory forecast service')
engine=None
def active():
    global engine
    if engine is None:engine=Forecaster()
    return engine

@app.get('/health')
def health():return {'status':'ready','service':'inventory-daily','model':active().metadata['model_name']}
@app.get('/config')
def config():return active().config()
@app.post('/forecast')
def forecast(request:ForecastRequest):
    try:return active().forecast(request)
    except ValueError as e:raise HTTPException(422,detail=str(e)) from e
@app.get('/history/{item}')
def history(item:str):
    p=active()
    if item not in p.catalog.index:raise HTTPException(404,detail='Unsupported item.')
    return p.history[p.history.item_id==item][['date','requested_qty','issued_qty']].tail(28).to_dict('records')
if __name__=='__main__':uvicorn.run(app,host='127.0.0.1',port=8770)
