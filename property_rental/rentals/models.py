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
from .utils import update_FX_database

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
    name = models.CharField(max_length=50)
    location = models.CharField(max_length=50)
    address = models.CharField(max_length=150, null=True, blank=True)
    num_bedrooms = models.PositiveIntegerField()
    area = models.DecimalField(max_digits=8, decimal_places=2, null=True, blank=True)
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
        latest_before_date_value = self.capital.filter(capital_structure_date__lte=date, capital_structure_value__isnull=False).order_by('-capital_structure_date').first()
        latest_before_date_debt = self.capital.filter(capital_structure_date__lte=date, capital_structure_debt__isnull=False).order_by('-capital_structure_date').first()

        # Get the earliest capital structure entry that is after the specified date
        earliest_after_date_value = self.capital.filter(capital_structure_date__gt=date, capital_structure_value__isnull=False).order_by('capital_structure_date').first()
        earliest_after_date_debt = self.capital.filter(capital_structure_date__gt=date, capital_structure_debt__isnull=False).order_by('capital_structure_date').first()

        if latest_before_date_value and earliest_after_date_value:
            # Calculate the average value between two dates
            value_before = latest_before_date_value.capital_structure_value
            value_after = earliest_after_date_value.capital_structure_value
            days_between = (earliest_after_date_value.capital_structure_date - latest_before_date_value.capital_structure_date).days
            days_to_specified_date = (date - latest_before_date_value.capital_structure_date).days
            average_value = value_before + (value_after - value_before) * days_to_specified_date / days_between
        elif latest_before_date_value:
            # If there is only one entry, return its value
            average_value = latest_before_date_value.capital_structure_value
        else:
            # No capital structure entries for value, return None or some default value
            average_value = 0

        if latest_before_date_debt and earliest_after_date_debt:
            # Calculate the average debt between two dates
            debt_before = latest_before_date_debt.capital_structure_debt
            debt_after = earliest_after_date_debt.capital_structure_debt
            days_between = (earliest_after_date_debt.capital_structure_date - latest_before_date_debt.capital_structure_date).days
            days_to_specified_date = (date - latest_before_date_debt.capital_structure_date).days
            average_debt = debt_before + (debt_after - debt_before) * days_to_specified_date / days_between
        elif latest_before_date_debt:
            # If there is only one entry, return its debt
            average_debt = latest_before_date_debt.capital_structure_debt
        else:
            # No capital structure entries for debt, return None or some default value
            average_debt = 0

        return average_value, average_debt
    
# Keep track of captital structure for the property
class Property_capital_structure(models.Model):
    property = models.ForeignKey(Property, on_delete=models.CASCADE, related_name='capital')
    capital_structure_date = models.DateField(default=timezone.now)
    capital_structure_value = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    capital_structure_debt = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)

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
    def rent_total(self, end_date, start_date=None, target_currency=None, include_post_vacation=False):
        # Get all properties associated with this tenant
        property = self.property
        
        # Get all rent transactions for those properties
        transactions = Transaction.objects.filter(property=property, category='rent')

        if start_date is None:
            start_date = self.lease_start  # Default to self.lease_start if start_date is not provided
        else:
            start_date = max(start_date, self.lease_start)
        
        # Only limit end_date to lease_end if include_post_vacation is False
        # This allows us to see rent payments made after tenant vacated
        if self.lease_end and not include_post_vacation:
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
        
        check_date = date.today() if as_of_date is None else as_of_date
        
        # Count months from lease start to check date, considering payday
        # Rent is due on payday of each month during the lease period
        total_rent_due = 0
        
        # Start from the first month of the lease
        current_month = self.lease_start.replace(day=1)  # First day of lease start month
        
        # End at the month of check_date
        end_month = check_date.replace(day=1)  # First day of check month
        
        # If the lease ended, don't count months after lease end
        if self.lease_end:
            lease_end_month = self.lease_end.replace(day=1)
            end_month = min(end_month, lease_end_month)
        
        # Iterate through each month and check if rent is due
        while current_month <= end_month:
            # Determine the due date for this month
            try:
                # Handle edge case where payday might not exist in the month (e.g., payday=31 in February)
                if current_month.month == 2 and self.payday > 28:
                    # For February, use the last day of the month if payday doesn't exist
                    if current_month.year % 4 == 0 and (current_month.year % 100 != 0 or current_month.year % 400 == 0):
                        due_date = current_month.replace(day=29)  # Leap year
                    else:
                        due_date = current_month.replace(day=28)  # Non-leap year
                elif current_month.month in [4, 6, 9, 11] and self.payday > 30:
                    # For months with 30 days, use day 30 if payday is 31
                    due_date = current_month.replace(day=30)
                else:
                    due_date = current_month.replace(day=self.payday)
            except ValueError:
                # Fallback: use the last day of the month
                if current_month.month == 12:
                    due_date = current_month.replace(year=current_month.year + 1, month=1, day=1) - relativedelta(days=1)
                else:
                    due_date = current_month.replace(month=current_month.month + 1, day=1) - relativedelta(days=1)
            
            # Check if this rent payment is due
            rent_is_due = False
            
            if current_month == self.lease_start.replace(day=1):
                # First month: rent is due if lease started before or on the payday
                rent_is_due = self.lease_start <= due_date and due_date <= check_date
            elif current_month == check_date.replace(day=1):
                # Current month: For advance payment scenarios, be more conservative
                # Only count as due if we're past the due date by at least a few days
                # This helps avoid counting advance payments as debt
                grace_period_days = 3  # Give a few days grace for advance payments
                rent_is_due = due_date <= (check_date - relativedelta(days=grace_period_days))
            else:
                # Middle months: rent is always due (but check lease end)
                rent_is_due = True
            
            # If lease ended, check if due date is before lease end
            if self.lease_end and due_date > self.lease_end:
                rent_is_due = False
            
            if rent_is_due:
                # Get the rent rate for this month
                monthly_rate_obj = self.rent_history.filter(date_rent_set__lte=due_date).order_by('-date_rent_set').first()
                if monthly_rate_obj:
                    total_rent_due += monthly_rate_obj.rent
            
            # Move to next month
            if current_month.month == 12:
                current_month = current_month.replace(year=current_month.year + 1, month=1)
            else:
                current_month = current_month.replace(month=current_month.month + 1)
        
        total_rent_paid = self.rent_total(
            end_date=check_date, 
            start_date=self.lease_start, 
            include_post_vacation=True  # Debt calculation should not include post-vacation payments
        )
        
        # Debt is amount due minus amount paid (negative means tenant owes money)
        debt = total_rent_paid - total_rent_due
        
        return debt
    
    # Alternative debt calculation for advance payment scenarios
    def debt_advance_payment(self, as_of_date=None):
        """
        Alternative debt calculation that considers advance payments.
        For tenants who pay in advance, this method calculates debt differently:
        - Only counts completed months as "due"
        - Current month is only due if significantly past the due date
        """
        
        check_date = date.today() if as_of_date is None else as_of_date
        total_rent_due = 0
        
        # Calculate completed months (not including current month unless well past due date)
        current_month = self.lease_start.replace(day=1)
        
        # For advance payments, only count months that are definitely completed
        # Current month should not be counted unless we're well past the due date
        end_month = (check_date - relativedelta(months=1)).replace(day=1)
        
        # If lease ended, don't count months after lease end
        if self.lease_end:
            lease_end_month = self.lease_end.replace(day=1)
            end_month = min(end_month, lease_end_month)
        
        # Count completed months
        while current_month <= end_month:
            # Get rent rate for this month
            try:
                if current_month.month == 2 and self.payday > 28:
                    if current_month.year % 4 == 0 and (current_month.year % 100 != 0 or current_month.year % 400 == 0):
                        due_date = current_month.replace(day=29)
                    else:
                        due_date = current_month.replace(day=28)
                elif current_month.month in [4, 6, 9, 11] and self.payday > 30:
                    due_date = current_month.replace(day=30)
                else:
                    due_date = current_month.replace(day=self.payday)
            except ValueError:
                if current_month.month == 12:
                    due_date = current_month.replace(year=current_month.year + 1, month=1, day=1) - relativedelta(days=1)
                else:
                    due_date = current_month.replace(month=current_month.month + 1, day=1) - relativedelta(days=1)
            
            # Check if this month should count (only if within lease period)
            if current_month == self.lease_start.replace(day=1):
                # First month: only count if lease started before or on due date
                if self.lease_start <= due_date:
                    monthly_rate_obj = self.rent_history.filter(date_rent_set__lte=due_date).order_by('-date_rent_set').first()
                    if monthly_rate_obj:
                        total_rent_due += monthly_rate_obj.rent
            else:
                # Other completed months: always count
                monthly_rate_obj = self.rent_history.filter(date_rent_set__lte=due_date).order_by('-date_rent_set').first()
                if monthly_rate_obj:
                    total_rent_due += monthly_rate_obj.rent
            
            # Move to next month
            if current_month.month == 12:
                current_month = current_month.replace(year=current_month.year + 1, month=1)
            else:
                current_month = current_month.replace(month=current_month.month + 1)
        
        # Add current month only if significantly past due (for advance payment tolerance)
        current_month_start = check_date.replace(day=1)
        if current_month_start <= end_month:  # This shouldn't happen, but safety check
            pass  # Already counted above
        else:
            # Check if current month's rent should be counted
            try:
                if check_date.month == 2 and self.payday > 28:
                    if check_date.year % 4 == 0 and (check_date.year % 100 != 0 or check_date.year % 400 == 0):
                        current_due_date = check_date.replace(day=29)
                    else:
                        current_due_date = check_date.replace(day=28)
                elif check_date.month in [4, 6, 9, 11] and self.payday > 30:
                    current_due_date = check_date.replace(day=30)
                else:
                    current_due_date = check_date.replace(day=self.payday)
            except ValueError:
                current_due_date = check_date.replace(day=28)  # Fallback
            
            # Only count current month if we're significantly past due (e.g., 7+ days)
            days_past_due = (check_date - current_due_date).days
            if days_past_due >= 7:  # More conservative threshold for advance payments
                monthly_rate_obj = self.rent_history.filter(date_rent_set__lte=current_due_date).order_by('-date_rent_set').first()
                if monthly_rate_obj:
                    total_rent_due += monthly_rate_obj.rent
        
        # Calculate payments (including post-vacation payments)
        total_rent_paid = self.rent_total(
            end_date=check_date,
            start_date=self.lease_start,
            include_post_vacation=True
        )
        
        # Debt is payments minus what's due
        debt = total_rent_paid - total_rent_due
        
        return debt
    
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
        
        if properties is not None:
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
    def update_fx_rates(cls, property_id):
        # Get FX model variables, except 'date'
        fx_variables = [field for field in cls._meta.get_fields() if (field.name != 'date' and field.name != 'id')]

        # Extract source and target currencies
        currency_pairs = [(field.name[:3], field.name[3:]) for field in fx_variables]

        # Get the specific property
        property_instance = Property.objects.get(id=property_id)

        # Scan Transaction instances in the database to collect dates
        transaction_dates = property_instance.transactions.values_list('date', flat=True)

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
                        fx_instance, created = cls.objects.get_or_create(date=rate_data['requested_date'])
                        setattr(fx_instance, f'{source}{target}', rate_data['exchange_rate'])
                        fx_instance.save()
                        print(f'{source}{target} for {rate_data["requested_date"]} is updated')
                    else:
                        raise Exception(f'{source}{target} for {rate_data["requested_date"]} is NOT updated. Yahoo Finance is not responding correctly')
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

                    # Determine the correct field name for the FX pair
                    fx_field = f'{i_source}{i_target}' if element.find(i_source) == 0 else f'{i_target}{i_source}'

                    
                    # print("FX.get_rate. Inputs:", date, element, i_source, i_target)
                    # print("FX.get_rate. Database call:", cls.objects.filter(date__lte=date).values('date', quote=F(f'{i_source}{i_target}')).order_by("-date").first())
                    try:
                        # fx_call = cls.objects.filter(date__lte=date).values('date', quote=F(f'{i_source}{i_target}')).order_by("-date").first()
                        fx_call = cls.objects.filter(
                            date__lte=date
                            ).exclude(**{fx_field: None}).values('date', quote=F(fx_field)).order_by("-date").first()
                        
                        if not fx_call:
                            raise ValueError(f"FX rate for {i_source} to {i_target} not found.")
                        
                    
                        # Update fx_rate based on the direction of the conversion
                        if element.find(i_source) == 0:
                            fx_rate *= fx_call['quote']
                        else:
                            fx_rate /= fx_call['quote']

                        dates_list.append(fx_call['date'])
                        dates_async = (dates_list[0] != fx_call['date']) or dates_async
    
                    except Exception as e:
                        raise ValueError(f"Error fetching FX rate for {i_source} to {i_target}: {str(e)}")
                                        
                    break
        
        # Final result adjustment: multiply to get the final FX rate
        fx_rate = round(1 / fx_rate, 6)
                
        return {
            'FX': fx_rate,
            'conversions': len(cross_currency) - 1,
            'dates_async': dates_async,
            'dates': dates_list
        }
                