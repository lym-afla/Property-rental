import yfinance as yf
import datetime
# import requests

from rentals.utils import update_FX_database
# from rentals.models import FX

# Example usage
date = datetime.datetime(2023, 5, 16)  # Replace with your desired date
usd_to_eur = update_FX_database("USD", "GBP", date)

if usd_to_eur is not None:
    print(f"USD to EUR exchange rate on {usd_to_eur['actual_date']}: {usd_to_eur['exchange_rate']}")
else:
    print(f"No exchange rate data found for {date}")

# FX.update_fx_rates()
# print(FX.objects.all())