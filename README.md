# Property rental tracking application

This application tracks rental-property operations and investment performance. Django and Django REST Framework provide the backend and typed analytics API; the frontend is a React/TypeScript SPA built with Vite, TanStack Query, Tailwind CSS, shadcn/ui, and Recharts.

## Distinctiveness and Complexity
+ The idea of the project is to bring property portfolio management analytics to the database of properties
+ The data is structured as a comprehensive database consisting of eight models (users, landlord, tenants, property, property funding, transactions, rent history, FX data)
+ The app allows registered user to save own properties and include key information (address, footage, rooms, price, etc.), create tenants and "rent" own properties to tenants. Include revenue inputs (rent received) and costs (utility bills, capex, etc.) into the respective database. And track the economics of each property project: P&L components, charges executed in time, rent outstanding
+ Recharts renders the typed investment dashboard, property valuation history, and tenant rent-performance analytics
+ Instances of the main models (user, property, tenant, transaction) can also be edited or deleted in case of the wrong data present
+ User settings are also included to be able to save user details (username, name, email) and data visual properties (default currency, chart frequency, chart timeline and number of digits shown in tables)
+ The application is multi-currency. Each property has its onw _natural_ currrency. Data representation, however, can be made in any currency (set up in user settings). And home page, summarising all the statistics is shown using single default currency. After the new transaction is entered, special function is run to update FX database to be able to convert currencies
+ For consistency of FX conversions _Bellman-Ford_ algorithm used for shortest path cross-currency conversion using `networkx` library to deal with undirected graphs
+ The application has the ability to update the effective date, such that all the data and calculations are shown as of that effective date. This is more like a _developer_ functionality and should be removed for production

## File structure
`Property_rental` build with Django with the single app `rentals`. Rentals app has fairly standard structure:
+ `migrations` folder keep the history of model updates
+ `frontend` contains the React/TypeScript SPA, component tests, and Playwright scenarios
+ `rentals/analytics` owns financial classification, FX conversion, occupancy, yields, and bounded date bucketing
+ Django templates provide only the SPA shell; behavioral endpoints live under `/api/v1/`
+ In addition, `forms.py` to do form creation and handling, `constants.py` to use constants throughout the app, mainly in models and forms, and `utils.py` with additional useful functions to do, for instance, currency format representation, preparing datasets for charting (dates, labels), updating FX spot rates from yahoo finance (using yfinance package)

### Running the application
Can be run in `development` mode on the local server with Django approach, using `runserver` command. 

### Analytics API and visual regression checks

The React investment dashboard reads typed analytics responses from `/api/v1/analytics/portfolio/summary/`, `cash-flow/`, `expenses/`, `property-contribution/`, `yields/`, `currency-exposure/`, and `occupancy/`. Property valuation history is available at `/api/v1/analytics/properties/<id>/valuation/`. Time-series requests are capped at 600 buckets.

Run the frontend checks from `frontend/`:

```powershell
npm ci
$env:PW_CHANNEL='chrome'
npm run test:e2e -- --workers=1
```

`test:e2e` starts Vite with a root base for deterministic fixture-backed Playwright tests and runs the desktop (1440px), tablet (768px), and mobile (390px) projects. Exact-pixel baselines are pinned to Windows Chrome locally and in CI; other platform/browser combinations skip only the visual snapshot spec. Update intentional baselines with `$env:PW_CHANNEL='chrome'; npm run test:e2e -- --update-snapshots --workers=1`.
