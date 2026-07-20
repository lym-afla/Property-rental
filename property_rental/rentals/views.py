from django.shortcuts import render, redirect
from django.contrib.auth import logout, update_session_auth_hash
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.conf import settings
from django.http import JsonResponse, HttpResponse, HttpResponseNotAllowed
from django.views.generic import TemplateView
import json
from rest_framework import serializers
from datetime import date
from django.shortcuts import get_object_or_404
from django.db.models import Sum, Q
from dateutil.relativedelta import relativedelta
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from django.db import models

from .forms import PropertyForm, TenantForm, TransactionForm, UserProfileForm, UserSettingsForm, PropertyValuationForm, CustomPasswordChangeForm, TenantVacateForm
from .models import Property, Landlord, Tenant, Transaction, Lease_rent, FX, Property_capital_structure
from .utils import get_currency_symbol, get_category_name, get_effective_date, convert_period, chart_dates, chart_labels, calculate_from_date
from .constants import INCOME_CATEGORIES

# Using built-in serializers as the manual did not recognize currencies properly
class PropertySerializer(serializers.ModelSerializer):
    class Meta:
        model = Property
        fields = '__all__'

class TenantSerializer(serializers.ModelSerializer):
    class Meta:
        model = Tenant
        fields = '__all__'

class TransactionSerializer(serializers.ModelSerializer):
    # Make 'type' read-only
    type = serializers.ReadOnlyField()

    class Meta:
        model = Transaction
        fields = '__all__'

    # Assign correct sign to 'amount' based on the transaction category
    def to_internal_value(self, data):
        # Call the parent class method to get the initial internal value
        internal_value = super(TransactionSerializer, self).to_internal_value(data)

        # Determine the sign based on the category
        if 'category' in data:
            if data['category'] in INCOME_CATEGORIES:
                internal_value['amount'] = abs(internal_value['amount'])
            else:
                internal_value['amount'] = -abs(internal_value['amount'])

        return internal_value

class PropertyValuationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Property_capital_structure
        fields = '__all__'

def index(request):

    if request.user.is_authenticated:

        currency_basis = request.session['default_currency']

        # Resolve the as-of date per user (replaces the process-global
        # effective_current_date; falls back to date.today() if unset).
        effective_current_date = get_effective_date(request.user)

        landlord = Landlord.objects.get(user=request.user)
        properties = landlord.properties.filter(Q(sold__isnull=True) | Q(sold__gte=effective_current_date)).all()
        current_year = effective_current_date.year
        revenue_ytd = Transaction.financials(target_currency=currency_basis, end_date=effective_current_date, properties=properties, start_date=date(current_year, 1, 1), transaction_type='income')
        expense_ytd = Transaction.financials(target_currency=currency_basis, end_date=effective_current_date, properties=properties, start_date=date(current_year, 1, 1), transaction_type='expense')

        print(f'index function. properties. {properties == None}')

        debt = 0
        for property in properties:
            for tenant in property.tenants.all():
                # Only include debt from active tenants (not vacated)
                if tenant.lease_end is None or tenant.lease_end > effective_current_date:
                    debt += tenant.debt(effective_current_date) * FX.get_rate(property.currency, currency_basis, effective_current_date)['FX']
        dashboard_card_props = [
            {
                'logoLink': settings.STATIC_URL + 'rentals/img/houses.svg',
                'number': properties.count(),
                'number_text': '',
                'text': 'Properties',
            },
            {
                'logoLink': settings.STATIC_URL + 'rentals/img/cash-coin.svg',
                'number': get_currency_symbol(currency_basis) + str(f'{revenue_ytd:,.0f}'),
                'number_text': '',
                'text': 'Revenue YTD',
            },
            {
                'logoLink': settings.STATIC_URL + 'rentals/img/cash-coin.svg',
                'number': get_currency_symbol(currency_basis) + str(f'{revenue_ytd + expense_ytd:,.0f}'),
                'number_text': '',
                'text': 'Income YTD',
            },
            {
                'logoLink': settings.STATIC_URL + 'rentals/img/exclamation-diamond-fill.svg',
                'number': get_currency_symbol(currency_basis) + str(f'{-debt:,.0f}'),
                'number_text': '',
                'text': 'Rent due',
            },
        ]

        # print(f'index function. debt. {get_currency_symbol(currency_basis) + str(f'{-debt:,.0f}')}')

        chart_settings = request.session['chart_settings']
        from_date = calculate_from_date(chart_settings['To'], chart_settings['timeline'])
        chart_settings['From'] = from_date.strftime("%Y-%m-%d")
        if type(chart_settings['To']) != str:
            chart_settings['To'] = chart_settings['To'].strftime("%Y-%m-%d")

        chart_data = get_chart_data(type='homePage',
                                    element_id=None,
                                    frequency=chart_settings['frequency'],
                                    from_date=from_date,
                                    to_date=chart_settings['To'],
                                    currency=currency_basis,
                                    properties=properties
                                    )

        digits = request.session['digits']
        expenses, rent_ytd, rent_all_time, unique_categories = pnl_calc(properties, currency_basis, True, digits, as_of=effective_current_date)

        pnl = {
            'rent': {
                'ytd': rent_ytd,
                'all_time': rent_all_time,
                },
            'expenses': expenses,
            'net_income': {
                'ytd': rent_ytd + expenses['total']['ytd'],
                'all_time': rent_all_time + expenses['total']['all_time'],
                },
            'format_args': str(digits) + ',' + get_currency_symbol(currency_basis),
            }

        properties = [ {'id': property.id, 'name': property.name} for property in properties]

        return render(request, 'rentals/index.html', {
            'dashboard_card_props': dashboard_card_props,
            # 'app_date': effective_current_date.strftime("%Y-%m-%d"),
            'chart_settings': chart_settings,
            'chart_data': chart_data,
            'properties': properties,
            'pnl': pnl,
        })
    else:
        # Task 13: the legacy ``/login/`` template route was deleted; the
        # SPA catch-all (``SpaView``) now serves the shell at ``/login/``,
        # and React Router renders the LoginPage client-side.
        return redirect('/login/')

def logout_view(request):
    logout(request)
    return redirect('rentals:index')

@login_required
def new_form(request, form_type):

    # Create an instance of the Form
    if form_type == 'property':
        form = PropertyForm()
    elif form_type == 'tenant':
        # Passing landlord to have the selection of properties for a tenant
        landlord = Landlord.objects.get(user=request.user)
        form = TenantForm(landlord_user=landlord)
    elif form_type == 'transaction':
        # Passing landlord to have the selection of properties for a tenant
        landlord = Landlord.objects.get(user=request.user)
        form = TransactionForm(landlord_user=landlord)
    elif form_type == 'propertyValuation':
        form = PropertyValuationForm()
    else:
        messages.error(request, "Wrong form type requested")
        return redirect('rentals:index')

    return render(request, 'rentals/new_form.html', {'form': form, 'form_type': form_type})

# Get data to populate table with selected elements
@login_required
def table_data(request, data_type):

    try:
        landlord = Landlord.objects.get(user=request.user)
        properties_owned_by_landlord = Property.objects.filter(owned_by=landlord)
    except Landlord.DoesNotExist:
        return JsonResponse({'error': 'Landlord does not exist.'}, status=400)

    # Per-user as-of date (replaces the process-global).
    effective_current_date = get_effective_date(request.user)

    data = [effective_current_date.strftime("%Y-%m-%d")]  # List to store elements data
    digits = request.session['digits']

    match data_type:
        case 'property':
            for property in properties_owned_by_landlord:

                property_tenant = Tenant.objects.filter(property=property).order_by('lease_start').first()
                rent_since = property_tenant.lease_start if property_tenant else None
                property_currency = property.currency if request.session['default_currency_for_all_data'] == False else request.session['default_currency']

                income_all_time = Transaction.financials(effective_current_date, target_currency=property_currency, properties=[property], transaction_type='income')
                expense_all_time = Transaction.financials(effective_current_date, target_currency=property_currency, properties=[property], transaction_type='expense')

                current_year = effective_current_date.year
                income_YTD = Transaction.financials(properties=[property], target_currency=property_currency, start_date=date(current_year, 1, 1), end_date=date(current_year, 12, 31), transaction_type='income')
                expense_YTD = Transaction.financials(properties=[property], target_currency=property_currency, start_date=date(current_year, 1, 1), end_date=date(current_year, 12, 31), transaction_type='expense')

                property_data = {
                    'id': property.id,
                    'name': property.name,
                    'location': property.location,
                    'rent_since': rent_since,
                    'status': property.status(effective_current_date),
                    'income_all_time': round(float(income_all_time), digits),
                    'expense_all_time': round(float(expense_all_time), digits),
                    'net_income_all_time': round(float(income_all_time + expense_all_time), digits),
                    'income_ytd': round(float(income_YTD), digits),
                    'expense_ytd': round(float(expense_YTD), digits),
                    'net_income_ytd': round(float(income_YTD + expense_YTD), digits),
                    'currency': get_currency_symbol(property_currency),
                }
                data.append(property_data)
        case 'tenant':
            tenants = Tenant.objects.filter(property__in=properties_owned_by_landlord)
            for tenant in tenants:

                tenant_currency = tenant.property.currency if request.session['default_currency_for_all_data'] == False else request.session['default_currency']

                # Use rent_total with include_post_vacation=True to include payments after tenant vacated
                revenue_all_time = tenant.rent_total(effective_current_date, target_currency=tenant_currency, include_post_vacation=True)
                current_year = effective_current_date.year
                revenue_YTD = tenant.rent_total(start_date=date(current_year, 1, 1), end_date=date(current_year, 12, 31), target_currency=tenant_currency, include_post_vacation=True)

                lease_rent = tenant.lease_rent(effective_current_date)

                # Determine tenant status
                is_vacated = tenant.lease_end is not None and tenant.lease_end <= effective_current_date
                will_vacate = tenant.lease_end is not None and tenant.lease_end > effective_current_date
                
                if is_vacated:
                    status = 'Vacated'
                elif will_vacate:
                    status = 'Will Vacate'
                else:
                    status = 'Active'

                tenant_data = {
                    'id': tenant.id,
                    'first_name': tenant.first_name,
                    'property': tenant.property.name,
                    'lease_start': tenant.lease_start,
                    'lease_end': tenant.lease_end,
                    'is_vacated': is_vacated,
                    'will_vacate': will_vacate,
                    'status': status,
                    'currency': get_currency_symbol(tenant_currency),
                    'lease_rent': lease_rent if type(lease_rent) == str else float(tenant.lease_rent(effective_current_date)),
                    'lease_native_currency': get_currency_symbol(tenant.property.currency),
                    'revenue_all_time': round(float(revenue_all_time), digits),
                    'revenue_ytd': round(float(revenue_YTD), digits),
                    'debt': round(float(tenant.debt(effective_current_date) * FX.get_rate(tenant.property.currency, tenant_currency, effective_current_date)['FX']), digits),
                }
                data.append(tenant_data)
        case 'transaction':
            transactions = Transaction.objects.filter(property__in=properties_owned_by_landlord, date__lte=effective_current_date).order_by('-date')

            for transaction in transactions:
                transaction_currency = transaction.currency if request.session['default_currency_for_all_data'] == False else request.session['default_currency']
                transaction_data = {
                    'id': transaction.id,
                    'transaction_date': transaction.date,
                    'property': transaction.property.name,
                    'tenant': f"{transaction.tenant.first_name} {transaction.tenant.last_name}" if transaction.tenant else "—",
                    'category': get_category_name(transaction.category),
                    'currency': get_currency_symbol(transaction_currency),
                    'transaction_amount': round(float(transaction.amount * FX.get_rate(transaction.currency, transaction_currency, transaction.date)['FX']), digits) if transaction.amount else None,
                    'comment': transaction.comment,
                    'period': convert_period(transaction.period),
                }
                data.append(transaction_data)
        case 'propertyValuation':
            property_id = request.GET.get('property_id')
            selected_property = Property.objects.get(id=property_id)
            property_valuations = selected_property.capital.filter(capital_structure_date__lte=effective_current_date).order_by('-capital_structure_date')
            property_currency = selected_property.currency

            for valuation in property_valuations:
                valuation_data = {
                    'id': valuation.id,
                    'date': valuation.capital_structure_date,
                    'value': round(float(valuation.capital_structure_value), digits) if valuation.capital_structure_value is not None else None,
                    'debt': round(float(valuation.capital_structure_debt), digits) if valuation.capital_structure_debt is not None else None,
                    'currency': get_currency_symbol(property_currency),
                }
                data.append(valuation_data)
        case _:
            return JsonResponse({'error': 'Data type does not exist.'}, status=400)

    return JsonResponse(data, safe=False)

# Get data for a particular element
@login_required
def handle_element(request, data_type, element_id):

    # Per-user as-of date (replaces the process-global).
    effective_current_date = get_effective_date(request.user)

    match data_type:
        case 'property':
            try:
                element = Property.objects.get(id=element_id)
            except Property.DoesNotExist:
                return JsonResponse({'error': 'Property not found'}, status=404)
        case 'tenant':
            try:
                element = Tenant.objects.get(id=element_id)
            except Tenant.DoesNotExist:
                return JsonResponse({'error': 'Tenant not found'}, status=404)
        case 'transaction':
            try:
                element = Transaction.objects.get(id=element_id)
            except Transaction.DoesNotExist:
                return JsonResponse({'error': 'Transaction not found'}, status=404)
        case 'propertyValuation':
            try:
                element = Property_capital_structure.objects.get(id=element_id)
            except Property_capital_structure.DoesNotExist:
                return JsonResponse({'error': 'Property valuation entry not found'}, status=404)
        case _:
            return JsonResponse({'error': f'Unknown data type: {data_type}'}, status=400)

    if request.method == 'GET':
        digits = request.session['digits']
        match data_type:
            case 'property':
                # Check if the logged-in user is the landlord of the property
                if request.user.is_landlord and element.owned_by.user == request.user:

                    # Define the currency for calculations
                    element_currency = element.currency if request.session['default_currency_for_all_data'] == False else request.session['default_currency']

                    expenses, rent_ytd, rent_all_time, unique_categories = pnl_calc([element], element_currency, request.session['default_currency_for_all_data'], digits, as_of=effective_current_date)

                    # Get data for Payments schedule
                    # Create a list of month abbreviations for the six previous months
                    number_of_months = 5
                    months_for_payment_schedule = []
                    # unique_categories.insert(0, 'rent')
                    rows_for_payment_schedule = {get_category_name(category): [] for category in unique_categories}
                    for i in range(number_of_months):
                        # Calculate the month number for the previous month
                        prev_month = (effective_current_date.month - i - 1) % 12

                        # Map the month number to its abbreviation
                        month_abbreviations = ['J', 'F', 'M', 'A', 'M', 'J', 'J', 'A', 'S', 'O', 'N', 'D']
                        month_abbrev = month_abbreviations[prev_month - 1]

                        # Add the abbreviation to the list
                        months_for_payment_schedule.append(month_abbrev)

                        # Calculate the year and month for the month to check
                        year_to_check = effective_current_date.year
                        month_to_check = prev_month

                        # Adjust the year if the month is less than 1 (January)
                        if month_to_check < 1:
                            month_to_check += 12
                            year_to_check -= 1

                        for category in unique_categories:
                            # Check if a transaction exists for the given category, year, and month
                            transaction_exists = element.transactions.filter(
                                category=category,
                                period=f"{year_to_check}-{month_to_check:02}",
                            ).exists()
                            rows_for_payment_schedule[get_category_name(category)].insert(0, 'green' if transaction_exists else 'red')

                    # Reverse the list to get the months in chronological order
                    months_for_payment_schedule.reverse()

                    data = {
                        'name': element.name,
                        'location': element.location,
                        'num_bedrooms': element.num_bedrooms,
                        'area': round(float(element.area), digits) if element.area else None,
                        'currency': get_currency_symbol(element_currency),
                        'property_value': round(float(element.property_value(effective_current_date)[0] / 1000), digits) if element.property_value(effective_current_date) else None,
                        'rent': {
                            'ytd': round(float(rent_ytd), digits),
                            'all_time': round(float(rent_all_time), digits),
                        },
                        'expenses': expenses,
                        'net_income': {
                            'ytd': round(float(rent_ytd + expenses['total']['ytd']), digits),
                            'all_time': round(float(rent_all_time + expenses['total']['all_time']), digits),
                        },
                        'months': months_for_payment_schedule,
                        'rows': rows_for_payment_schedule,
                        'address': element.address,
                        'app_date': effective_current_date,
                    }

                    # Rounding according to user settings. Not rounded before defining data to calculate net income without rounding errors.
                    data['expenses']['total']['ytd'] = round(float(data['expenses']['total']['ytd']), digits)
                    data['expenses']['total']['all_time'] = round(float(data['expenses']['total']['all_time']), digits)

                    chart_settings = request.session['chart_settings']
                    data['chart_settings'] = chart_settings
                    from_date = calculate_from_date(chart_settings['To'], chart_settings['timeline'])
                    data['chart_settings']['From'] = from_date
                    data['chart_data'] = get_chart_data('property', element.id, chart_settings['frequency'], from_date, chart_settings['To'], element_currency)
                else:
                    return JsonResponse({'error': 'You do not have permission to access this property'}, status=403)
            case 'tenant':
                # Check if the logged-in user is the landlord and tenant lives in landlord's property
                if request.user.is_landlord and element.property.owned_by.user == request.user:

                    lease_rent_value = element.lease_rent(effective_current_date)
                    if isinstance(lease_rent_value, (int, float)):
                        lease_rent = round(lease_rent_value, digits)
                    else:
                        lease_rent = lease_rent_value  # Keep as string if not numeric

                    element_currency = element.property.currency if request.session['default_currency_for_all_data'] == False else request.session['default_currency']

                    # Determine tenant status
                    is_vacated = element.lease_end is not None and element.lease_end <= effective_current_date
                    will_vacate = element.lease_end is not None and element.lease_end > effective_current_date
                    
                    if is_vacated:
                        status = 'Vacated'
                    elif will_vacate:
                        status = 'Will Vacate'
                    else:
                        status = 'Active'

                    data = {
                        'id': element.id,
                        'first_name': element.first_name,
                        'last_name': element.last_name,
                        'phone': element.phone,
                        'email': element.email,
                        'renting_since': element.lease_start,
                        'left_property_at': element.lease_end,
                        'is_vacated': is_vacated,
                        'will_vacate': will_vacate,
                        'status': status,
                        'rent_currency': get_currency_symbol(element_currency),
                        'rent_native_currency': get_currency_symbol(element.property.currency),
                        'rent_rate': lease_rent if type(lease_rent) == str else round(float(element.lease_rent(effective_current_date)), digits),
                        'property': element.property.name,
                        'property_id': element.property.id,
                        'all_time_rent': round(float(element.rent_total(end_date=effective_current_date, target_currency=element_currency, include_post_vacation=True)), digits),
                        'payday': element.payday,
                        'app_date': effective_current_date.strftime("%Y-%m-%d"),
                    }

                    # Default chart settings
                    # global chart_settings
                    chart_settings = request.session['chart_settings']
                    data['chart_settings'] = chart_settings
                    from_date = calculate_from_date(chart_settings['To'], chart_settings['timeline'])
                    data['chart_settings']['From'] = from_date
                    data['chart_data'] = get_chart_data('tenant', element.id, chart_settings['frequency'], from_date, chart_settings['To'], element_currency)
                else:
                    return JsonResponse({'error': 'You do not have permission to access this tenant'}, status=403)
            case 'transaction':
                element_currency = element.currency if request.session['default_currency_for_all_data'] == False else request.session['default_currency']
                if request.user.is_landlord and element.property.owned_by.user == request.user:
                    tenant_label = f"{element.tenant.first_name} {element.tenant.last_name}" if element.tenant else ""
                    data = {
                        'property': element.property.name,
                        'tenant': tenant_label,
                        'transaction_date': element.date,
                        'category': element.category,
                        'period': element.period,
                        'currency': get_currency_symbol(element_currency),
                        'amount': abs(element.amount),
                        'comment': element.comment,
                        'app_date': effective_current_date.strftime("%Y-%m-%d"),
                    }
            case 'propertyValuation':
                # element_currency = element.currency if request.session['default_currency_for_all_data'] == False else request.session['default_currency']
                if request.user.is_landlord and element.property.owned_by.user == request.user:
                    data = {
                        'date': element.capital_structure_date,
                        'value': element.capital_structure_value,
                        'debt': element.capital_structure_debt,
                        'property_id': element.property.id,
                        'currency': element.property.currency,
                    }
                print(f'561. Printing data: {data}')
        return JsonResponse(data, status=200)
    elif request.method == 'DELETE':
        if data_type == 'property':
            owner_user = element.owned_by.user
        else:  # tenant, transaction, propertyValuation all route through .property.owned_by
            owner_user = element.property.owned_by.user
        if owner_user != request.user:
            return JsonResponse({'error': 'Not authorized'}, status=403)
        element.delete()
        return JsonResponse({'message': f'{data_type} deleted successfully'}, status=200)
    elif request.method == 'PUT':
        # Ownership check (final-review fix): mirror the DELETE branch's
        # per-data_type ownership check BEFORE any mutation. Without this,
        # any authenticated landlord could PUT to another landlord's
        # /handling/<data_type>/<id> and mutate their records (IDOR).
        if data_type == 'property':
            owner_user = element.owned_by.user
        else:  # tenant, transaction, propertyValuation all route through .property.owned_by
            owner_user = element.property.owned_by.user
        if owner_user != request.user:
            return JsonResponse({'error': 'Not authorized'}, status=403)
        try:
            json_data = json.loads(request.body)
            match data_type:
                case 'property':
                    # Retain the existing 'owned_by' value
                    json_data['owned_by'] = element.owned_by.id
                    serializer = PropertySerializer(instance=element, data=json_data)
                case 'tenant':
                    serializer = TenantSerializer(instance=element, data=json_data)
                case 'transaction':
                    serializer = TransactionSerializer(instance=element, data=json_data)
                case 'propertyValuation':
                    serializer = PropertyValuationSerializer(instance=element, data=json_data)
            if serializer.is_valid():
                serializer.save()
                return JsonResponse({'success': True}, status=200)
            else:
                print(serializer.errors)
                return JsonResponse({'errors': serializer.errors}, status=400)
        except json.JSONDecodeError:
            return JsonResponse({'error': 'Invalid JSON data in request body'}, status=400)
    else:
        return HttpResponseNotAllowed(['GET', 'PUT', 'DELETE'])  # Return a 405 Method Not Allowed response for other methods

# Saave particular element
@login_required
def create_element(request, data_type):

    if request.method == 'POST':
        match data_type:
            case 'property':
                if request.user.is_landlord:
                    # Form for creating new property
                    form = PropertyForm(request.POST or None)
                    if form.is_valid():
                        property_instance = form.save(commit=False)
                        property_instance.owned_by = Landlord.objects.get(user=request.user)
                        property_instance.save()

                        # Create Property_capital_structure instance
                        date = form.cleaned_data.get('capital_structure_date')
                        value = form.cleaned_data.get('capital_structure_value')
                        debt = form.cleaned_data.get('capital_structure_debt')

                        if date:
                            capital_structure_instance = Property_capital_structure(
                                property=property_instance,
                                capital_structure_date=date,
                                capital_structure_value=value,
                                capital_structure_debt=debt,
                            )
                            capital_structure_instance.save()

                        return JsonResponse({'message': 'Property created successfully'}, status=200)
                    else:
                        return JsonResponse({'errors': form.errors}, status=400)
                else:
                    return JsonResponse({'error': 'You do not have permission to access this property'}, status=403)
            case 'tenant':
                if request.user.is_landlord:
                    form = TenantForm(landlord_user=Landlord.objects.get(user=request.user), data=request.POST)
                    if form.is_valid():
                        tenant = form.save(commit=False)
                        # Retrieve the property ID from the form data
                        property_id = request.POST.get('property')

                        property = get_object_or_404(Property, id=property_id)

                        tenant.property = property
                        tenant.save()

                        lease_rent = form.cleaned_data.get('lease_rent')
                        currency = form.cleaned_data.get('currency')
                        date = form.cleaned_data.get('lease_start')

                        lease_rent = Lease_rent(
                            tenant = tenant,
                            date_rent_set = date,
                            currency = currency,
                            rent = lease_rent,
                        )

                        lease_rent.save()
                        return JsonResponse({'message': 'Tenant created successfully'}, status=200)
                    else:
                        return JsonResponse({'errors': form.errors}, status=400)
                else:
                    return JsonResponse({'error': 'You do not have permission to access this property'}, status=403)
            case 'transaction':
                if request.user.is_landlord:
                    form = TransactionForm(Landlord.objects.get(user=request.user), request.POST)
                    print(form.errors)
                    if form.is_valid():
                        transaction = form.save(commit=False)
                        # Retrieve the property ID from the form data
                        property_id = request.POST.get('property')
                        tenant_id = request.POST.get('tenant')
                        transaction.amount = abs(transaction.amount) if transaction.category in INCOME_CATEGORIES else -abs(transaction.amount)

                        property = get_object_or_404(Property, id=property_id)
                        transaction.property = property
                        
                        # Assign tenant if provided
                        if tenant_id:
                            tenant = get_object_or_404(Tenant, id=tenant_id)
                            # Verify tenant belongs to this property
                            if tenant.property == property:
                                transaction.tenant = tenant
                        
                        transaction.save()

                        # When adding new transaction update FX rates from Yahoo
                        FX.update_fx_rates(property_id)

                        return JsonResponse({'message': 'Transaction created successfully'}, status=200)
                    else:
                        print(form.errors)
                        return JsonResponse({'errors': form.errors}, status=400)
                else:
                    return JsonResponse({'error': 'You do not have permission to access this property'}, status=403)
            case 'propertyValuation':
                if request.user.is_landlord:
                    form = PropertyValuationForm(request.POST)
                    # print(f"645. Create_element: {request.POST.get('property')}")
                    # print(f'646 {form}')
                    if form.is_valid():
                        valuation = form.save(commit=False)
                        # Retrieve the property ID from the form data
                        property_id = request.POST.get('property')
                        # print(f"create_element: {property_id}")

                        property = get_object_or_404(Property, id=property_id)

                        valuation.property = property
                        valuation.save()

                        return JsonResponse({'message': 'Property valuation created successfully'}, status=200)
                    else:
                        print(form.errors)
                        return JsonResponse({'errors': form.errors}, status=400)
                else:
                    return JsonResponse({'error': 'You do not have permission to access this property'}, status=403)
    else:
        return HttpResponseNotAllowed(['POST'])  # Return a 405 Method Not Allowed response for other methods

@login_required
def vacate_tenant(request, tenant_id):
    """Handle tenant vacate action - set lease_end date"""
    
    if request.method == 'POST':
        try:
            tenant = Tenant.objects.get(id=tenant_id)
            
            # Check if the logged-in user is the landlord of the property
            if not request.user.is_landlord or tenant.property.owned_by.user != request.user:
                return JsonResponse({'error': 'You do not have permission to vacate this tenant'}, status=403)
            
            form = TenantVacateForm(tenant=tenant, data=request.POST)
            if form.is_valid():
                vacate_date = form.cleaned_data['vacate_date']
                
                # Set the lease_end date
                tenant.lease_end = vacate_date
                tenant.save()
                
                return JsonResponse({
                    'message': f'Tenant {tenant.first_name} {tenant.last_name} will vacate on {vacate_date.strftime("%Y-%m-%d")}',
                    'vacate_date': vacate_date.strftime("%Y-%m-%d")
                }, status=200)
            else:
                return JsonResponse({'errors': form.errors}, status=400)
                
        except Tenant.DoesNotExist:
            return JsonResponse({'error': 'Tenant not found'}, status=404)
    else:
        return JsonResponse({'error': 'Only POST method allowed'}, status=405)

# Extract property choices for Tenant form
@login_required
def property_choices(request):

    # Per-user as-of date (replaces the process-global).
    effective_current_date = get_effective_date(request.user)

    landlord = Landlord.objects.get(user=request.user)
    properties = Property.objects.filter(
            Q(tenants__isnull=True) | Q(tenants__lease_end__lte=effective_current_date),
            Q(sold__isnull=True) | Q(sold__gte=effective_current_date),
            owned_by=landlord,
        )

    if properties.exists():
        data = [[property.id, property.name] for property in properties]
    else:
        # Return a special message when no properties are available
        data = [['', 'No available properties (all properties have active tenants)']]

    return JsonResponse(data, safe=False)

@login_required
def chart_data_request(request):
    if request.method == 'GET':
        type = request.GET.get('type')
        id = request.GET.get('id')
        frequency = request.GET.get('frequency')
        from_date = request.GET.get('from')
        to_date = request.GET.get('to')
        # print(id == 'null')

        if type == 'homePage':
            landlord = Landlord.objects.get(user=request.user)
            properties = Property.objects.filter(
                Q(sold__isnull=True) | Q(sold__gte=get_effective_date(request.user)),
                owned_by=landlord)
            if id != 'null':
                properties = properties.filter(id=id)
            properties = properties.all()
            currency = request.session['default_currency']
        else:
            properties = None
            if type == 'property':
                currency = Property.objects.get(id=id).currency
            elif type == 'tenant':
                currency = Tenant.objects.get(id=id).property.currency

        chart_data = get_chart_data(type, id, frequency, from_date, to_date, currency, properties)

        return JsonResponse(chart_data)

    return JsonResponse({'error': 'Invalid request method'}, status=400)

# Chart-dataset builder.
#
# Task 12: body moved verbatim into ``rentals.services.charts.get_chart_data``.
# This shim is kept so existing callers in this module (``index``,
# ``handle_element``, ``chart_data_request``, ``property_valuation``) and the
# characterization test (``test_charts_char.py`` imports
# ``rentals.views.get_chart_data``) don't need to change. Lazy import avoids a
# module-load circular import (``services.charts`` imports ``rentals.models``
# / ``rentals.utils`` lazily for the same reason ``services.financials`` does).
def get_chart_data(type, element_id, frequency, from_date, to_date, currency, properties=None):
    from rentals.services.charts import get_chart_data as _get_chart_data
    return _get_chart_data(
        type,
        element_id,
        frequency,
        from_date,
        to_date,
        currency,
        properties=properties,
    )


# Calculate pnl for given properties.
#
# Task 11: body moved verbatim into ``rentals.services.financials.pnl_calc``.
# This shim kept so existing callers in this module (``index``,
# ``handle_element``) and the characterization test
# (``test_pnl_calc_portfolio`` calls ``views.pnl_calc``) don't need to
# change. Lazy import avoids a module-load circular import
# (``services.financials`` imports ``rentals.models`` / ``rentals.utils``
# lazily for the same reason).
def pnl_calc(properties, target_currency, default_currency_for_all_data, digits, as_of=None):
    from rentals.services.financials import pnl_calc as _pnl_calc
    return _pnl_calc(
        properties,
        target_currency,
        default_currency_for_all_data,
        digits,
        as_of=as_of,
    )

# Fetching data for property valuation
@login_required
def property_valuation(request, property_id):

    chart_settings = request.session['chart_settings']

    data = {
        'chart_settings': chart_settings
    }

    from_date = calculate_from_date(chart_settings['To'], chart_settings['timeline'])
    data['chart_settings']['From'] = from_date
    # data['chart_data'] = get_chart_data('tenant', element.id, chart_settings['frequency'], from_date, chart_settings['To'], element_currency)

    # Task 12: chart params come from request.GET (per-request) with the
    # session's chart_settings as the fallback. Previously these were
    # hardcoded to freq='M', start='2022-06-01', end='2023-09-15',
    # currency='USD' — a bug that pinned every property valuation chart
    # to the same window regardless of the user's session settings.
    settings = chart_settings
    freq = request.GET.get("freq", settings.get("frequency", "M"))
    start = request.GET.get("start", settings.get("From"))
    end = request.GET.get("end", settings.get("To"))
    currency = request.GET.get("currency", settings.get("currency", "USD"))
    data['chart_data'] = get_chart_data("property", property_id, freq, start, end, currency, None)
    print(f'property_valuation function; data: {data}')
    return JsonResponse(data)

# Compiling the table with FX data
@login_required
def update_fx_view(request):
    try:
        # Scope to properties owned by the requesting user (avoids touching
        # other users' data and limits external Yahoo Finance calls).
        all_properties = Property.objects.filter(owned_by__user=request.user)

        # Loop through each property and update FX rates
        for property_instance in all_properties:
            # Call the method to update FX rates
            FX.update_fx_rates(property_instance.id)

        # Return a success response if everything went well
        return JsonResponse({'success': True, 'message': 'FX rates updated successfully.'})
    
    except Exception as e:
        # Handle any errors and return a failure response
        return JsonResponse({'success': False, 'message': str(e)})

def chrome_devtools_config(request):
    """Handle Chrome DevTools configuration requests"""
    return JsonResponse({}, status=200)

def well_known_handler(request, path):
    """Handle .well-known requests to prevent 404 errors in logs"""
    return HttpResponse("", status=204)  # No Content


# Task 6: SPA catch-all.
#
# Serves ``spa_index.html`` (the React shell rendered through django-vite)
# for any URL not claimed by the API, admin, or template-rendered routes
# wired earlier in ``rentals/urls.py``. The React Router handles client-
# side routing; we deliberately do NOT enforce auth here — protected
# pages get a 401 from the API on first fetch and the SPA redirects.
class SpaView(TemplateView):
    """Serves the built React SPA. Falls through to index.html for client-side routing."""

    template_name = 'spa_index.html'

    def get(self, request, *args, **kwargs):
        # Optionally check auth here for protected routes — but the SPA
        # handles that client-side via API 401s.
        return super().get(request, *args, **kwargs)
