from django.shortcuts import render, redirect
from django.contrib.auth.forms import AuthenticationForm
from django.contrib.auth import login, logout
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.conf import settings
from django.http import JsonResponse, HttpResponseNotAllowed
import json
from rest_framework import serializers
from datetime import date, datetime
from django.shortcuts import get_object_or_404
from django.db.models import Sum, Q
from dateutil.relativedelta import relativedelta

from .forms import CustomUserCreationForm, PropertyForm, TenantForm, TransactionForm, UserProfileForm, UserSettingsForm, PropertyValuationForm
from .models import Property, Landlord, Tenant, Transaction, Lease_rent, FX, Property_capital_structure
from .utils import get_currency_symbol, get_category_name, effective_current_date, convert_period, chart_dates, chart_labels, calculate_from_date
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

    global effective_current_date

    if request.user.is_authenticated:

        currency_basis = request.session['default_currency']

        landlord = Landlord.objects.get(user=request.user)
        properties = landlord.properties.filter(Q(sold__isnull=True) | Q(sold__gte=effective_current_date)).all()
        current_year = effective_current_date.year
        revenue_ytd = Transaction.financials(target_currency=currency_basis, end_date=effective_current_date, properties=properties, start_date=date(current_year, 1, 1), transaction_type='income')
        expense_ytd = Transaction.financials(target_currency=currency_basis, end_date=effective_current_date, properties=properties, start_date=date(current_year, 1, 1), transaction_type='expense')

        print(f'index function. properties. {properties == None}')

        debt = 0
        for property in properties:
            for tenant in property.tenants.all():
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
        expenses, rent_ytd, rent_all_time, unique_categories = pnl_calc(properties, currency_basis, True, digits)

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
        return redirect('rentals:login')

# Register new user
def register(request):

    if request.method == 'POST':
        form = CustomUserCreationForm(request.POST)
        if form.is_valid():
            form.save()
            return redirect('rentals:login')
    else:
        form = CustomUserCreationForm()

    return render(request, 'rentals/register.html', {'form': form})

# Login existing user
def login_view(request):

    if request.method == 'POST':
        form = AuthenticationForm(request, data=request.POST)
        if form.is_valid():
            user = form.get_user()
            login(request, user)

            # Store user-specific settings in the session
            request.session['chart_settings'] = {
                'frequency': user.chart_frequency,
                'timeline': user.chart_timeline,
                'To': str(effective_current_date),
            }
            request.session['default_currency'] = user.default_currency
            request.session['default_currency_for_all_data'] = user.use_default_currency_for_all_data
            request.session['digits'] = user.digits

            return redirect('rentals:index')
    else:
        form = AuthenticationForm()

    return render(request, 'rentals/login.html', {'form': form})

def logout_view(request):
    logout(request)
    return redirect('rentals:login')

@login_required
def profile_page(request):
    user = request.user
    settings_form = UserSettingsForm(instance=user)

    if request.method == 'POST':
        if 'settings_form_submit' in request.POST:
            settings_form = UserSettingsForm(request.POST, instance=user)
            if settings_form.is_valid():
                settings_form.save()

                # After saving, update the session data
                request.session['chart_settings'] = {
                    'frequency': user.chart_frequency,
                    'timeline': user.chart_timeline,
                    'To': str(effective_current_date),
                }
                request.session['default_currency'] = user.default_currency
                request.session['default_currency_for_all_data'] = user.use_default_currency_for_all_data
                request.session['digits'] = user.digits

                return JsonResponse({'success': True}, status=200)
            else:
                print(f"profile page: {settings_form.errors}")
                return JsonResponse({'errors': settings_form.errors}, status=400)

    return render(request, 'rentals/profile_page.html', {'user': user, 'settings_form': settings_form})

# User profile form
@login_required
def edit_profile(request):
    user = request.user
    profile_form = UserProfileForm(instance=user)
    # settings_form = UserSettingsForm(instance=user)

    if request.method == 'POST':
        profile_form = UserProfileForm(request.POST, instance=user)
        if profile_form.is_valid():
            print(f"Printing profile form from profile {profile_form}")
            profile_form.save()
            return redirect('rentals:profile_page')

    return render(request, 'rentals/edit_profile.html', {'profile_form': profile_form})

# Render properties page
@login_required
def properties(request):

    if request.user.is_landlord:
        return render(request, 'rentals/properties.html')#, {'property_form': form})
    else:
        messages.error(request, "You are not authorized to access this page.")
        return redirect('rentals:index')

# Render tenants page
@login_required
def tenants(request):

    if request.user.is_landlord:
        return render(request, 'rentals/tenants.html')
    else:
        messages.error(request, "You are not authorized to access this page.")
        return redirect('rentals:index')

# Render transactions page
@login_required
def transactions(request):

    if request.user.is_landlord:
        return render(request, 'rentals/transactions.html')
    else:
        messages.error(request, "You are not authorized to access this page.")
        return redirect('rentals:index')

# Create form for adding new property
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

    global effective_current_date

    try:
        landlord = Landlord.objects.get(user=request.user)
        properties_owned_by_landlord = Property.objects.filter(owned_by=landlord)
    except Landlord.DoesNotExist:
        return JsonResponse({'error': 'Landlord does not exist.'}, status=400)

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

                revenue_all_time = tenant.rent_total(effective_current_date, target_currency=tenant_currency)
                current_year = effective_current_date.year
                revenue_YTD = tenant.rent_total(start_date=date(current_year, 1, 1), end_date=date(current_year, 12, 31), target_currency=tenant_currency)

                lease_rent = tenant.lease_rent(effective_current_date)

                tenant_data = {
                    'id': tenant.id,
                    'first_name': tenant.first_name,
                    'property': tenant.property.name,
                    'lease_start': tenant.lease_start,
                    'lease_end': tenant.lease_end,
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

    global effective_current_date

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

    if request.method == 'GET':
        digits = request.session['digits']
        match data_type:
            case 'property':
                # Check if the logged-in user is the landlord of the property
                if request.user.is_landlord and element.owned_by.user == request.user:

                    # Define the currency for calculations
                    element_currency = element.currency if request.session['default_currency_for_all_data'] == False else request.session['default_currency']

                    expenses, rent_ytd, rent_all_time, unique_categories = pnl_calc([element], element_currency, request.session['default_currency_for_all_data'], digits)

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

                    lease_rent = round(element.lease_rent(effective_current_date), digits)

                    element_currency = element.property.currency if request.session['default_currency_for_all_data'] == False else request.session['default_currency']

                    data = {
                        'id': element.id,
                        'first_name': element.first_name,
                        'last_name': element.last_name,
                        'phone': element.phone,
                        'email': element.email,
                        'renting_since': element.lease_start,
                        'left_property_at': element.lease_end,
                        'rent_currency': get_currency_symbol(element_currency),
                        'rent_native_currency': get_currency_symbol(element.property.currency),
                        'rent_rate': lease_rent if type(lease_rent) == str else round(float(element.lease_rent(effective_current_date)), digits),
                        'property': element.property.name,
                        'all_time_rent': round(float(element.rent_total(end_date=effective_current_date, target_currency=element_currency)), digits),
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
                    data = {
                        'property': element.property.name,
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
        element.delete()
        return JsonResponse({'message': f'{data_type} deleted successfully'}, status=200)
    elif request.method == 'PUT':
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
                    form = TenantForm(Landlord.objects.get(user=request.user), request.POST)
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
                        transaction.amount = abs(transaction.amount) if transaction.category in INCOME_CATEGORIES else -abs(transaction.amount)

                        property = get_object_or_404(Property, id=property_id)

                        transaction.property = property
                        transaction.save()

                        # When adding new transaction update FX rates from Yahoo
                        FX.update_fx_rates()

                        return JsonResponse({'message': 'Tenant created successfully'}, status=200)
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

# Extract property choices for Tenant form
def property_choices(request):

    global  effective_current_date

    landlord = Landlord.objects.get(user=request.user)
    properties = Property.objects.filter(
            Q(tenants__isnull=True) | Q(tenants__lease_end__lte=effective_current_date),
            Q(sold__isnull=True) | Q(sold__gte=effective_current_date),
            owned_by=landlord,
        )

    data = [[property.id, property.name] for property in properties]

    return JsonResponse(data, safe=False)

# Handling effective date update
def update_date(request):

    if request.method == 'POST':

        data = json.loads(request.body)
        selectedDate = data.get('selectedDate')
        # Convert the selectedDate to a datetime variable
        formatted_date = datetime.strptime(selectedDate, "%Y-%m-%d").date()

        global effective_current_date
        effective_current_date = formatted_date
        print(f"update_date function -> effective_current_date: {effective_current_date}")
        request.session['chart_settings']['To'] = str(effective_current_date)
        print(f"update_date function -> chart_settings: {request.session['chart_settings']}")
        request.session.save()

        # # Update chart_settings['To'] with the new effective_current_date
        # global_chart_settings['To'] = effective_current_date

        # You may want to send a response with a success message
        return JsonResponse({'message': 'Date updated successfully'})

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
                Q(sold__isnull=True) | Q(sold__gte=effective_current_date),
                owned_by=landlord)
            if id != 'null':
                properties = properties.filter(id=id)
            properties = properties.all()
            currency = request.session['default_currency']
        else:
            properties = None
            if type == 'property':
                currency = Property.objects.get(id=id).currency
            elif:
                currency = Tenant.objects.get(id=id).property.currency

        chart_data = get_chart_data(type, id, frequency, from_date, to_date, currency, properties)

        return JsonResponse(chart_data)

    return JsonResponse({'error': 'Invalid request method'}, status=400)

def get_chart_data(type, element_id, frequency, from_date, to_date, currency, properties=None):

    # Create an empty data dictionary
    chart_data = {
        'labels': [],
        'datasets': [],
    }

    # Get the correct starting date for "All time" category
    if type == 'tenant':
        tenant = Tenant.objects.get(id=element_id)
        if from_date == '1900-01-01':
            from_date = tenant.property.activity_start_date() - relativedelta(months=1)
    elif type == 'property':
        # Get the property or return a 404 response if not found
        property = get_object_or_404(Property, id=element_id)
        if from_date == '1900-01-01':
            from_date = property.activity_start_date() - relativedelta(months=1)
    elif type == 'homePage' and properties:
        if from_date == '1900-01-01':
            from_date = Transaction.objects.filter(property__in=properties).order_by('date').first().date

    # Create set of dates and labels for the chart
    dates = chart_dates(from_date, to_date, frequency)
    chart_data['labels']= chart_labels(dates, frequency)

    time_delta = {
        'M': 1,
        'Q': 3,
        'Y': 12
        }

    # Define currency
    chart_data['currency'] = get_currency_symbol(currency)

    if type == 'homePage' and properties:
        # Filter transactions for the specified date range
        filtered_transactions = Transaction.objects.filter(date__range=(from_date, to_date), property__in=properties)
        # Get a list of unique categories from the filtered transactions
        unique_categories = list(filtered_transactions.values_list('category', flat=True).distinct()) or []

        for category in unique_categories:
            single_dataset_data = {'label': category, 'data': []}  # Initialize for each category

            for d in dates:
                start_date = d - relativedelta(months = time_delta[frequency])
                transactions = Transaction.financials(end_date = d, target_currency=currency, properties=properties, start_date=start_date, category=category)
                single_dataset_data['data'].append(round(transactions, 0))

            chart_data['datasets'].append(single_dataset_data)

    if type == 'tenant':


        # chart_data['currency'] = get_currency_symbol(tenant.rent_history.first().currency)

        single_dataset_data = {'data': []}

        for d in dates:
            start_date = d - relativedelta(months = time_delta[frequency])
            total_rent = tenant.rent_total(end_date=d, start_date=start_date, target_currency=currency)
            single_dataset_data['data'].append(round(total_rent, 0))

        chart_data['datasets'].append(single_dataset_data)

    if type == 'property':

        # Initializing dataset for Chart.js
        datasets = [
            {
                'label': 'Debt',
                'data': [],
            },
            {
                'label': 'Equity',
                'data': [],
            },
        ]

        for d in dates:
            start_date = d - relativedelta(months = time_delta[frequency])
            value, debt = property.property_value(d)
            datasets[0]['data'].append(round(debt / 1000, 0))
            datasets[1]['data'].append(round((value - debt) / 1000, 0))

        chart_data['datasets'] = datasets
        chart_data['currency'] += 'k'

    return chart_data


# Calculate pnl for given properties
def pnl_calc(properties, target_currency, default_currency_for_all_data, digits):

    current_year_start = effective_current_date.replace(month=1, day=1)

    # Filter transactions for the specified date range
    # filtered_transactions = element.transactions.filter(
    #     Q(date__lte=effective_current_date) &
    #     Q(type='expense')
    # )

    filtered_transactions = Transaction.objects.filter(property__in=properties, date__lte=effective_current_date, type='expense')

    # Get a list of unique categories from the filtered transactions
    unique_categories = list(filtered_transactions.values_list('category', flat=True).distinct()) or []
    # Initialize the expenses dictionary with unique categories
    expenses = {get_category_name(category): {'ytd': 0, 'all_time': 0} for category in unique_categories}
    # Add the 'total' key to the expenses dictionary
    expenses['total'] = {'ytd': 0, 'all_time': 0}

    # Adding rent category to collect in one for loop
    unique_categories.insert(0, 'rent')

    for category in unique_categories:

        cf_queryset = Transaction.objects.filter(property__in=properties, category=category)
        queryset_ytd = cf_queryset.filter(date__range=(current_year_start, effective_current_date))
        queryset_all_time = cf_queryset.filter(date__lte=effective_current_date)
        if not default_currency_for_all_data:
            cf_ytd = queryset_ytd.aggregate(Sum('amount'))['amount__sum'] or 0
            cf_all_time = queryset_all_time.aggregate(Sum('amount'))['amount__sum'] or 0
        else:
            queryset_ytd = queryset_ytd.values('date', 'currency', 'amount').all()
            cf_ytd = 0
            for transaction in queryset_ytd:
                fx_rate = FX.get_rate(transaction['currency'], target_currency, transaction['date'])['FX']
                cf_ytd += transaction['amount'] * fx_rate

            queryset_all_time = queryset_all_time.values('date', 'currency', 'amount').all()
            cf_all_time = 0
            for transaction in queryset_all_time:
                fx_rate = FX.get_rate(transaction['currency'], target_currency, transaction['date'])['FX']
                cf_all_time += transaction['amount'] * fx_rate

        if category == 'rent':
            rent_ytd = cf_ytd
            rent_all_time = cf_all_time
        else:
            category_name = get_category_name(category)
            expenses[category_name]['ytd'] = round(float(cf_ytd), digits)
            expenses[category_name]['all_time'] = round(float(cf_all_time), digits)

            expenses['total']['ytd'] += cf_ytd
            expenses['total']['all_time'] += cf_all_time

    return expenses, rent_ytd, rent_all_time, unique_categories

# Fetching data for property valuation
def property_valuation(request, property_id):

    chart_settings = request.session['chart_settings']

    data = {
        'chart_settings': chart_settings
    }

    from_date = calculate_from_date(chart_settings['To'], chart_settings['timeline'])
    data['chart_settings']['From'] = from_date
    # data['chart_data'] = get_chart_data('tenant', element.id, chart_settings['frequency'], from_date, chart_settings['To'], element_currency)

    data['chart_data'] = get_chart_data('property', property_id, 'M', '2022-06-01', '2023-09-15', 'USD', None)
    print(f'property_valuation function; data: {data}')
    return JsonResponse(data)