from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.forms.widgets import DateInput
from django.db.models import Q

from .models import User, Property, Tenant, Transaction, Lease_rent
from .constants import CURRENCY_CHOICES
from .utils import effective_current_date

class CustomUserCreationForm(UserCreationForm):
    email = forms.EmailField(required=True)
    user_type = forms.ChoiceField(choices=[("landlord", "Landlord"), ("tenant", "Tenant")])

    class Meta:
        model = User
        fields = ('username', 'email', 'password1', 'password2')
        
class UserProfileForm(forms.ModelForm):
    class Meta:
        model = User
        fields = ['username', 'first_name', 'last_name', 'email']
        
class UserSettingsForm(forms.ModelForm):
    class Meta:
        model = User
        fields = ['default_currency', 'use_default_currency_for_all_data', 'chart_frequency', 'chart_timeline']

class PropertyForm(forms.ModelForm):
    class Meta:
        model = Property
        fields = ['name', 'location', 'address', 'num_bedrooms', 'area', 'currency', 'property_value']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'location': forms.TextInput(attrs={'class': 'form-control'}),
            'address': forms.TextInput(attrs={'class': 'form-control'}),
            'num_bedrooms': forms.NumberInput(attrs={'class': 'form-control'}),
            'area': forms.NumberInput(attrs={'class': 'form-control'}),
            'currency': forms.Select(attrs={'class': 'form-select'}),
            'property_value': forms.NumberInput(attrs={'class': 'form-control'}),
        }
        labels = {
            'address': 'Address (optional)',
            'num_bedrooms': 'Number of bedrooms',
            'currency': '',
            'property_value': 'Value (in thousands, optional)',
            'area': 'Area (optional)',
        }
        
class TenantForm(forms.ModelForm):
    lease_rent = forms.DecimalField(widget=forms.NumberInput(attrs={'class': 'form-control'}), label='Monthly rate')
    currency = forms.ChoiceField(choices=CURRENCY_CHOICES, widget=forms.Select(attrs={'class': 'form-select'}), label='Currency')

    def __init__(self, landlord_user, *args, **kwargs):
        super(TenantForm, self).__init__(*args, **kwargs)

        # Customize the queryset for the property field based on the landlord user
        queryset = Property.objects.filter(
            Q(tenants__isnull=True) | Q(tenants__lease_end__lte=effective_current_date),
            owned_by=landlord_user,
        )
        self.fields['property'].queryset = queryset
        # Set the initial value to the first item in the queryset
        if queryset.exists():
            self.fields['property'].initial = queryset.first()
        
    class Meta:
        model = Tenant
        fields = ['first_name', 'last_name', 'phone', 'email', 'property', 'lease_start', 'payday', 'currency', 'lease_rent']
        widgets = {
            'first_name': forms.TextInput(attrs={'class': 'form-control'}),
            'last_name': forms.TextInput(attrs={'class': 'form-control'}),
            'phone': forms.TextInput(attrs={'class': 'form-control'}),
            'email': forms.EmailInput(attrs={'class': 'form-control'}),
            'property': forms.Select(attrs={'class': 'form-select'}),
            'lease_start': DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'payday': forms.NumberInput(attrs={'class': 'form-control'}),
        }
        labels = {
            'first_name': 'First name',
            'last_name': 'Last name (optional)',
            'phone': 'Phone',
            'email': 'Email (optional)',
            'property': 'Select property',
            'lease_start': 'Lease start date',
            'payday': 'Payday (same as Lease start date if not defined)',
        }
        
class TransactionForm(forms.ModelForm):
    property = forms.ModelChoiceField(queryset=Property.objects.none(), widget=forms.Select(attrs={'class': 'form-select'}), label='Select property')

    def __init__(self, landlord_user, *args, **kwargs):
        super(TransactionForm, self).__init__(*args, **kwargs)

        # Customize the queryset for the property field based on the landlord user
        self.fields['property'].queryset = Property.objects.filter(owned_by=landlord_user)
        
    class Meta:
        model = Transaction
        fields = ['property', 'date', 'category', 'period', 'currency', 'amount', 'comment']
        widgets = {
            'category': forms.Select(attrs={'class': 'form-select'}),
            'currency': forms.Select(attrs={'class': 'form-select'}),
            'amount': forms.NumberInput(attrs={'class': 'form-control'}),
            'date': DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'comment': forms.Textarea(attrs={'class': 'form-control', 'rows': 4}),
            'period': DateInput(attrs={'class': 'form-control', 'type': 'month'}),
        }
        labels = {
            'category': 'Select category',
            'currency': '',
            'amount': 'Transaction value',
            'comment': 'Comment (optional)',
            'date': 'Transaction date',
            'period': 'The month and year for this transaction',
        }

        
