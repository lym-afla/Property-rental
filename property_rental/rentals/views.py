from django.shortcuts import render, redirect
from django.contrib.auth.forms import AuthenticationForm
from django.contrib.auth import login, logout
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.conf import settings
from django.http import JsonResponse, HttpResponseNotAllowed
import json
from rest_framework import serializers
from datetime import date

from .forms import CustomUserCreationForm, PropertyForm, TenantForm, TransactionForm
from .models import Property, Landlord, Tenant, Transaction
from .workings import get_currency_symbol, get_category_name
from .constants import INCOME_CATEGORIES

# Define the effective 'current' date for the application
effective_current_date = date.today()

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
    class Meta:
        model = Transaction
        fields = '__all__'
        
def index(request):
    
    if request.user.is_authenticated:
        months = ['J', 'F', 'M', 'A', 'M']
        rows = [
            {'name': 'Rent', 'cells': [{'color': 'green'}, {'color': 'green'}, {'color': 'green'}, {'color': 'red'}, {'color': 'red'}]},
            {'name': 'Tax', 'cells': [{'color': 'green'}, {'color': 'green'}, {'color': 'green'}, {'color': 'green'}, {'color': 'red'}]},
            {'name': 'Capex', 'cells': [{'color': 'green'}, {'color': 'green'}, {'color': 'green'}, {'color': 'green'}, {'color': 'green'}]},
            {'name': 'Management', 'cells': [{'color': 'green'}, {'color': 'green'}, {'color': 'red'}, {'color': 'red'}, {'color': 'red'}]},
            {'name': 'Electricity', 'cells': [{'color': 'green'}, {'color': 'green'}, {'color': 'green'}, {'color': 'red'}, {'color': 'red'}]},
            {'name': 'Utilities', 'cells': [{'color': 'green'}, {'color': 'green'}, {'color': 'green'}, {'color': 'red'}, {'color': 'red'}]},
            {'name': 'Internet', 'cells': [{'color': 'green'}, {'color': 'green'}, {'color': 'green'}, {'color': 'green'}, {'color': 'green'}]},
        ]
        
        dashboard_card_props = [
        {
            'logoLink': settings.STATIC_URL + 'rentals/img/hourglass.svg',
            'number': 'X',
            'number_text': ' months',
            'text': 'Tenant in the property',
        },
        {
            'logoLink': settings.STATIC_URL + 'rentals/img/cash-coin.svg',
            'number': '$10,000',
            'number_text': '',
            'text': 'Revenue YTD',
        },
        {
            'logoLink': settings.STATIC_URL + 'rentals/img/cash-coin.svg',
            'number': '$3,000',
            'number_text': '',
            'text': 'Income YTD',
        },
        {
            'logoLink': settings.STATIC_URL + 'rentals/img/exclamation-diamond-fill.svg',
            'number': '$1,000',
            'number_text': '',
            'text': 'Rent due',
        },
        ]
        
        return render(request, 'rentals/index.html', {
            'months': months,
            'rows': rows,
            'dashboard_card_props': dashboard_card_props,
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
            return redirect('rentals:index')
    else:
        form = AuthenticationForm()
        
    return render(request, 'rentals/login.html', {'form': form})

def logout_view(request):
    logout(request)
    return redirect('rentals:login')

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
        print(request.user)
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
    
    data = []  # List to store elements data
    
    match data_type:
        case 'property':
            for property in properties_owned_by_landlord:
                
                property_tenant = Tenant.objects.filter(property=property).order_by('lease_start').first()
                rent_since = property_tenant.lease_start if property_tenant else None
                
                
                income_all_time = Transaction.financials(properties=[property], transaction_type='income')
                expense_all_time = Transaction.financials(properties=[property], transaction_type='expense')
                
                current_year = date.today().year
                income_YTD = Transaction.financials(properties=[property], start_date=date(current_year, 1, 1), end_date=date(current_year, 12, 31), transaction_type='income')
                expense_YTD = Transaction.financials(properties=[property], start_date=date(current_year, 1, 1), end_date=date(current_year, 12, 31), transaction_type='expense')
                
                property_data = {
                    'id': property.id,
                    'name': property.name,
                    'location': property.location,
                    'rent_since': rent_since,
                    'status': property.status,
                    'income_all_time': float(income_all_time),
                    'expense_all_time': float(expense_all_time),
                    'net_income_all_time': float(income_all_time - expense_all_time),
                    'income_ytd': float(income_YTD),
                    'expense_ytd': float(expense_YTD),
                    'net_income_ytd': float(income_YTD - expense_YTD),
                    'currency': get_currency_symbol(property.currency),
                }
                data.append(property_data)
        case 'tenant':
            tenants = Tenant.objects.filter(property__in=properties_owned_by_landlord)
            for tenant in tenants:
                
                revenue_all_time = tenant.rent_total()
                current_year = date.today().year
                revenue_YTD = tenant.rent_total(start_date=date(current_year, 1, 1), end_date=date(current_year, 12, 31))
                
                tenant_data = {
                    'id': tenant.id,
                    'first_name': tenant.first_name,
                    'property': tenant.property.name,
                    'lease_start': tenant.lease_start,
                    'lease_end': tenant.lease_end,
                    'currency': get_currency_symbol(tenant.currency),
                    'lease_rent': float(tenant.lease_rent),
                    'revenue_all_time': float(revenue_all_time),
                    'revenue_ytd': float(revenue_YTD),
                    # 'debt':
                }
                data.append(tenant_data)
        case 'transaction':
            transactions = Transaction.objects.filter(property__in=properties_owned_by_landlord)
            for transaction in transactions:
                transaction_data = {
                    'id': transaction.id,
                    'transaction_date': transaction.date,
                    'property': transaction.property.name,
                    'category': get_category_name(transaction.category),
                    'currency': get_currency_symbol(transaction.currency),
                    'transaction_amount': float(transaction.amount) if transaction.amount else None,
                    'comment': transaction.comment
                }
                print(transaction_data)
                data.append(transaction_data)
        case _:
            return JsonResponse({'error': 'Data type does not exist.'}, status=400)

    return JsonResponse(data, safe=False)
    
# Get data for a particular element
@login_required
def handle_element(request, data_type, element_id):
    
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
        
    if request.method == 'GET':
        match data_type:
            case 'property':
                # Check if the logged-in user is the landlord of the property
                if request.user.is_landlord and element.owned_by.user == request.user:
                    data = {
                        'name': element.name,
                        'location': element.location,
                        'num_bedrooms': element.num_bedrooms,
                        'area': float(element.area) if element.area else None,
                        'currency': get_currency_symbol(element.currency),
                        'property_value': float(element.property_value) if element.property_value else None,
                    }
                else:
                    return JsonResponse({'error': 'You do not have permission to access this property'}, status=403) 
            case 'tenant':
                # Check if the logged-in user is the landlord and tenant lives in landlord's property
                if request.user.is_landlord and element.property.owned_by.user == request.user:
                    data = {
                        'first_name': element.first_name,
                        'last_name': element.last_name,
                        'phone': element.phone,
                        'email': element.email,
                        'renting_since': element.lease_start,
                        'left_property_at': element.lease_end,
                        'rent_currency': get_currency_symbol(element.currency),
                        'rent_rate': float(element.lease_rent) if element.lease_rent else None,
                        'property': element.property.name,
                    }
                else:
                    return JsonResponse({'error': 'You do not have permission to access this tenant'}, status=403)
            # case 'transaction':
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
            if serializer.is_valid():
                serializer.save()
                return JsonResponse({'success': True}, status=200)
            else:
                return JsonResponse({'errors': serializer.errors}, status=400)
        except json.JSONDecodeError:
            return JsonResponse({'error': 'Invalid JSON data in request body'}, status=400)
    else:
        return HttpResponseNotAllowed(['GET', 'PUT', 'DELETE', 'POST'])  # Return a 405 Method Not Allowed response for other methods
    
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
                        property = form.save(commit=False)
                        property.owned_by = Landlord.objects.get(user=request.user)
                        property.save()
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
                        
                        try:
                            # Attempt to retrieve the corresponding property
                            property = Property.objects.get(id=property_id)
                        except Property.DoesNotExist:
                            return JsonResponse({'error': 'Invalid property ID'}, status=400)
                        
                        tenant.save()
                        
                        property.tenant = tenant
                        property.status = 'rented'
                        property.save()
                        return JsonResponse({'message': 'Tenant created successfully'}, status=200)
                    else:
                        return JsonResponse({'errors': form.errors}, status=400)
                else:
                    return JsonResponse({'error': 'You do not have permission to access this property'}, status=403)
            case 'transaction':
                if request.user.is_landlord:
                    form = TransactionForm(Landlord.objects.get(user=request.user), request.POST)
                    if form.is_valid():
                        transaction = form.save(commit=False)
                        # Retrieve the property ID from the form data
                        property_id = request.POST.get('property')
                        transaction.amount = abs(transaction.amount) if transaction.category in INCOME_CATEGORIES else -abs(transaction.amount)
                        
                        try:
                            # Attempt to retrieve the corresponding property
                            property = Property.objects.get(id=property_id)
                        except Property.DoesNotExist:
                            return JsonResponse({'error': 'Invalid property ID'}, status=400)
                        
                        transaction.property = property
                        transaction.save()
                        
                        return JsonResponse({'message': 'Tenant created successfully'}, status=200)
                    else:
                        return JsonResponse({'errors': form.errors}, status=400)
                else:
                    return JsonResponse({'error': 'You do not have permission to access this property'}, status=403)
    else:
        return HttpResponseNotAllowed(['POST'])  # Return a 405 Method Not Allowed response for other methods