from .constants import CURRENCY_CHOICES, TRANSACTION_CATEGORIES
from datetime import date

from .models import FX

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
    
# Get quote 
def quote_at_date(model, date, source='price', target='', asset_id=''):
    filter_kwargs = {
        f'{source}{target}__isnull': False,
        'date': date
    }

    if asset_id:
        filter_kwargs['asset_id'] = asset_id

    queryset = model.objects.filter(**filter_kwargs)

    if queryset.exists():
        # Returns quote for a given date if it exists
        result = queryset.values('date', f'{source}{target}', 'currency').first()

        return {
            'date': result['date'],
            'quote': result[f'{source}{target}'],
            'currency': result['currency']
        }
    else:
        # Find the nearest earliest date where a quote exists in the table
        filter_kwargs = {
            f'{source}{target}__isnull': False,
            'date__lt': date
        }

        if asset_id:
            filter_kwargs['asset_id'] = asset_id

        earliest_entry = model.objects.filter(**filter_kwargs).order_by('-date').first()

        if earliest_entry:
            return {
                'date': earliest_entry.date,
                'quote': getattr(earliest_entry, f'{source}{target}'),
                'currency': earliest_entry.currency
            }
        else:
            # Handle the case when no earlier date is found
            nearest_date = model.objects.filter(
                f'{source}{target}__isnull': False,
                date__gt=date
            )

            if asset_id:
                nearest_date = nearest_date.filter(asset_id=asset_id)

            nearest_date = nearest_date.order_by('date').first()

            if nearest_date:
                print(f'Error: {source + target} quote does not exist at dates earlier than {date}. The nearest is {nearest_date.date.strftime("%Y-%m-%d")}')
                return {
                    'date': date,
                    'quote': 0,
                    'currency': 'None'
                }
            else:
                # Handle the case when no nearest date is found
                print(f'Error: {source + target} quote does not exist for any date.')
                return {
                    'date': date,
                    'quote': 0,
                    'currency': 'None'
                }

# Get FX quote
def FX_rate(source_currency, target_currency, date):
    fx_rate = 1
    dates_async = False
    dates_list = []

    if source_currency == target_currency:
        return {
            'FX': fx_rate,
            'conversions': 0,
            'dates_async': dates_async,
            'FX dates used': dates_list
        }

    # Get all existing pairs
    pairs_list = [field.name for field in FX._meta.get_fields() if field.name != 'date']
    
    # Create undirected graph with currencies, import networkx library working with graphs
    import networkx as nx
    G = nx.Graph()
    for entry in pairs_list:
        G.add_nodes_from([entry[0:3], entry[3:6]])
        G.add_edge(entry[0:3], entry[3:6])
    
    # Finding shortest path for cross-currency conversion using "Bellman-Ford" algorithm
    cross_currency = nx.shortest_path(G, source_currency, target_currency, method='bellman-ford')

    for i in range(1, len(cross_currency)):
        i_source = cross_currency[i - 1]
        i_target = cross_currency[i]
        
        for element in pairs_list:
            if i_source in element and i_target in element:
                if element.find(i_source) == 0:
                    fx_call = quote_at_date(FX, date, i_source, i_target)
                    fx_rate *= fx_call['quote']
                    dates_list.append(fx_call['date'])
                    dates_async = (dates_list[0] != fx_call['date']) or dates_async
                else:
                    fx_call = quote_at_date(FX, date, i_target, i_source)
                    fx_rate /= fx_call['quote']
                    dates_list.append(fx_call['date'])
                    dates_async = (dates_list[0] != fx_call['date']) or dates_async
                break
    
    # Use inverse in order to multiply when using, not divide
    fx_rate = round(1 / fx_rate, 4)
            
    return {
        'FX': fx_rate,
        'conversions': len(cross_currency) - 1,
        'dates_async': dates_async,
        'dates': dates_list
    }