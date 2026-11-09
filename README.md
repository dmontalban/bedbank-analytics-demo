Bedbank analytics demo

A portfolio project by David Montalbán Salar (LinkedIn). Interactive demo: davidprojectsportfolio.netlify.app

All data is synthetic. The company is fictional (a B2B accommodation wholesaler). No real company or client data is used.

What is this?

A small, end-to-end analytics project that answers two business questions:

Why did revenue change?
Where will we end the year versus budget?
What it does
Creates the data. About 426,000 fake bookings over 34 months (Jan 2024 to Oct 2026), with some deliberate mess: duplicates, inconsistent market codes and test bookings.
Cleans and checks it with dbt. 17 models and 71 automated tests. A data-quality log shows how many rows each rule fixed, so no row is lost silently.
Explains the revenue change. A "bridge" splits the change into four causes: volume, average booking value, mix and take rate.
Forecasts. Three methods are compared on past data, the best one is used to project the rest of the year, and a simple scenario tool shows what would move the number.
Main results (last 12 months vs the same period a year earlier)
	
Revenue	+4.4%
Volume	+€0.37M
Price (average booking value)	+€0.38M
Mix	-€0.15M
Take rate	-€0.14M

Revenue grew, but mix and a lower take rate gave back part of the growth. That is the point of the bridge: growth alone does not tell the whole story.

Forecast: Holt-Winters had a 1.8% average error three months ahead, against 4.1% for the simple "same month last year" benchmark. FY2026 lands about 3.4% below budget.

Files
File	What it is
gen_data.py	Generates the synthetic data
load_raw.py	Loads it into a local database (DuckDB)
dbt_project/	The dbt models and tests (cleaning, KPIs, bridge)
forecast.py	Forecast, backtest and scenarios
export_site_data.py	Exports the results used by the website
out/	The exported results (JSON)
Run it
bash
bash run_all.sh

Needs Python 3.11+. Everything runs locally and is free.

Limits

The data is synthetic, so the findings demonstrate the method, not a real market. 34 months is a short history for a forecast.

MIT License.
