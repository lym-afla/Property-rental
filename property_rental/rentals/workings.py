from .constants import CURRENCY_CHOICES

def get_currency_symbol(currency_code):
    for code, symbol in CURRENCY_CHOICES:
        if code == currency_code:
            return symbol
    return currency_code  # Return the code itself if not found