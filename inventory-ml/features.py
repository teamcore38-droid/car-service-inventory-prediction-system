"""Known-date features; no generated lag history or random forecast noise."""
from pathlib import Path
from datetime import timedelta
import json
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent
HOLIDAYS = json.loads((ROOT/'data/holidays.json').read_text())
NUMERIC = ['planned_open_hours','is_public_holiday','travel_window_proxy',
           'pre_new_year_window','pre_holiday_3d','wet_season_proxy',
           'year_sin','year_cos','halfyear_sin','halfyear_cos']
FEATURES = ['item_id','weekday',*NUMERIC]

class ItemRateRegressor:
    """Regularized item-specific hourly rate; opening hours act as exposure."""
    def fit(self,x,y):
        from sklearn.compose import ColumnTransformer
        from sklearn.preprocessing import OneHotEncoder, StandardScaler
        from sklearn.pipeline import make_pipeline
        from sklearn.linear_model import PoissonRegressor
        self.models={}
        numeric=[c for c in NUMERIC if c!='planned_open_hours']
        for item in x.item_id.unique():
            mask=(x.item_id==item)&(x.planned_open_hours>0)
            pre=ColumnTransformer([('weekday',OneHotEncoder(handle_unknown='ignore',sparse_output=False),['weekday']),('numeric',StandardScaler(),numeric)])
            pipe=make_pipeline(pre,PoissonRegressor(alpha=.03,max_iter=500))
            pipe.fit(x.loc[mask],np.asarray(y)[mask.to_numpy()]/x.loc[mask,'planned_open_hours'])
            self.models[item]=pipe
        return self
    def predict(self,x):
        values=np.zeros(len(x))
        for item,model in self.models.items():
            mask=(x.item_id==item).to_numpy()
            if mask.any():values[mask]=model.predict(x.loc[mask])*x.loc[mask,'planned_open_hours'].to_numpy()
        return values

def features(frame):
    result=frame.copy()
    d=pd.to_datetime(result.date)
    result['weekday']=d.dt.weekday.astype(str)
    phase=2*np.pi*(d.dt.dayofyear-1)/np.where(d.dt.is_leap_year,366,365)
    result['year_sin']=np.sin(phase);result['year_cos']=np.cos(phase)
    result['halfyear_sin']=np.sin(2*phase);result['halfyear_cos']=np.cos(2*phase)
    return result[FEATURES]

def calendar(day, schedule, holiday_hours, overrides):
    iso=day.isoformat(); names=HOLIDAYS.get(str(day.year),{})
    holiday=iso in names
    pre=any((day+timedelta(days=n)).isoformat() in HOLIDAYS.get(str((day+timedelta(days=n)).year),{}) for n in (1,2,3))
    travel=int((day.month==4 and day.day<=21) or (day.month==8 and 10<=day.day<=25) or (day.month==12 and day.day>=15))
    closed_newyear=day.month==4 and day.day in (13,14)
    hours=0.0 if closed_newyear else holiday_hours if holiday else schedule[day.weekday()]
    row=dict(date=iso,planned_open_hours=hours,is_public_holiday=int(holiday),
             holiday_name=names.get(iso,''),travel_window_proxy=travel,
             pre_new_year_window=int(day.month==4 and 5<=day.day<=12),
             pre_holiday_3d=int(pre),wet_season_proxy=int(day.month in (5,6,7,8,9,10,11)),
             calendar_verified=str(day.year) in HOLIDAYS)
    row.update(overrides.get(iso,{}))
    if not row['is_public_holiday']:row['holiday_name']=''
    elif not row['holiday_name']:row['holiday_name']='User holiday assumption'
    return row
