from django import template

register = template.Library()

@register.filter
def format_number_with_parentheses(value, args):
    digits, currency = args.split(',')
    if value < 0:
        return f'({currency}{abs(value):,.{digits}f})'
    elif value == 0:
        return '–'
    return f'{currency}{value:,.{digits}f}'

# @register.filter
# def format_number_with_currency(value, currency):
#     if value != 0:
#         return f'{currency}{value}'
