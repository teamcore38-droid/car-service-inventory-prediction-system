"""Chronological daily-model selection; locked test is never used for selection."""
import json
import joblib
import numpy as np
import pandas as pd
import sklearn
from sklearn.compose import ColumnTransformer
from sklearn.preprocessing import OneHotEncoder
from sklearn.pipeline import make_pipeline
from sklearn.ensemble import ExtraTreesRegressor, HistGradientBoostingRegressor
from sklearn.linear_model import Ridge
from features import ROOT, FEATURES, NUMERIC, features, ItemRateRegressor

def prepare():
    ledger=pd.read_csv(ROOT/'data/daily_inventory_ledger.csv')
    activity=pd.read_csv(ROOT/'data/daily_service_activity.csv')
    df=ledger[['date','item_id','unit','requested_qty']].merge(activity[['date',*NUMERIC[:6]]],on='date',validate='many_to_one')
    df['date']=pd.to_datetime(df.date)
    if df.duplicated(['date','item_id']).any():raise ValueError('Duplicate demand rows.')
    if df.isna().any().any() or (df.requested_qty<0).any():raise ValueError('Invalid daily history.')
    catalog=pd.read_csv(ROOT/'data/item_catalog.csv').set_index('item_id')
    if not df.item_id.isin(catalog.index).all():raise ValueError('History contains an unknown catalogue item.')
    if not df.unit.eq(df.item_id.map(catalog.unit)).all():raise ValueError('History units must match the item catalogue.')
    if not np.isfinite(df[['requested_qty',*NUMERIC[:6]]].to_numpy(dtype=float)).all():raise ValueError('History contains nonfinite values.')
    for _,g in df.groupby('item_id'):
        if not g.date.sort_values().diff().dropna().eq(pd.Timedelta(days=1)).all():raise ValueError('Nonconsecutive history.')
    return df.sort_values(['date','item_id']).reset_index(drop=True)

def scores(df,p):
    report=df[['date','item_id','unit','requested_qty']].copy();report['prediction']=p
    report['week']=report.date-pd.to_timedelta(report.date.dt.weekday,unit='d')
    daily=[];weekly=[]
    for item,g in report.groupby('item_id'):
        y=g.requested_qty.to_numpy();pred=g.prediction.to_numpy()
        daily.append(dict(item_id=item,unit=g.unit.iloc[0],MAE=float(abs(y-pred).mean()),WAPE=float(abs(y-pred).sum()/max(y.sum(),1e-9))))
        w=g.groupby('week')[['requested_qty','prediction']].sum()
        weekly.append(float(abs(w.requested_qty-w.prediction).sum()/max(w.requested_qty.sum(),1e-9)))
    return {'daily_macro_WAPE':float(np.mean([r['WAPE'] for r in daily])), 'weekly_macro_WAPE':float(np.mean(weekly))},daily

def main():
    df=prepare();dates=sorted(df.date.unique())
    if len(dates)<140:raise ValueError('Provide at least 140 consecutive daily observations per item for chronological evaluation.')
    train_end=(round(len(dates)*.70)//7)*7;valid_end=(round(len(dates)*.85)//7)*7
    train=df[df.date<dates[train_end]];valid=df[(df.date>=dates[train_end])&(df.date<dates[valid_end])];test=df[df.date>=dates[valid_end]]
    scales=train.groupby('item_id').requested_qty.mean().clip(lower=.1).to_dict()
    transform=ColumnTransformer([('category',OneHotEncoder(handle_unknown='error',sparse_output=False),['item_id','weekday']),('numeric','passthrough',NUMERIC)])
    candidates={'Ridge seasonal':Ridge(alpha=20),'Extra Trees calendar':ExtraTreesRegressor(n_estimators=160,max_depth=12,min_samples_leaf=25,random_state=42,n_jobs=2),'Histogram gradient boosting':HistGradientBoostingRegressor(max_iter=140,max_leaf_nodes=15,l2_regularization=20,random_state=42)}
    fitted={};comparison=[]
    for name,model in candidates.items():
        pipe=make_pipeline(transform,model)
        pipe.fit(features(train),train.requested_qty/train.item_id.map(scales))
        p=np.maximum(0,pipe.predict(features(valid))*valid.item_id.map(scales).to_numpy());p[valid.planned_open_hours.to_numpy()==0]=0
        metrics,_=scores(valid,p);comparison.append({'model':name,**metrics});fitted[name]=(pipe,p)
        print(name,metrics,flush=True)
    rate=ItemRateRegressor().fit(features(train),train.requested_qty/train.item_id.map(scales))
    rp=np.maximum(0,rate.predict(features(valid))*valid.item_id.map(scales).to_numpy())
    rm,_=scores(valid,rp);comparison.append({'model':'Item Poisson hourly calendar',**rm});fitted['Item Poisson hourly calendar']=(rate,rp)
    print('Item Poisson hourly calendar',rm,flush=True)
    # Baseline is evaluated on exactly the same dates, with known opening hours.
    rates=train.assign(rate=lambda d:d.requested_qty/d.planned_open_hours.replace(0,np.nan)).groupby(['item_id',train.date.dt.weekday]).rate.mean()
    def baseline(frame):return np.array([rates.loc[(r.item_id,r.date.weekday())]*r.planned_open_hours for r in frame.itertuples()])
    bm,_=scores(valid,baseline(valid));comparison.append({'model':'Weekday hourly mean',**bm})
    chosen=min(comparison,key=lambda r:r['daily_macro_WAPE'])['model']
    if chosen=='Weekday hourly mean':
        # The baseline may win; serving supports it explicitly.
        model=None;validation_prediction=baseline(valid)
    else:model,validation_prediction=fitted[chosen]
    errors=valid.assign(residual=(valid.requested_qty-validation_prediction)/valid.item_id.map(scales)).groupby('item_id').residual
    envelopes={item:[float(g.quantile(.1)),float(g.quantile(.9))] for item,g in errors}
    test_prediction=baseline(test) if model is None else np.maximum(0,model.predict(features(test))*test.item_id.map(scales).to_numpy())
    test_prediction[test.planned_open_hours.to_numpy()==0]=0
    testmetrics,per_item=scores(test,test_prediction);basemetrics,_=scores(test,baseline(test))
    coverage=[]
    for r,p in zip(test.itertuples(),test_prediction):
        lo,hi=envelopes[r.item_id];coverage.append(max(0,p+lo*scales[r.item_id])<=r.requested_qty<=max(0,p+hi*scales[r.item_id]))
    metadata={'model_name':chosen,'method':'direct_daily_calendar','data_origin':'synthetic_inventory_simulation','history_start':str(df.date.min().date()),'history_through':str(df.date.max().date()),'rows':len(df),'features':FEATURES,'versions':{'scikit-learn':sklearn.__version__},'selection':'lowest validation macro daily WAPE for the daily graph; test untouched','train_dates':[str(train.date.min().date()),str(train.date.max().date())],'validation_dates':[str(valid.date.min().date()),str(valid.date.max().date())],'test_dates':[str(test.date.min().date()),str(test.date.max().date())],'validation_comparison':comparison,'locked_test':testmetrics,'locked_test_baseline':basemetrics,'test_daily_envelope_coverage':float(np.mean(coverage)),'per_item':per_item,'limitation':'Synthetic single-station data. Calendar-conditional expected demand, not a guarantee. Multi-year projections and user scenarios are not independently validated.'}
    # Refit selected family on all observations after locking evaluation.
    finalscales=df.groupby('item_id').requested_qty.mean().clip(lower=.1).to_dict()
    if model is not None:model.fit(features(df),df.requested_qty/df.item_id.map(finalscales))
    finalrates=df.assign(rate=lambda d:d.requested_qty/d.planned_open_hours.replace(0,np.nan)).groupby(['item_id',df.date.dt.weekday]).rate.mean().to_dict()
    # Residual envelopes are absolute quantities from validation; do not re-scale them silently.
    absolute_envelopes={i:[lo*scales[i],hi*scales[i]] for i,(lo,hi) in envelopes.items()}
    joblib.dump({'model':model,'scales':finalscales,'rates':finalrates,'envelopes':absolute_envelopes,'metadata':metadata},ROOT/'artifacts/daily_model.joblib')
    (ROOT/'artifacts/evaluation.json').write_text(json.dumps(metadata,indent=2,allow_nan=False))
    pd.DataFrame(per_item).to_csv(ROOT/'artifacts/test_per_item.csv',index=False)
    print('Selected',chosen,'locked test',testmetrics,flush=True)

if __name__=='__main__':main()
