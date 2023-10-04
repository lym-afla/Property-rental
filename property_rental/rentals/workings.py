from .constants import CURRENCY_CHOICES, TRANSACTION_CATEGORIES

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