# import yfinance as yf

import os
from django import setup
from django.conf import settings
import datetime
# import requests
from rentals.models import Transaction

from rentals.utils import update_FX_database
# from rentals.models import FX

# Configure Django settings
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "property_rental.settings")
setup()

# Example usage
date = datetime.datetime(2023, 5, 16)  # Replace with your desired date
# usd_to_eur = update_FX_database("USD", "GBP", date)

# if usd_to_eur is not None:
#     print(f"USD to EUR exchange rate on {usd_to_eur['actual_date']}: {usd_to_eur['exchange_rate']}")
# else:
#     print(f"No exchange rate data found for {date}")

transaction_dates = Transaction.objects.values_list('date', flat=True)
print(transaction_dates)