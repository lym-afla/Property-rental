from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.forms.widgets import DateInput

from .models import User, Property, Tenant, Transaction

class CustomUserCreationForm(UserCreationForm):
    email = forms.EmailField(required=True)
    user_type = forms.ChoiceField(choices=[("landlord", "Landlord"), ("tenant", "Tenant")])

    class Meta:
        model = User
        fields = ('username', 'email', 'password1', 'password2')

class PropertyForm(forms.ModelForm):
    class Meta:
        model = Property
        fields = ['name', 'location', 'num_bedrooms', 'area', 'currency', 'property_value']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'location': forms.TextInput(attrs={'class': 'form-control'}),
            'num_bedrooms': forms.NumberInput(attrs={'class': 'form-control'}),
            'area': forms.NumberInput(attrs={'class': 'form-control'}),
            'currency': forms.Select(attrs={'class': 'form-select'}),
            'property_value': forms.NumberInput(attrs={'class': 'form-control'}),
        }
        labels = {
            'num_bedrooms': 'Number of bedrooms',
            'currency': '',
            'property_value': 'Value (optional)',
            'area': 'Area (optional)',
        }
        
class TenantForm(forms.ModelForm):
    property = forms.ModelChoiceField(queryset=Property.objects.none(), widget=forms.Select(attrs={'class': 'form-select'}), label='Select property')

    def __init__(self, landlord_user, *args, **kwargs):
        super(TenantForm, self).__init__(*args, **kwargs)

        # Customize the queryset for the property field based on the landlord user
        self.fields['property'].queryset = Property.objects.filter(owned_by=landlord_user)

    class Meta:
        model = Tenant
        fields = ['first_name', 'last_name', 'phone', 'email', 'property', 'lease_start', 'currency', 'lease_rent']
        widgets = {
            'first_name': forms.TextInput(attrs={'class': 'form-control'}),
            'last_name': forms.TextInput(attrs={'class': 'form-control'}),
            'phone': forms.TextInput(attrs={'class': 'form-control'}),
            'email': forms.EmailInput(attrs={'class': 'form-control'}),
            'lease_start': DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'currency': forms.Select(attrs={'class': 'form-select'}),
            'lease_rent': forms.NumberInput(attrs={'class': 'form-control'}),
        }
        labels = {
            'first_name': 'First name',
            'last_name': 'Last name (optional)',
            'phone': 'Phone',
            'email': 'Email (optional)',
            'lease_start': 'Lease start date',
            'currency': '',
            'lease_rent': 'Monthly rent',
        }
        
class TransactionForm(forms.ModelForm):
    class Meta:
        model = Transaction
        fields = ['type']