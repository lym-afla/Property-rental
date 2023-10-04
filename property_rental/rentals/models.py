from django.db import models
from django.contrib.auth.models import AbstractUser
from django.utils import timezone
from django.core.validators import MinValueValidator, MaxValueValidator
from datetime import date
from django.db.models import Q

from .constants import CURRENCY_CHOICES, TRANSACTION_CATEGORIES, INCOME_CATEGORIES

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
    
    STATUS_CHOICES = (
        ('rented', 'Rented out'),
        ('not_rented', 'Idle'),
    )
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='not_rented')

    def __str__(self):
        return self.name
    
    def current_tenant(self):
        return self.tenants.filter(lease_end__isnull=True).first()
    
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
        default=1,
        validators=[MinValueValidator(1), MaxValueValidator(27)]
    )
    lease_end = models.DateField(blank=True, null=True)
    currency = models.CharField(max_length=3, choices=CURRENCY_CHOICES, default='USD', null=True, blank=False)
    lease_rent = models.DecimalField(max_digits=10, decimal_places=2)

    def __str__(self):
        return f"{self.first_name} {self.last_name}"
    
    # Set payday to lease_start if not defined
    def save(self, *args, **kwargs):
        if self.payday is None:
            self.payday = self.lease_start.day
        super().save(*args, **kwargs)
    
    # Calculating total rent for the tenant between specified dates or all time if either date is not specified
    def rent_total(self, start_date=None, end_date=None):
        # Get all properties associated with this tenant
        property = self.property
        
        # Get all rent transactions for those properties
        transactions = Transaction.objects.filter(property=property, category='rent')

        if start_date and end_date:
            if self.lease_start:
                start_date = max(start_date, self.lease_start)
            if self.lease_end:
                end_date = min(end_date, self.lease_end)

            transactions = transactions.filter(date__range=(start_date, end_date))

        total_rent = transactions.aggregate(models.Sum('amount'))['amount__sum'] or 0
        return total_rent
    
    def debt(self):
        # Calculate today's date
        today = date.today()

        # # Check if the lease has ended
        # if self.lease_end and today > self.lease_end:
        #     return 0  # Tenant has moved out, no debt

        # Calculate the current month's due date based on payday
        latest_month_due = date(today.year, today.month, self.payday)
        latest_month_due.month = latest_month_due.month - 1 if self.payday > today.day else latest_month_due.month

        # # Calculate the number of days until the due date
        # days_until_due = (current_month_due - today).days

        # if days_until_due >= 0:
        #     # The rent is not yet due for this month
        #     return 0
        # else:
        #     # Calculate the start of the current month
        #     current_month_start = today.replace(day=1)



        # Calculate the number of months since lease start
        months_since_start = (
            (latest_month_due.year - self.lease_start.year) * 12
            + latest_month_due.month - self.lease_start.month
        )

        # Calculate the total rent due
        total_rent_due = months_since_start * self.lease_rent

        # Filter transactions based on the lease_end if it exists
        lease_end_filter = (
            Q(transaction_date__gte=self.lease_start)
            & (Q(transaction_date__lte=self.lease_end) | Q(lease_end__isnull=True))
        )

        # Deduct the transactions with 'rent' category
        rent_transactions = self.property.transactions.filter(lease_end_filter, category='rent')

        for transaction in rent_transactions:
            total_rent_due -= transaction.amount

        return total_rent_due
    
    def lease_rent(self, date):
        rent_history = self.rent_history.filter(date_rent_set__lte=date).order_by('-date_rent_set')
        if rent_history.exists():
            return rent_history.first().rent
        else:
            return 'No rent history for the Tenant'

class Lease_rent(models.Model):
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, related_name='rent_history')
    date_rent_set = models.DateField(null=False, blank=False)
    rent = models.DecimalField(max_digits=10, decimal_places=2)
    
class Transaction(models.Model):
    date = models.DateField(default=timezone.now)
    property = models.ForeignKey(Property, on_delete=models.CASCADE, related_name='transactions')
    category = models.CharField(max_length=20, choices=TRANSACTION_CATEGORIES, default='rent')
    currency = models.CharField(max_length=3, choices=CURRENCY_CHOICES, default='USD', null=True, blank=False)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    
    TRANSACTION_TYPES = (
        ('income', 'Income'),
        ('expense', 'Expense'),
    )
    
    type = models.CharField(max_length=20, choices=TRANSACTION_TYPES)
    comment = models.TextField(max_length=250, blank=True, null=True)
    
    @classmethod
    def financials(cls, properties=None, start_date=None, end_date=None, transaction_type='income'):
        """
        Calculate the sum of transactions for a specific period and type.

        Args:
            properties (database instances): Iterable selection of properties to check cash flows for.
            start_date: Defines the start date for the obsevation period. All-time if not defined.
            end_date: Defines the end date for the obsevation period. All-time if not defined
            transaction_type (str): 'income' or 'expense'.

        Returns:
            Decimal: The total sum of transactions.
        """
        queryset = cls.objects.filter(type=transaction_type)
        
        if properties:
            queryset = queryset.filter(property__in=properties)
        
        if start_date and end_date:
            queryset = queryset.filter(date__range=(start_date, end_date))
        
        total_amount = queryset.aggregate(models.Sum('amount'))['amount__sum'] or 0
        return total_amount
    
    def __str__(self):
        return self.property.name + ": " + self.type

    def save(self, *args, **kwargs):
        # Automatically set the 'type' field based on the 'category' field
        if self.category in INCOME_CATEGORIES:  # Replace with your category values
            self.type = 'income'
        else:
            self.type = 'expense'
        
        super(Transaction, self).save(*args, **kwargs)
        