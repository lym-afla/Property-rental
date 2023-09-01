from django import forms
from django.contrib.auth.forms import UserCreationForm

from .models import User, Property

class CustomUserCreationForm(UserCreationForm):
    email = forms.EmailField(required=True)
    user_type = forms.ChoiceField(choices=[("landlord", "Landlord"), ("tenant", "Tenant")])

    class Meta:
        model = User
        fields = ('username', 'email', 'password1', 'password2')

class PropertyForm(forms.ModelForm):
    class Meta:
        model = Property
        fields = ['name', 'location', 'num_bedrooms', 'area', 'value_currency', 'property_value']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'location': forms.TextInput(attrs={'class': 'form-control'}),
            'num_bedrooms': forms.NumberInput(attrs={'class': 'form-control'}),
            'area': forms.NumberInput(attrs={'class': 'form-control'}),
            'value_currency': forms.Select(attrs={'class': 'form-select'}),
            'property_value': forms.NumberInput(attrs={'class': 'form-control'}),
        }
        labels = {
            'num_bedrooms': 'Number of bedrooms',
            'value_currency': '',
            'property_value': 'Value (optional)',
            'area': 'Area (optional)',
        }