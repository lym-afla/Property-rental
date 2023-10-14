from django.db import models
from django.contrib.auth.models import AbstractUser
from django.utils import timezone
from django.core.validators import MinValueValidator, MaxValueValidator
from datetime import date
from django.db.models import Q
from dateutil.relativedelta import relativedelta

from .constants import CURRENCY_CHOICES, TRANSACTION_CATEGORIES, INCOME_CATEGORIES
from .utils import effective_current_date, get_currency_exchange_rate

# Amending default AbstractUser to differentiate between Landlord and Tenant
class User(AbstractUser):
    is_landlord = models.BooleanField(default=False)
    is_tenant = models.BooleanField(default=False)
    # Add additional fields as needed

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        if self.is_landlord:
            Landlord.objects.get_or_create(user=self)
        elif self.is_tenant:
            Tenant.objects.get_or_create(user=self)

class Landlord(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='landlord')

class Property(models.Model):
    owned_by = models.ForeignKey(Landlord, on_delete=models.CASCADE, related_name='properties')
    # tenants = models.ForeignKey(Tenant, on_delete=models.SET_NULL, related_name='property', blank=True, null=True)
    name = models.CharField(max_length=50)
    location = models.CharField(max_length=50)
    address = models.CharField(max_length=150, null=True, blank=True)
    num_bedrooms = models.PositiveIntegerField()
    area = models.DecimalField(max_digits=8, decimal_places=2, null=True, blank=True)
    property_value = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    currency = models.CharField(max_length=3, choices=CURRENCY_CHOICES, default='USD', null=True, blank=False)
    sold = models.DateField(null=True, blank=True)

    def __str__(self):
        return self.name
    
    def current_tenant(self, date):
        return self.tenants.filter(Q(lease_end__isnull=True) | Q(lease_end__gte=date)).first()
    
    def status(self, date):
        if self.tenants.filter(Q(lease_end__isnull=True) | Q(lease_end__gte=date)).exists():
            return 'Rented out'
        else:
            return 'Idle'
    
class Tenant(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='tenant', blank=True, null=True)
    
    # Fields specific to the tenant user type
    property = models.ForeignKey(Property, on_delete=models.CASCADE, related_name='tenants')
    first_name = models.CharField(max_length=30)
    last_name = models.CharField(max_length=30, blank=True, null=True)
    phone = models.CharField(max_length=15)
    email = models.EmailField(blank=True, null=True)
    lease_start = models.DateField()
    payday = models.PositiveIntegerField(
        # default=1,
        validators=[MinValueValidator(1), MaxValueValidator(27)],
        null=True,
        blank=True
    )
    lease_end = models.DateField(blank=True, null=True)
    # currency = models.CharField(max_length=3, choices=CURRENCY_CHOICES, default='USD', null=True, blank=False)
    # lease_rent = models.DecimalField(max_digits=10, decimal_places=2)

    def __str__(self):
        return f"{self.first_name} {self.last_name}"
    
    # Set payday to lease_start if not defined
    def save(self, *args, **kwargs):
        if self.payday is None:
            self.payday = self.lease_start.day
        super().save(*args, **kwargs)
    
    # Calculating total rent for the tenant between specified dates or all time if either date is not specified
    def rent_total(self, end_date, start_date=None):
        # Get all properties associated with this tenant
        property = self.property
        
        # Get all rent transactions for those properties
        transactions = Transaction.objects.filter(property=property, category='rent')

        if start_date is None:
            start_date = self.lease_start  # Default to self.lease_start if start_date is not provided
        else:
            start_date = max(start_date, self.lease_start)
        
        # if start_date and end_date:
        #     if self.lease_start:
        #         start_date = max(start_date, self.lease_start)
        # end_date = end_date if end_date is not None else effective_current_date
        if self.lease_end:
            end_date = min(end_date, self.lease_end)

        transactions = transactions.filter(date__range=(start_date, end_date))

        total_rent = transactions.aggregate(models.Sum('amount'))['amount__sum'] or 0
        return total_rent
    
    # Calculate tenant's debt for specified date
    def debt(self, as_of_date=None):
        total_rent_due = 0
        
        # Calculate start date
        start_date = self.lease_start

        # Calculate the month's due date based on payday
        check_date = date.today() if as_of_date is None else as_of_date
        latest_month_due = check_date - relativedelta(months=1) if self.payday > check_date.day else check_date
        if self.lease_end is not None:
            latest_month_due = min(latest_month_due, self.lease_end)

        while start_date <= latest_month_due:
            monthly_rate = self.rent_history.filter(date_rent_set__lte=start_date).order_by('-date_rent_set').first().rent or 0
            total_rent_due += monthly_rate
            start_date += relativedelta(months=1)

        total_rent_due -= self.rent_total(end_date=latest_month_due, start_date=self.lease_start)

        return total_rent_due
    
    # Extract lease rent for the specific date
    def lease_rent(self, as_of_date=None):
        as_of_date = as_of_date if as_of_date is not None else date.today()
        rent_history = self.rent_history.filter(date_rent_set__lte=as_of_date).order_by('-date_rent_set')
        if rent_history.exists():
            return rent_history.first().rent
        else:
            return 'No rent history for the Tenant'

class Lease_rent(models.Model):
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, related_name='rent_history')
    date_rent_set = models.DateField(null=False, blank=False)
    currency = models.CharField(max_length=3, choices=CURRENCY_CHOICES, default='USD', null=True, blank=False)
    rent = models.DecimalField(max_digits=10, decimal_places=2)
    
class Transaction(models.Model):
    date = models.DateField(default=timezone.now)
    property = models.ForeignKey(Property, on_delete=models.CASCADE, related_name='transactions')
    category = models.CharField(max_length=20, choices=TRANSACTION_CATEGORIES, default='rent')
    period = models.CharField(max_length=20, null=True, blank=True)
    currency = models.CharField(max_length=3, choices=CURRENCY_CHOICES, default='USD', null=True, blank=False)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    
    TRANSACTION_TYPES = (
        ('income', 'Income'),
        ('expense', 'Expense'),
    )
    
    type = models.CharField(max_length=20, choices=TRANSACTION_TYPES)
    comment = models.TextField(max_length=250, blank=True, null=True)
    
    @classmethod
    def financials(cls, end_date, properties=None, start_date=None, transaction_type='income'):
        """
        Calculate the sum of transactions for a specific period and type.

        Args:
            properties (database instances): Iterable selection of properties to check cash flows for.
            start_date: Defines the start date for the obsevation period. All-time if not defined.
            end_date: Defines the end date for the obsevation period.
            transaction_type (str): 'income' or 'expense'.

        Returns:
            Decimal: The total sum of transactions.
        """
        queryset = cls.objects.filter(type=transaction_type, date__lte=end_date)
        
        if properties:
            queryset = queryset.filter(property__in=properties)
        
        if start_date:
            queryset = queryset.filter(date__range=(start_date, end_date))
        
        total_amount = queryset.aggregate(models.Sum('amount'))['amount__sum'] or 0
        return total_amount
    
    def __str__(self):
        return self.property.name + ": " + self.category

    def save(self, *args, **kwargs):
        # Automatically set the 'type' field based on the 'category' field
        if self.category in INCOME_CATEGORIES:  
            self.type = 'income'
        else:
            self.type = 'expense'
            
        self.comment = '–' if not self.comment else self.comment
        
        super(Transaction, self).save(*args, **kwargs)
        
# Table with FX data
class FX(models.Model):
    __tablename__ = 'FX'
    
    date = models.DateField()
    USDEUR = models.DecimalField(max_digits=10, decimal_places=4, blank=True, null=True)
    USDGBP = models.DecimalField(max_digits=10, decimal_places=4, blank=True, null=True)
    RUBUSD = models.DecimalField(max_digits=10, decimal_places=4, blank=True, null=True)
    
    @classmethod
    def update_fx_rates(cls):
        # Get FX model variables, except 'date'
        fx_variables = [field for field in cls._meta.get_fields() if (field.name != 'date' and field.name != 'id')]
        print(fx_variables)

        # Extract source and target currencies
        currency_pairs = [(field.name[:3], field.name[3:]) for field in fx_variables]
        print(currency_pairs)

        # Scan Transaction instances in the database to collect dates
        transaction_dates = Transaction.objects.values_list('date', flat=True)

        for date in transaction_dates:
            print(f"Updating FX for {date} (toal: {len(transaction_dates)})")
            for source, target in currency_pairs:
                print(f"Updating {source}/{target} for {date}")
                # Check if an FX rate exists for the date and currency pair
                existing_rate = cls.objects.filter(date=date).values(f'{source}{target}').first()
                print(existing_rate)

                if existing_rate is None:
                    # Get the FX rate for the date
                    rate_data = get_currency_exchange_rate(source, target, date)

                    if rate_data['exchange_rate'] != 0:
                        # Update or create an FX instance with the new rate
                        fx_instance, created = FX.objects.get_or_create(date=rate_data['actual_date'])
                        setattr(fx_instance, f'{source}{target}', rate_data['exchange_rate'])
                        fx_instance.save()