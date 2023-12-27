# Property rental tracking application

This is a web application to keep track of a portfolio of properties in terms of renting statistics together with the economic result of property rentals. It is written on Python with Django framework on the back-end and plain HTML with JavaScript on the front-end.

## Distinctiveness and Complexity
+ The idea of the project is to bring property portfolio management analytics to the database of properties
+ The data is structured as a comprehensive database consisting of eight models (users, landlord, tenants, property, property funding, transactions, rent history, FX data)
+ The app allows registered user to save own properties and include key information (address, footage, rooms, price, etc.), create tenants and "rent" own properties to tenants. Include revenue inputs (rent received) and costs (utility bills, capex, etc.) into the respective database. And track the economics of each property project: P&L components, charges executed in time, rent outstanding
+ `Chart.js` package is used to include charts in the application, normally showing P&L entries for the portfolio or distinct properties and rent history
+ Instances of the main models (user, property, tenant, transaction) can also be edited in case of the wrong data
+ User settings are also included to be able to save user details (username, name, email) and data visual properties (default currency, chart frequency, chart timeline and number of digits shown in tables)
+ The application is multi-currency. Each property has its onw _natural_ currrency. Data representation, however, can be made in any currency (set up in user settings). And home page, summarising all the statistics is shown using single default currency. After the new transaction is entered special function is run to update FX database to be able to convert currencies
+ For consistency of FX conversions _Bellman-Ford_ algorithm used for shortest path cross-currency conversion using `networkx` library to deal with undirected graphs

## File structure
`Property_rental` build with Django with the single app `rentals`. Rentals app has fairly standard structure:
+ `migrations` folder
+ `static` folder with images used, styles.css and a number of JavaScript files that are used to handle actions on web pages
+ `templates` folder with a number of `html` pages, templates and snippets used when rendering pages (layouts for home page, property, tenants and transaction pages, chart divs, tables)
+ Fairly standard `views.py`, `models.py`, `urls.py` handling routing and exchange of data between back-end and front-end
+ In addition, `forms.py` to do form creation and handling, `constants.py` to use constants throughout the app, mainly in models and forms, and `utils.py` with additional useful functions to do, for instance, currency format representation, preparing datasets for charting (dates, labels), updating FX spot rates from yahoo finance (using yfinance package)

### Running the application
Can be run in `development` mode on the local server with Django approach, using `runserver` command. 
