from datetime import date, timedelta
import requests
import yfinance as yf
from dateutil.relativedelta import relativedelta
import datetime

from .constants import CURRENCY_CHOICES, TRANSACTION_CATEGORIES

# Define the effective 'current' date for the application
effective_current_date = date.today()

# Define the currency of representation for aggregated data
currency_basis = 'USD'

# global_chart_settings = {
#     'frequency': 'M',
#     'timeline': '6m',
#     'To': effective_current_date
#     }

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
    
def is_yahoo_finance_available():
    """Check if Yahoo Finance is available by making a test request with proper headers"""
    url = "https://finance.yahoo.com"
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.5',
        'Accept-Encoding': 'gzip, deflate',
        'Connection': 'keep-alive',
        'Upgrade-Insecure-Requests': '1'
    }
    try:
        response = requests.get(url, headers=headers, timeout=10)
        if response.status_code == 200:
            return True
    except (requests.ConnectionError, requests.Timeout):
        pass
    return False

def update_FX_database(base_currency, target_currency, date, max_attempts=5):
    """
    Fetch FX rate from Yahoo Finance.
    
    Note: Modern yfinance uses curl_cffi internally to handle headers and browser mimicking.
    We let yfinance handle the session to avoid conflicts.
    
    Args:
        base_currency: Base currency code (e.g., 'USD')
        target_currency: Target currency code (e.g., 'EUR')
        date: Date for which to fetch the rate
        max_attempts: Number of attempts to try fetching data
        
    Returns:
        dict with exchange_rate, actual_date, requested_date or None if failed
    """
    if not is_yahoo_finance_available():
        raise ConnectionError("Yahoo Finance is not available")

    # Define the currency pair (Yahoo Finance format: XXXYYY=X)
    currency_pair = f"{target_currency}{base_currency}=X"

    # Initialize a counter for the number of attempts
    attempt = 0

    while attempt < max_attempts:
        # Define the date for which you want the exchange rate
        end_date = date - timedelta(
            days=attempt - 1
        )  # Go back in time for each attempt. Need to deduct 1 to get rate for exactly the date
        start_date = end_date - timedelta(days=1)  # Go back one day to ensure the date is covered

        # Fetch historical data for the currency pair within the date range
        try:
            # Let yfinance handle the session internally (uses curl_cffi for better browser mimicking)
            ticker = yf.Ticker(currency_pair)
            # Note: Only set start and end, not period (yfinance allows max 2 of period/start/end)
            exchange_rate_data = ticker.history(
                start=start_date.strftime('%Y-%m-%d'), 
                end=end_date.strftime('%Y-%m-%d')
            )
            
            # Add small delay to avoid rate limiting
            import time
            time.sleep(0.5)
            
        except Exception as e:
            print(f"Error fetching exchange rate data for {currency_pair}: {e}")
            attempt += 1
            continue

        if not exchange_rate_data.empty and not exchange_rate_data["Close"].isnull().all():
            # Get the exchange rate for the specified date
            exchange_rate = round(exchange_rate_data["Close"].iloc[0], 6)
            actual_date = exchange_rate_data.index[0].date()  # Extract the actual date

            print(
                f"Successfully fetched {currency_pair} rate for {actual_date}: {exchange_rate}"
            )

            return {
                "exchange_rate": exchange_rate,
                "actual_date": actual_date,
                "requested_date": date,
            }

        # Increment the attempt counter
        attempt += 1
        print(
            f"Attempt {attempt}/{max_attempts} failed for {currency_pair} on {date}"
        )

    # If no data is found after max_attempts, return None or an appropriate error message
    print(
        f"Failed to fetch {currency_pair} after {max_attempts} attempts for date {date}"
    )
    return None

# Collect chart dates 
def chart_dates(start_date, end_date, freq):
    from datetime import date, timedelta
    from dateutil.relativedelta import relativedelta
    
    # Convert the start_date and end_date strings to date objects
    if type(start_date) == str:
        start_date = date.fromisoformat(start_date)
    if type(end_date) == str:
        end_date = date.fromisoformat(end_date)

    # Store original dates
    original_start = start_date
    original_end = end_date

    # If the frequency is yearly, adjust the end_date to the end of the current year
    if freq == 'Y':
        end_date = end_date.replace(month=12, day=31)
        start_date = start_date.replace(month=1, day=1)

    if freq == 'M':
        # For monthly, adjust to next month start
        end_date = end_date + relativedelta(months=1)
        start_date = start_date + relativedelta(months=1)

    # Generate date range without pandas
    dates = []
    current_date = start_date
    
    if freq == 'D':  # Daily (business days)
        while current_date <= end_date:
            # Skip weekends (Monday=0, Sunday=6)
            if current_date.weekday() < 5:  # Monday-Friday
                dates.append(current_date)
            current_date += timedelta(days=1)
    
    elif freq == 'W':  # Weekly - simplified to start from original date
        current_date = original_start
        while current_date <= original_end:
            dates.append(current_date)
            current_date += timedelta(weeks=1)
    
    elif freq == 'M':  # Monthly
        # Simplified monthly: start from beginning of month after start_date
        current_date = start_date.replace(day=1)
        while current_date <= end_date:
            dates.append(current_date)
            current_date += relativedelta(months=1)
    
    elif freq == 'Q':  # Quarterly - align to quarter boundaries
        # Start from the first quarter that includes or follows the start date
        current_date = original_start
        # Move to the next quarter boundary
        if current_date.month <= 3:
            current_date = current_date.replace(month=3, day=31)
        elif current_date.month <= 6:
            current_date = current_date.replace(month=6, day=30)
        elif current_date.month <= 9:
            current_date = current_date.replace(month=9, day=30)
        else:
            current_date = current_date.replace(month=12, day=31)
        
        while current_date <= original_end:
            dates.append(current_date)
            current_date += relativedelta(months=3)
    
    elif freq == 'Y':  # Yearly
        while current_date <= end_date:
            dates.append(current_date)
            current_date += relativedelta(years=1)
    
    return dates
    
# Create labels according to dates
def chart_labels(dates, frequency):
    
    if frequency == 'D':
        return [i.strftime("%d-%b-%y") for i in dates]
    if frequency == 'W':
        return [i.strftime("%d-%b-%y") for i in dates]
    if frequency == 'M':
        return [i.strftime("%b-%y") for i in dates]
    if frequency == 'Q':
        labels = []
        for i in dates:
            if i.month == 3:
                labels.append('Q1 ' + i.strftime("%y"))
            if i.month == 6:
                labels.append('Q2 ' + i.strftime("%y"))
            if i.month == 9:
                labels.append('Q3 ' + i.strftime("%y"))
            if i.month == 12:
                labels.append('Q4 ' + i.strftime("%y"))
        return labels
    if frequency == 'Y':
        return [i.strftime("%Y") for i in dates]

# Calculating from date based on the final date and timeline
def calculate_from_date(to_date, timeline):
    
    if type(to_date) == str:
        to_date = datetime.datetime.strptime(to_date, "%Y-%m-%d").date()  # Convert 'to' date to datetime.date

    if timeline == 'YTD':
        from_date = to_date.replace(months=1, day=1)
    elif timeline == '3m':
        from_date = to_date - relativedelta(months=3)
    elif timeline == '6m':
        from_date = to_date - relativedelta(months=6)
    elif timeline == '12m':
        from_date = to_date - relativedelta(years=1)
    elif timeline == '3Y':
        from_date = to_date - relativedelta(years=3)
    elif timeline == '5Y':
        from_date = to_date - relativedelta(years=5)
    elif timeline == 'All time':
        from_date = '1900-01-01' # Convention that ultimately will be converted to the date of the first transaction
    else:
        # Handle other cases as needed
        from_date = to_date

    return from_date
