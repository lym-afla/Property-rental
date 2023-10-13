import yfinance as yf
import datetime

def get_currency_exchange_rate(base_currency, target_currency, date, max_attempts=10):
    # Define the currency pair (e.g., "USDEUR=X" for USD to EUR)
    currency_pair = f"{base_currency}{target_currency}=X"

    # Initialize a counter for the number of attempts
    attempt = 0

    while attempt < max_attempts:
        # Define the date for which you want the exchange rate
        end_date = date - datetime.timedelta(days=attempt - 1)  # Go back in time for each attempt. Need to deduct 1 to get rate for exactly the date
        start_date = end_date - datetime.timedelta(days=1)  # Go back one day to ensure the date is covered

        # Fetch historical data for the currency pair within the date range
        data = yf.Ticker(currency_pair)
        try:
            exchange_rate_data = data.history(period="1d", start=start_date, end=end_date)
            print(f"Error: {yf.shared._ERRORS[currency_pair]}")
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

# Example usage
date = datetime.datetime(2023, 5, 16)  # Replace with your desired date
usd_to_eur = get_currency_exchange_rate("USD", "EUR", date)

if usd_to_eur is not None:
    print(f"USD to EUR exchange rate on {usd_to_eur['actual_date']}: {usd_to_eur['exchange_rate']}")
else:
    print(f"No exchange rate data found for {date}")
