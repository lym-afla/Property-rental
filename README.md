# Property rental tracking application

This is a web application to keep track of a portfolio of properties in terms of renting statistics together with the economic result of property rentals. It is written on Python with Django framework on the back-end and plain HTML with JavaScript on the front-end.

## Distinctiveness and Complexity
+ The idea of the project is to bring property portfolio management analytics to the database of properties data
+ The data is sructured as a comprehensive database consisting of eight models (users, landlord, tenants, property, property funding, transactions, rent history, FX data)
+ The app allows registered user to save own properties and include key information (address, footage, rooms, price, etc.), create tenants and "rent" own properties to tenants. Include revenue inputs (rent received) and costs (utility bills, capex, etc.) into the respective database. And track the economics of each property project: P&L components, charges executed in time, rent outstanding
+ Chart.js is used to include charts in the application, normally showing P&L entries for the portfolio or distinct properties and rent history
+ Instances of the main models (user, property, tenant, transaction) can also be edited in case of the wrong data
+ User settings are also included to be able to save user details (username, name, email) and data visual properties (default currency, chart frequency, chart timeline and number of digits shown in tables)
