from datetime import date, timedelta
from dateutil.relativedelta import relativedelta
import datetime
from django.conf import settings
from django.utils import timezone

from .constants import CURRENCY_CHOICES, TRANSACTION_CATEGORIES

# Define the currency of representation for aggregated data
currency_basis = 'USD'

# NOTE: The former process-global ``effective_current_date`` was removed in
# Task 8 because it bled across users (any user's update mutated it for every
# concurrent request). Per-user as-of dates now live on ``User.effective_date``
# and are resolved via ``get_effective_date(user)`` below.

# global_chart_settings = {
#     'frequency': 'M',
#     'timeline': '6m',
#     'To': effective_current_date
#     }


def get_effective_date(user):
    """Return the as-of date for ``user``.

    Mirrors the legacy ``effective_current_date`` global but scoped per user:
    each user's ``effective_date`` field drives their own view of the data,
    so concurrent users no longer share a single mutable date. Falls back to
    ``date.today()`` when the user has no ``effective_date`` set (None),
    which preserves the pre-Task-8 default behavior for existing users and
    for tests that do not pin a specific date.
    """
    if not settings.LOCAL_PASSWORD_AUTH_ENABLED:
        return timezone.localdate()
    return getattr(user, "effective_date", None) or date.today()

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
        from_date = date(to_date.year, 1, 1)
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
