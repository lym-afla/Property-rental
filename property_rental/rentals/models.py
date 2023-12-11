from django.db import models
from django.contrib.auth.models import AbstractUser
from django.utils import timezone
from django.core.validators import MinValueValidator, MaxValueValidator
from datetime import date
from django.db.models import Q, F
from dateutil.relativedelta import relativedelta
import networkx as nx
from django.core.validators import MaxValueValidator

from .constants import CURRENCY_CHOICES, TRANSACTION_CATEGORIES, INCOME_CATEGORIES
from .utils import effective_current_date, update_FX_database

# Amending default AbstractUser to differentiate between Landlord and Tenant
class User(AbstractUser):
    is_landlord = models.BooleanField(default=False)
    is_tenant = models.BooleanField(default=False)
    
    default_currency = models.CharField(max_length=3, choices=CURRENCY_CHOICES, default='USD', blank=True, null=True)
    use_default_currency_for_all_data = models.BooleanField(default=False)
    chart_frequency = models.CharField(max_length=1, default='M')
    chart_timeline = models.CharField(max_length=3, default='6m')
    digits = models.IntegerField(
        default=0,
        validators=[MaxValueValidator(6)],
        error_messages={
            'max_value': 'The value for digits must be less than or equal to 6.',
            }
        )
    
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
    # property_value = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
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
        
    # Calculation of the starting date of transaction activities
    def activity_start_date(self):
        return self.transactions.order_by('date').first().date
    
    def property_value(self, date):
        # Get the latest capital structure entry that is on or before the specified date
        latest_before_date_value = self.capital.filter(date__lte=date, value__isnull=False).order_by('-date').first()
        latest_before_date_debt = self.capital.filter(date__lte=date, debt__isnull=False).order_by('-date').first()

        # Get the earliest capital structure entry that is on or after the specified date
        earliest_after_date_value = self.capital.filter(date__gte=date, value__isnull=False).order_by('date').first()
        earliest_after_date_debt = self.capital.filter(date__gte=date, debt__isnull=False).order_by('date').first()

        if latest_before_date_value and earliest_after_date_value:
            # Calculate the average value between two dates
            value_before = latest_before_date_value.value
            value_after = earliest_after_date_value.value
            days_between = (earliest_after_date_value.date - latest_before_date_value.date).days
            days_to_specified_date = (date - latest_before_date_value.date).days
            average_value = value_before + (value_after - value_before) * days_to_specified_date / days_between
        elif latest_before_date_value:
            # If there is only one entry, return its value
            average_value = latest_before_date_value.value
        else:
            # No capital structure entries for value, return None or some default value
            average_value = 0

        if latest_before_date_debt and earliest_after_date_debt:
            # Calculate the average debt between two dates
            debt_before = latest_before_date_debt.debt
            debt_after = earliest_after_date_debt.debt
            days_between = (earliest_after_date_debt.date - latest_before_date_debt.date).days
            days_to_specified_date = (date - latest_before_date_debt.date).days
            average_debt = debt_before + (debt_after - debt_before) * days_to_specified_date / days_between
        elif latest_before_date_debt:
            # If there is only one entry, return its debt
            average_debt = latest_before_date_debt.debt
        else:
            # No capital structure entries for debt, return None or some default value
            average_debt = 0

        return average_value, average_debt


        # if latest_before_date_value and earliest_after_date_value:
        #     # Calculate the average value between two dates
        #     value_before = latest_before_date.value
        #     value_after = earliest_after_date.value
        #     debt_before = latest_before_date.debt
        #     debt_after = earliest_after_date.debt

        #     days_between = (earliest_after_date.date - latest_before_date.date).days
        #     days_to_specified_date = (date - latest_before_date.date).days

        #     average_value = value_before + (value_after - value_before) * days_to_specified_date / days_between
        #     average_debt = debt_before + (debt_after - debt_before) * days_to_specified_date / days_between
        #     return average_value, average_debt
        # elif latest_before_date:
        #     # If there is only one entry, return its value
        #     return latest_before_date.value, latest_before_date.debt
        # else:
        #     # No capital structure entries, return None or some default value
        #     return 0, 0
    
# Keep track of captital structure for the property
class Property_capital_structure(models.Model):
    property = models.ForeignKey(Property, on_delete=models.CASCADE, related_name='capital')
    date = models.DateField(default=timezone.now)
    value = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    debt = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)

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
    def rent_total(self, end_date, start_date=None, target_currency=None):
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

        if target_currency == None or property.currency == target_currency:
            total_rent = transactions.aggregate(models.Sum('amount'))['amount__sum'] or 0
        else:
            transactions = transactions.values('date', 'currency', 'amount').all()
            total_rent = 0
            for transaction in transactions:
                fx_rate = FX.get_rate(transaction['currency'], target_currency, transaction['date'])['FX']
                total_rent += transaction['amount'] * fx_rate

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

        return -total_rent_due
    
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
    def financials(cls, end_date, target_currency=None, properties=None, start_date=None, transaction_type=None, category=None):
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
        
        FX_conversion_required = True
        
        queryset = cls.objects.filter(date__lte=end_date)
        
        if properties:
            queryset = queryset.filter(property__in=properties)
        
        # if properties is not None and len(properties) == 1:
        #     target_currency = properties[0].currency
        #     FX_conversion_required = False
        # else:
        if target_currency is None:
            raise ValueError('Target currency is not defined')
        
        if start_date:
            queryset = queryset.filter(date__range=(start_date, end_date))
            
        if transaction_type:
            queryset = queryset.filter(type=transaction_type)
            
        if category:
            queryset = queryset.filter(category=category)
        
        transactions = queryset.values('date', 'currency', 'amount').all()
        
        total_amount = 0
        for transaction in transactions:
            
            if FX_conversion_required:
                fx_rate = FX.get_rate(transaction['currency'], target_currency, transaction['date'])['FX']
            else:
                fx_rate = 1
            total_amount += transaction['amount'] * fx_rate
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
    EURUSD = models.DecimalField(max_digits=10, decimal_places=6, blank=True, null=True)
    GBPUSD = models.DecimalField(max_digits=10, decimal_places=6, blank=True, null=True)
    USDRUB = models.DecimalField(max_digits=10, decimal_places=6, blank=True, null=True)
    
    @classmethod
    def update_fx_rates(cls):
        # Get FX model variables, except 'date'
        fx_variables = [field for field in cls._meta.get_fields() if (field.name != 'date' and field.name != 'id')]

        # Extract source and target currencies
        currency_pairs = [(field.name[:3], field.name[3:]) for field in fx_variables]

        # Scan Transaction instances in the database to collect dates
        transaction_dates = Transaction.objects.values_list('date', flat=True)

        print(f"Checking FX rates for {len(transaction_dates)} dates")
        count = 0
        for date in transaction_dates:
            count += 1
            print(f'{count} of {len(transaction_dates)}')    
            for source, target in currency_pairs:
                # Check if an FX rate exists for the date and currency pair
                existing_rate = cls.objects.filter(date=date).values(f'{source}{target}').first()

                if existing_rate is None or existing_rate[f'{source}{target}'] is None:
                    # Get the FX rate for the date
                    rate_data = update_FX_database(source, target, date)

                    if rate_data is not None:
                        # Update or create an FX instance with the new rate
                        fx_instance, created = cls.objects.get_or_create(date=rate_data['actual_date'])
                        setattr(fx_instance, f'{source}{target}', rate_data['exchange_rate'])
                        fx_instance.save()
                        print(f'{source}{target} for {rate_data["actual_date"]} is updated')
                    else:
                        raise Exception(f'{source}{target} for {rate_data["actual_date"]} is NOT updated. Yahoo Finance is not responding correctly')
                else:
                    print(f'{source}{target} for {date} already exists')
                    
    # Get FX quote for date
    @classmethod
    def get_rate(cls, source, target, date):
        fx_rate = 1
        dates_async = False
        dates_list = []

        if source == target:
            return {
                'FX': fx_rate,
                'conversions': 0,
                'dates_async': dates_async,
                'FX dates used': dates_list
            }

        # Get all existing pairs
        pairs_list = [field.name for field in FX._meta.get_fields() if (field.name != 'date' and field.name != 'id')]
        
        # Create undirected graph with currencies, import networkx library working with graphs
        G = nx.Graph()
        for entry in pairs_list:
            G.add_nodes_from([entry[:3], entry[3:]])
            G.add_edge(entry[:3], entry[3:])

        # Finding shortest path for cross-currency conversion using "Bellman-Ford" algorithm
        cross_currency = nx.shortest_path(G, source, target, method='bellman-ford')

        for i in range(1, len(cross_currency)):
            i_source = cross_currency[i - 1]
            i_target = cross_currency[i]
            
            for element in pairs_list:
                if i_source in element and i_target in element:
                    if element.find(i_source) == 0:
                        try:
                            fx_call = cls.objects.filter(date__lte=date).values('date', quote=F(f'{i_source}{i_target}')).order_by("-date").first()
                        except:
                            raise ValueError
                        fx_rate *= fx_call['quote']
                        # dates_list.append(fx_call['date'])
                        # dates_async = (dates_list[0] != fx_call['date']) or dates_async
                    else:
                        try:
                            fx_call = cls.objects.filter(date__lte=date).values('date', quote=F(f'{i_target}{i_source}')).order_by("-date").first()
                        except:
                            raise ValueError
                        fx_rate /= fx_call['quote']
                    dates_list.append(fx_call['date'])
                    dates_async = (dates_list[0] != fx_call['date']) or dates_async
                    break
        
        # Thea target is to multiply when using, not divide
        fx_rate = round(1 / fx_rate, 6)
                
        return {
            'FX': fx_rate,
            'conversions': len(cross_currency) - 1,
            'dates_async': dates_async,
            'dates': dates_list
        }
                