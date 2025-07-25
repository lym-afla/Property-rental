from django import forms
from django.contrib.auth.forms import UserCreationForm, PasswordChangeForm
from django.forms.widgets import DateInput
from django.db.models import Q

from .models import User, Property, Tenant, Transaction, Property_capital_structure
from .constants import CURRENCY_CHOICES
from .utils import effective_current_date

class CustomUserCreationForm(UserCreationForm):
    email = forms.EmailField(required=True)
    # user_type = forms.ChoiceField(choices=[("landlord", "Landlord"), ("tenant", "Tenant")])

    class Meta:
        model = User
        fields = ('username', 'email', 'password1', 'password2')

    def save(self, commit=True):
        user = super().save(commit=False)
        user.email = self.cleaned_data["email"]

        # user_type = self.cleaned_data.get("user_type")
        user_type = 'landlord'
        if user_type == 'landlord':
            user.is_landlord = True
        elif user_type == 'tenant':
            user.is_tenant = True

        if commit:
            user.save()
        return user
        
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

class CustomPasswordChangeForm(PasswordChangeForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field_name in ['old_password', 'new_password1', 'new_password2']:
            self.fields[field_name].widget.attrs['class'] = 'form-control'

class PropertyForm(forms.ModelForm):
    # Adding elements for Property_capital_structure instance
    capital_structure_date = forms.DateField(
        label='Date',
        required=False,
        widget=forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
    )
    capital_structure_value = forms.DecimalField(
        label='Value',
        required=False,
        widget=forms.NumberInput(attrs={'class': 'form-control'}),
    )
    capital_structure_debt = forms.DecimalField(
        label='Debt',
        required=False,
        widget=forms.NumberInput(attrs={'class': 'form-control'}),
    )
    
    class Meta:
        model = Property
        fields = ['name', 'location', 'address', 'num_bedrooms', 'area', 'currency', 'capital_structure_date', 'capital_structure_value', 'capital_structure_debt']
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
            'currency': 'Currency',
            'area': 'Area (optional)',
        }

        # def save(self, commit=True):
        #     property_instance = super().save(commit)
        #     date = self.cleaned_data.get('capital_structure_date')
        #     value = self.cleaned_data.get('capital_structure_value')
        #     debt = self.cleaned_data.get('capital_structure_debt')
        #     print(f'157 of forms.py. {value, debt}')
        #     if date:
        #         capital_structure_instance = Property_capital_structure(
        #             property=property_instance,
        #             capital_structure_date=date,
        #             capital_structure_value=value,
        #             capital_structure_debt=debt,
        #         )
        #         capital_structure_instance.save()
        #         print(f'167 of form.py. {capital_structure_instance}')

        #     if commit:
        #         property_instance.save()

        #     return property_instance

class PropertyValuationForm(forms.ModelForm):
    currency = forms.ChoiceField(
        choices=CURRENCY_CHOICES, 
        widget=forms.Select(attrs={'class': 'form-control', 'disabled': 'True'}), 
        label='Currency',
        required=False
    )
    
    class Meta:
        model = Property_capital_structure
        fields = ['property', 'capital_structure_date', 'currency', 'capital_structure_value', 'capital_structure_debt']
        widgets = {
            'capital_structure_date': DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'capital_structure_value': forms.NumberInput(attrs={'class': 'form-control'}),
            'capital_structure_debt': forms.NumberInput(attrs={'class': 'form-control'}),
            'property': forms.NumberInput(attrs={'id': 'id_property_valuation'}),
        }
        labels = {
            'capital_structure_date': 'Date of entry',
            'capital_structure_value': 'Value',
            'capital_structure_debt': 'Debt',
        }

        def clean(self):
            cleaned_data = super().clean()
            value = cleaned_data.get('capital_structure_value')
            debt = cleaned_data.get('capital_structure_debt')

            if value is None and debt is None:
                raise forms.ValidationError("You must provide either 'value' or 'debt' or both.")

            return cleaned_data
        
class TenantForm(forms.ModelForm):
    lease_rent = forms.DecimalField(widget=forms.NumberInput(attrs={'class': 'form-control'}), label='Monthly rate')
    currency = forms.ChoiceField(choices=CURRENCY_CHOICES, widget=forms.Select(attrs={'class': 'form-select'}), label='Currency')

    def __init__(self, landlord_user=None, *args, **kwargs):
        super(TenantForm, self).__init__(*args, **kwargs)

        if landlord_user:
            # Customize the queryset for the property field based on the landlord user
            # Only show properties that have no tenants or tenants with expired leases
            queryset = Property.objects.filter(
                Q(tenants__isnull=True) | Q(tenants__lease_end__lte=effective_current_date),
                Q(sold__isnull=True) | Q(sold__gte=effective_current_date),
                owned_by=landlord_user,
            )
            
            # If no properties are available, replace ModelChoiceField with ChoiceField
            if not queryset.exists():
                self.fields['property'] = forms.ChoiceField(
                    choices=[('', 'No available properties (all properties have active tenants)')],
                    widget=forms.Select(attrs={'class': 'form-select', 'disabled': True}),
                    label='Select property',
                    required=False
                )
            else:
                # Set normal queryset for available properties
                self.fields['property'].queryset = queryset
                # Set the initial value to the first item in the queryset
                self.fields['property'].initial = queryset.first()
        else:
            # If no landlord_user provided, replace with ChoiceField
            self.fields['property'] = forms.ChoiceField(
                choices=[('', 'No properties available')],
                widget=forms.Select(attrs={'class': 'form-select', 'disabled': True}),
                label='Select property',
                required=False
            )
    
    def clean_property(self):
        property_instance = self.cleaned_data.get('property')
        # If it's a string (from ChoiceField), it means no properties were available
        if isinstance(property_instance, str) or not property_instance:
            if hasattr(self.fields['property'], 'queryset'):
                # This is a ModelChoiceField, so validate normally
                if not property_instance:
                    raise forms.ValidationError('Please select a valid property. If no properties are available, you need to create a property first or end existing tenant leases.')
            else:
                # This is a ChoiceField (disabled state), skip validation
                return None
        return property_instance
        
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
    tenant = forms.ModelChoiceField(queryset=Tenant.objects.none(), widget=forms.Select(attrs={'class': 'form-select'}), label='Select tenant (optional)', required=False)

    def __init__(self, landlord_user, *args, **kwargs):
        super(TransactionForm, self).__init__(*args, **kwargs)

        # Customize the queryset for the property field based on the landlord user
        self.fields['property'].queryset = Property.objects.filter(owned_by=landlord_user)
        
        # Initialize tenant field to show all tenants for properties owned by this landlord
        self.fields['tenant'].queryset = Tenant.objects.filter(property__owned_by=landlord_user)
        
    class Meta:
        model = Transaction
        fields = ['property', 'tenant', 'date', 'category', 'period', 'currency', 'amount', 'comment']
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
            'tenant': 'Select tenant (optional)',
        }

class TenantVacateForm(forms.Form):
    vacate_date = forms.DateField(
        widget=DateInput(attrs={'class': 'form-control', 'type': 'date'}),
        label='Vacate Date',
        help_text='Select the date when the tenant will vacate the property'
    )
    
    def __init__(self, tenant=None, *args, **kwargs):
        super(TenantVacateForm, self).__init__(*args, **kwargs)
        if tenant:
            # Set initial value to today, but allow past dates
            from datetime import date
            self.fields['vacate_date'].initial = date.today()
        

        
