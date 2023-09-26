from django.shortcuts import render, redirect, HttpResponse
from django.contrib.auth.forms import AuthenticationForm
from django.contrib.auth import login, logout
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.conf import settings
from django.http import JsonResponse, HttpResponseNotAllowed
from django.template.loader import render_to_string
import json
from rest_framework import serializers

from .forms import CustomUserCreationForm, PropertyForm, TenantForm, TransactionForm
from .models import Property, Landlord

# Using built-in serializers as the manual did not recognize currencies properly
class PropertySerializer(serializers.ModelSerializer):
    class Meta:
        model = Property
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
        
        # Form for creating new property
        form = PropertyForm(request.POST or None)
        
        if request.method == 'POST' and form.is_valid():
            property = form.save(commit=False)
            property.owned_by = Landlord.objects.get(user=request.user)
            property.save()
            
            return JsonResponse({'success': True}, status=201)
        else:
            print(form.errors)
            
        return render(request, 'rentals/properties.html', {'property_form': form})
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
        form = TransactionForm()
    else:
        messages.error(request, "Wrong form type requested")
        return redirect('rentals:index')

    return render(request, 'rentals/new_form.html', {'form': form, 'form_type': form_type})
    
# Get data to populate table with properties
@login_required
def get_properties(request):
    
    try:
        landlord = Landlord.objects.get(user=request.user)
    except Landlord.DoesNotExist:
        return JsonResponse({'error': 'Landlord does not exist.'}, status=400)
    
    properties = Property.objects.filter(owned_by=landlord)
    
    data = []  # List to store property data
    
    for property in properties:
        property_data = {
            'id': property.id,
            'name': property.name,
            'location': property.location,
            # 'rent_since': property.rent_since,
            'status': property.status
            # Add cash flow fields as needed
        }
        data.append(property_data)

    return JsonResponse(data, safe=False)

# Get data for a particular property
@login_required
def property_details(request, property_id):
    
    try:
        property = Property.objects.get(id=property_id)
        
        # Check if the logged-in user is the landlord of the property
        if request.user.is_landlord and property.owned_by.user == request.user:
            if request.method == 'GET':
                property_data = {
                    'name': property.name,
                    'location': property.location,
                    'num_bedrooms': property.num_bedrooms,
                    'area': float(property.area) if property.area else None,
                    'currency': property.value_currency,
                    'property_value': property.property_value,
                }                
                return JsonResponse(property_data, status=200)
            elif request.method == 'DELETE':
                property.delete()
                return JsonResponse({'message': 'Property deleted successfully'}, status=200)
            elif request.method == 'PUT':
                try:
                    json_data = json.loads(request.body)
                    # Retain the existing 'owned_by' value
                    json_data['owned_by'] = property.owned_by.id                    
                    serializer = PropertySerializer(instance=property, data=json_data)
                    if serializer.is_valid():
                        serializer.save()
                        return JsonResponse({'success': True}, status=200)
                    else:
                        return JsonResponse({'errors': serializer.errors}, status=400)
                except json.JSONDecodeError:
                    return JsonResponse({'error': 'Invalid JSON data in request body'}, status=400)
            else:
                return HttpResponseNotAllowed(['GET', 'PUT', 'DELETE'])  # Return a 405 Method Not Allowed response for other methods
        else:
            return JsonResponse({'error': 'You do not have permission to access this property'}, status=403)
    except Property.DoesNotExist:
        return JsonResponse({'error': 'Property not found'}, status=404)