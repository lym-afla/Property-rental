from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.forms.widgets import DateInput
from django.db.models import Q

from .models import User, Property, Tenant, Transaction, Property_capital_structure
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
        widgets = {
            'username': forms.TextInput(attrs={'class': 'form-control'}),
            'first_name': forms.TextInput(attrs={'class': 'form-control'}),
            'last_name': forms.TextInput(attrs={'class': 'form-control'}),
            'email': forms.EmailInput(attrs={'class': 'form-control'})
        }
        labels = {
            'username': 'Username:',
            'first_name': 'First Name:',
            'last_name': 'Last Name:',
            'email': 'Email:',
        }

    # def __init__(self, *args, **kwargs):
    #     super(UserProfileForm, self).__init__(*args, **kwargs)

    #     for field_name, field in self.fields.items():
    #         field.widget.attrs['class'] = 'form-control'
        
class UserSettingsForm(forms.ModelForm):
    FREQUENCY_CHOICES = [
        ('M', 'Monthly'),
        ('Q', 'Quarterly'),
        ('Y', 'Yearly'),
    ]

    TIMELINE_CHOICES = [
        ('YTD', 'Year to Date'),
        ('3m', 'Last 3 months'),
        ('6m', 'Last 6 months'),
        ('12m', 'Last 12 months'),
        ('3Y', 'Last 3 years'),
        ('5Y', 'Last 5 years'),
        ('All', 'All history'),
        ('Custom', 'Custom'),
    ]
    
    default_currency = forms.ChoiceField(
        choices=CURRENCY_CHOICES,
        widget=forms.Select(attrs={'class': 'form-select'}),
        label='Default currency'
        )
    use_default_currency_for_all_data = forms.BooleanField(
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        label='Use default currency for all data?',
        required=False
    )
    chart_frequency = forms.ChoiceField(
        choices=FREQUENCY_CHOICES,
        widget=forms.Select(attrs={'class': 'form-select'}),
        label='Chart frequency'
    )
    chart_timeline = forms.ChoiceField(
        choices=TIMELINE_CHOICES,
        widget=forms.Select(attrs={'class': 'form-select'}),
        label='Chart timeline'
    )
    digits = forms.IntegerField(
        widget=forms.NumberInput(attrs={'class': 'form-control'}),
        label='Digits for tables'
    )
    
    class Meta:
        model = User
        fields = ['default_currency', 'use_default_currency_for_all_data', 'chart_frequency', 'chart_timeline', 'digits']
        widgets = {
            # 'chart_frequency': forms.Select(attrs={'class': 'form-select'}),
        #     'chart_timeline': forms.Select(attrs={'class': 'form-select'})
        }
        labels = {
            'digits': 'Number of digits',
        #     'chart_frequency': 'Chart frequency:',
        #     'chart_timeline': 'Chart timeline:',
        }

    def clean_digits(self):
        digits = self.cleaned_data.get('digits')
        if digits > 6:
            raise forms.ValidationError('The value for digits must be less than or equal to 6.')
        return digits

class PropertyForm(forms.ModelForm):
    class Meta:
        model = Property
        fields = ['name', 'location', 'address', 'num_bedrooms', 'area']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'location': forms.TextInput(attrs={'class': 'form-control'}),
            'address': forms.TextInput(attrs={'class': 'form-control'}),
            'num_bedrooms': forms.NumberInput(attrs={'class': 'form-control'}),
            'area': forms.NumberInput(attrs={'class': 'form-control'}),
            'currency': forms.Select(attrs={'class': 'form-select'}),
        }
        labels = {
            'address': 'Address (optional)',
            'num_bedrooms': 'Number of bedrooms',
            'currency': '',
            'area': 'Area (optional)',
        }

class PropertyValuationForm(forms.ModelForm):
    # currency = forms.ChoiceField(choices=CURRENCY_CHOICES, widget=forms.Select(attrs={'class': 'form-select'}), label='Currency')
    
    class Meta:
        model = Property_capital_structure
        fields = ['property', 'date', 'value', 'debt']
        widgets = {
            'date': DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'value': forms.NumberInput(attrs={'class': 'form-control'}),
            'debt': forms.NumberInput(attrs={'class': 'form-control'}),
            'property': forms.HiddenInput(attrs={'id': 'id_property_valuation', 'class': 'visually-hidden'}),
        }
        labels = {
            'date': 'Date of entry',
            'value': 'Value',
            'debt': 'Debt',
            'property': '',  # Empty string to hide the label
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

        
