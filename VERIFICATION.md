# Integration verification

Verified locally on Windows on 10 October 2026.

- Production dashboard build passed; Vite retains an existing large-bundle advisory.
- Eight forecast tests passed: exact future range, overlapping date consistency, deterministic results, closures, demand scenarios, stock balance, dated receipts, all catalogue units, pack rounding, calendar warnings and input validation.
- Express integration checks passed: authentication, manager access, cashier rejection, live SKU/unit mapping, future dates, invalid requests and unchanged stock after forecasts.
- Browser checks passed: April 5–20, 2027 generated exactly 16 dates; April 13–14 closures produced zero demand; changing demand from 100% to 120% changed expected total from 576.02 to 691.22 litres. Changed inputs disabled stale CSV export.
- Downloaded browser CSV independently checked for exact dates, zero closure demand and matching totals.
- Mobile viewport 390×844 checked without horizontal document overflow; temporary viewport reset.
- Owned launcher start, stop and restart passed; persistent local stock records survived restart.
- Setup script completed with a new project Python environment and clean Node dependency installation; all forecast tests and API checks passed again using that environment.
- Training data validation passed for 14,000 daily observations. Notebook JSON validated. The training/evaluation scripts ran locally; the notebook has not been executed in Google Colab.

The included dataset is simulated, not measured station demand. Daily macro WAPE is 90.83%; weekly macro WAPE is 36.71%. Intermittent parts are particularly uncertain. These checks verify implementation behavior, not guaranteed future accuracy.
