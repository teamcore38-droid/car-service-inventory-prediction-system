# Run the integrated Smart Vehicle system locally

This is the supplied final project with forecasting integrated into **Inventory → Demand forecast**. The blue background, orange buttons, white cards, existing stock table and role navigation are retained. The original ZIP was not changed.

## Quick start on Windows

1. Install **Node.js 22 LTS or newer** and **Python 3.12** (include the Python `py` launcher).
2. Extract the integrated ZIP into a normal writable folder. Keep all project folders together.
3. Double-click **Setup-System.cmd** once to install locked Node dependencies and pinned Python dependencies.
4. Double-click **Start-System.cmd**. Open **http://127.0.0.1:5180**.
5. Sign in with the existing local demonstration account:
   - Manager: `manager@servicecenter.dev` / `Manager123!`
   - Admin: `admin@servicecenter.dev` / `Admin123!`
6. Open **Inventory → Demand forecast**, or use **Forecast** beside a stock item.
7. Select the date range, starting stock and supply assumptions, then **Generate forecast**.

`Start-System.cmd` can also perform missing setup. The first start on another computer downloads MongoDB 7.0.14 from the official MongoDB distribution (approximately 592 MB on Windows); allow several minutes and keep Internet access available. After that, the cached binary is reused. No separate MongoDB installation or Atlas account is required for this local mode.

Use **Status-System.cmd** for readiness and **Stop-System.cmd** to stop this project's process tree. Stocks and other local database records are preserved under `.local-data/mongo`. Keep that folder when moving an existing installation. Do not copy it while MongoDB is running.

PowerShell alternatives:

```powershell
& .\setup.ps1
& .\start.ps1 -OpenBrowser
& .\status.ps1
& .\stop.ps1
```

The dashboard, API, model and database use localhost ports **5180**, **5008**, **8770** and **27028**. Occupied ports cause startup to stop with a clear error instead of silently changing the dashboard target. Logs are in `.runtime`.

## Local data and existing-system integration

The local launcher creates an isolated, persistent MongoDB database named `SmartVehicleInventoryLocal`. It ignores the original ZIP's Atlas connection configuration. It seeds the existing demonstration users/services and **20 explicitly labelled simulated inventory items** when this local stock collection is empty. It does not overwrite existing local inventory.

The original backend routes and mobile source remain present. The launcher runs the admin dashboard, backend, forecast service and database; it does not start the Expo mobile app. The inventory prediction API is protected for **admin and manager** roles.

For an existing configured station database, run the original backend entry point `backend/src/app.js` with your own environment and `INVENTORY_ML_URL=http://127.0.0.1:8770`, start `inventory-ml/service.py`, and point the dashboard's `VITE_API_URL` to your backend `/api`. Do not enable `SEED_INVENTORY_DEMO` for your station database. The added Stock fields are `unit`, `forecastItemId` and `dataOrigin`; existing documents remain valid. The station database was not contacted or migrated during this integration.

## How the forecast works

The earlier weekly model repeatedly fed its own predictions into later weeks. That can flatten the forecast. The integrated model instead predicts **each selected date directly** from known calendar features: weekday, annual season cycles, planned opening hours, public holidays, the days before holidays, and travel/pre-New-Year/wet-season proxies. It uses the underlying **14,000 simulated daily SKU records**, rather than inventing daily points from the 2,000 weekly rows.

The graph contains exactly the requested inclusive date range, from **1 to 366 days per request**. A range in April 2027 produces points in April 2027. The unused dates between the November 2025 history cutoff and the selected start date are neither displayed nor recursively generated. Asking for the same date in two overlapping ranges returns the same expected demand, given the same assumptions. The model does not add random noise for visual realism.

All dates use calendar days in **Asia/Colombo**. Default opening hours are nine hours Monday–Saturday and seven on Sunday, with five on public holidays; 13–14 April are closed unless overridden. These are simulation assumptions, not your station's verified schedule. Change them to your actual schedule.

Official public holiday calendars are bundled for 2024–2027. Later years remain selectable, but the UI warns that their holidays are unknown; supply individual date overrides. Named holidays do not automatically imply the station is closed: the chosen holiday hours control demand exposure. Travel windows and wet-season flags are calendar proxies, not school holiday schedules, weather forecasts or measured traffic.

## What can be customised

- **Inventory part and compatible model item:** map the correct specification/fitment and quantity unit. Unmapped stock requires an explicit mapping before generating a forecast. Quantity conversions are your responsibility: e.g. 10 four-litre bottles mean 40 litres, not 10 litres. New or incompatible SKUs require their own training data.
- **From/to dates:** exact forecast period; must be after recorded history. This is future forecasting, not a fitted reconstruction of observed historical dates.
- **Start stock:** quantity expected at the start of the selected period. A current database snapshot is shown for reference. It is not silently treated as future stock after a year of unmodelled consumption.
- **Outstanding orders and confirmed arrival date/quantity:** all outstanding stock affects reorder suggestions; only dated confirmed arrivals affect the daily balance. The API supports multiple receipt dates even though the simple form shows one arrival.
- **Buffer days:** additional stock coverage. Orders round to the model item's supplier pack size.
- **Demand percentage:** 100% is the fitted expected-demand scenario; 150% is a user assumption of 50% higher demand. This is not new training data.
- **Daily schedule and date overrides:** closures, extra opening hours and individual holiday/travel/wet-season assumptions.

Changed inputs mark old results stale and disable CSV export until rerun. The daily table and CSV include the dates, demand estimates, variation envelope, opening hours, flags, dated receipts and net balance. No forecast changes stock or submits a supplier order.

## Stock calculations

`net balance = start stock + cumulative confirmed receipts − cumulative expected demand`.

A negative balance means a **cumulative demand deficit**, not physically negative inventory. Receipts are assumed available at the start of their scheduled day. The first date this balance becomes negative is shown as the first projected shortage. Outstanding orders without confirmed arrival dates do not cover the daily demand balance.

The order suggestion uses a separate coverage window beginning at the requested start date: **supplier lead time + seven-day review + buffer**. It predicts demand over that window, subtracts start stock and all outstanding orders, clips at zero and rounds up to supplier packs. It is a transparent planning policy, not an ML prediction of an optimal purchase quantity. It does not automatically order enough for an entire year merely because the graph displays a year.

Expected demand for discrete parts may be fractional: an expected mean of 0.7 batteries/day does not mean buying a fraction of a battery. The total planning quantity and suggested purchase are rounded appropriately.

## Evaluation and limits

The training split is chronological: first 70 weeks for fitting, next 15 for validation/model selection, final 15 for locked testing. Candidate models and the baseline are evaluated on identical dates. Selection minimises average per-SKU **daily WAPE**, because this feature serves daily date-range graphs. A weekday hourly baseline remains available in the report for comparison.

The selected Ridge seasonal model has test **daily macro WAPE 90.83%** and **weekly macro WAPE 36.71%**. The weekday baseline's weekly error is **35.88%**, so the new calendar model does **not** demonstrate a weekly accuracy improvement. Engine oil 0W-20 has daily WAPE **29.33%** and MAE **10.03 litres/day**; intermittent parts perform substantially worse. WAPE is error, not an accuracy percentage.

The shaded graph envelope comes from per-item validation residuals. Its pooled locked-test daily coverage is approximately **68.43%**; it is not an advertised 80%/95% confidence interval, a period-total interval or a guarantee for far-future dates. Expected forecasts should usually be smoother than actual transactions. Realistic-looking spikes are not evidence of accuracy.

The data are synthetic. These results do not establish station-level production accuracy. The UI explicitly warns when history is over 90 days old. Future business changes, stockout-constrained sales and user-modified scenarios need actual recorded demand and rolling evaluation. The system cannot guarantee correct demand for a future date.

## Files, retraining and checks

- `inventory-ml/service.py`: direct date-range forecast service and validation.
- `inventory-ml/features.py`: calendar feature contract and cached holiday dates.
- `inventory-ml/train.py`: model comparisons, chronological evaluation and final refit.
- `inventory-ml/artifacts/daily_model.joblib`: saved inference model/scales/residuals.
- `inventory-ml/artifacts/evaluation.json`: complete comparisons, dates and per-item errors.
- `inventory-ml/data/`: audited original daily simulation, catalog and official holiday flags.
- `inventory-ml/Inventory_Daily_Training.ipynb`: Colab-compatible retraining notebook.
- `backend/src/routes/inventoryForecastRoutes.js`: authenticated dashboard integration.
- `admin-web/src/components/InventoryForecast.jsx`: integrated UI and CSV export.

To train with actual station records, replace the daily ledger and activity inputs with validated consecutive dates, the same supported SKU IDs and units, actual requested demand including logged unmet requests, and known calendar/opening hours. Do not silently label issued-only sales as unconstrained requested demand. Refit and evaluate using `train.py`; add/revalidate catalog mappings for new SKUs. Current snapshot changes alone do not update the demand history.

```powershell
# Run from the project root after setup.
& .\inventory-ml\.venv\Scripts\python.exe .\inventory-ml\train.py
& .\inventory-ml\.venv\Scripts\python.exe .\inventory-ml\test_forecast.py
# While the isolated local system is running:
node .\backend\test-inventory-integration.js
cd admin-web
npm run build
```

Restart the model service after retraining. Source packages exclude installed dependencies, original `.env` credentials, runtime logs, local database files and generated JWT secrets. Keep your local data separately if you need to transfer an existing installation.

Calendar sources: [CBSL 2024](https://www.cbsl.gov.lk/en/about/about-the-bank/bank-holidays-2024), [2025](https://www.cbsl.gov.lk/en/about/about-the-bank/bank-holidays-2025), [2026](https://www.cbsl.gov.lk/en/about/about-the-bank/bank-holidays-2026), [2027](https://www.cbsl.gov.lk/en/about/about-the-bank/bank-holidays-2027). Forecast evaluation guidance: [scikit-learn time-related features](https://scikit-learn.org/stable/auto_examples/applications/plot_cyclical_feature_engineering.html). Sources checked 10 October 2026.
