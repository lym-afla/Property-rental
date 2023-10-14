from datetime import date, timedelta
import requests
import yfinance as yf

from .constants import CURRENCY_CHOICES, TRANSACTION_CATEGORIES
# from .models import FX, Transaction

# Define the effective 'current' date for the application
effective_current_date = date.today()

def get_currency_symbol(currency_code):
    for code, symbol in CURRENCY_CHOICES:
        if code == currency_code:
            return symbol
    return currency_code  # Return the code itself if not found

def get_category_name(category):
    for code, symbol in TRANSACTION_CATEGORIES:
        if code == category:
            return symbol
    return code  # Return the code itself if not found

def convert_period(string_date):
    print(f"Printing string date: {string_date}")
    MONTHS = {
        '01': 'Jan',
        '02': 'Feb',
        '03': 'Mar',
        '04': 'Apr',
        '05': 'May',
        '06': 'Jun',
        '07': 'Jul',
        '08': 'Aug',
        '09': 'Sep',
        '10': 'Oct',
        '11': 'Nov',
        '12': 'Dec'
    }
    
    if string_date:
        return MONTHS[string_date[-2:]] + '-' + string_date[2:4]
    else:
        return ''
    
# # Get quote 
# def quote_at_date(model, date, source='price', target='', asset_id=''):
#     filter_kwargs = {
#         f'{source}{target}__isnull': False,
#         'date': date
#     }

#     if asset_id:
#         filter_kwargs['asset_id'] = asset_id

#     queryset = model.objects.filter(**filter_kwargs)

#     if queryset.exists():
#         # Returns quote for a given date if it exists
#         result = queryset.values('date', f'{source}{target}', 'currency').first()

#         return {
#             'date': result['date'],
#             'quote': result[f'{source}{target}'],
#             'currency': result['currency']
#         }
#     else:
#         # Find the nearest earliest date where a quote exists in the table
#         filter_kwargs = {
#             f'{source}{target}__isnull': False,
#             'date__lt': date
#         }

#         if asset_id:
#             filter_kwargs['asset_id'] = asset_id

#         earliest_entry = model.objects.filter(**filter_kwargs).order_by('-date').first()

#         if earliest_entry:
#             return {
#                 'date': earliest_entry.date,
#                 'quote': getattr(earliest_entry, f'{source}{target}'),
#                 'currency': earliest_entry.currency
#             }
#         else:
#             # Handle the case when no earlier date is found
#             nearest_date = model.objects.filter(
#                 # f'{source}{target}__isnull': False,
#                 date__gt=date
#             )

#             if asset_id:
#                 nearest_date = nearest_date.filter(asset_id=asset_id)

#             nearest_date = nearest_date.order_by('date').first()

#             if nearest_date:
#                 print(f'Error: {source + target} quote does not exist at dates earlier than {date}. The nearest is {nearest_date.date.strftime("%Y-%m-%d")}')
#                 return {
#                     'date': date,
#                     'quote': 0,
#                     'currency': 'None'
#                 }
#             else:
#                 # Handle the case when no nearest date is found
#                 print(f'Error: {source + target} quote does not exist for any date.')
#                 return {
#                     'date': date,
#                     'quote': 0,
#                     'currency': 'None'
#                 }

# # Get FX quote
# def FX_rate(source_currency, target_currency, date):
#     fx_rate = 1
#     dates_async = False
#     dates_list = []

#     if source_currency == target_currency:
#         return {
#             'FX': fx_rate,
#             'conversions': 0,
#             'dates_async': dates_async,
#             'FX dates used': dates_list
#         }

#     # Get all existing pairs
#     pairs_list = [field.name for field in FX._meta.get_fields() if field.name != 'date']
    
#     # Create undirected graph with currencies, import networkx library working with graphs
#     import networkx as nx
#     G = nx.Graph()
#     for entry in pairs_list:
#         G.add_nodes_from([entry[0:3], entry[3:6]])
#         G.add_edge(entry[0:3], entry[3:6])
    
#     # Finding shortest path for cross-currency conversion using "Bellman-Ford" algorithm
#     cross_currency = nx.shortest_path(G, source_currency, target_currency, method='bellman-ford')

#     for i in range(1, len(cross_currency)):
#         i_source = cross_currency[i - 1]
#         i_target = cross_currency[i]
        
#         for element in pairs_list:
#             if i_source in element and i_target in element:
#                 if element.find(i_source) == 0:
#                     fx_call = quote_at_date(FX, date, i_source, i_target)
#                     fx_rate *= fx_call['quote']
#                     dates_list.append(fx_call['date'])
#                     dates_async = (dates_list[0] != fx_call['date']) or dates_async
#                 else:
#                     fx_call = quote_at_date(FX, date, i_target, i_source)
#                     fx_rate /= fx_call['quote']
#                     dates_list.append(fx_call['date'])
#                     dates_async = (dates_list[0] != fx_call['date']) or dates_async
#                 break
    
#     # Use inverse in order to multiply when using, not divide
#     fx_rate = round(1 / fx_rate, 4)
            
#     return {
#         'FX': fx_rate,
#         'conversions': len(cross_currency) - 1,
#         'dates_async': dates_async,
#         'dates': dates_list
#     }
    
def is_yahoo_finance_available():
    url = "https://finance.yahoo.com"  # Replace with the Yahoo Finance API endpoint if needed
    try:
        response = requests.get(url, timeout=5)
        if response.status_code == 200:
            return True
    except requests.ConnectionError:
        pass
    return False

def get_currency_exchange_rate(base_currency, target_currency, date, max_attempts=5):
    
    if not is_yahoo_finance_available():
        raise ConnectionError("Yahoo Finance is not available")
    
    # Define the currency pair (e.g., "USDEUR=X" for USD to EUR)
    currency_pair = f"{base_currency}{target_currency}=X"

    # Initialize a counter for the number of attempts
    attempt = 0

    while attempt < max_attempts:
        # Define the date for which you want the exchange rate
        end_date = date - timedelta(days=attempt - 1)  # Go back in time for each attempt. Need to deduct 1 to get rate for exactly the date
        start_date = end_date - timedelta(days=1)  # Go back one day to ensure the date is covered
        
        # Fetch historical data for the currency pair within the date range
        data = yf.Ticker(currency_pair)
        exchange_rate_data = data.history(period="1d", start=start_date, end=end_date)
        try:
            exchange_rate_data = data.history(period="1d", start=start_date, end=end_date)
            # print(f"Error: {yf.shared._ERRORS[currency_pair]}")
        except:
            attempt += 1
            continue

        if not exchange_rate_data.empty and not exchange_rate_data["Close"].isnull().all():
            # Get the exchange rate for the specified date
            print(f"Data: {exchange_rate_data}")
            exchange_rate = round(exchange_rate_data["Close"].iloc[0], 4)
            actual_date = exchange_rate_data.index[0].date()  # Extract the actual date

            return {
                'exchange_rate': exchange_rate,
                'actual_date': actual_date
            }

        # Increment the attempt counter
        attempt += 1

    # If no data is found after max_attempts, return None or an appropriate error message
    return None

# def update_fx_rates():
#     # Get FX model variables, except 'date'
#     fx_variables = [field for field in FX._meta.get_fields() if field.name != 'date']

#     # Extract source and target currencies
#     currency_pairs = [(field.name[:3], field.name[3:]) for field in fx_variables]

#     # Scan Transaction instances in the database to collect dates
#     transaction_dates = Transaction.objects.values_list('date', flat=True)

#     for date in transaction_dates:
#         print(f"Updating FX for {date} (toal: {len(transaction_dates)})")
#         for source, target in currency_pairs:
#             # Check if an FX rate exists for the date and currency pair
#             existing_rate = FX.objects.filter(date=date).values(f'{source}{target}').first()

#             if existing_rate is None:
#                 # Get the FX rate for the date
#                 rate_data = get_currency_exchange_rate(source, target, date)

#                 if rate_data['quote'] != 0:
#                     # Update or create an FX instance with the new rate
#                     fx_instance, created = FX.objects.get_or_create(date=rate_data['date'])
#                     setattr(fx_instance, f'{source}{target}', rate_data['quote'])
#                     fx_instance.save()