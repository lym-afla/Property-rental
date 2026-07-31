from django.db import models
from django.contrib.auth.models import AbstractUser
from django.utils import timezone
from django.core.validators import MinValueValidator, MaxValueValidator
from datetime import date
from django.db.models import Q
# ``relativedelta`` was previously imported here for the month-iteration
# logic in ``Tenant.debt`` / ``Tenant.debt_advance_payment``. Task 13
# moved both bodies into ``rentals.services.scheduler``; this module no
# longer references ``relativedelta`` directly. Kept the comment instead
# of the import to make the move discoverable.
# networkx was previously imported here for the FX graph build in
# ``FX.get_rate``. Task 10 moved the graph code into
# ``rentals.services.fx``; this module no longer references ``nx``
# directly. Kept the comment instead of the import to make the move
# discoverable.
from django.core.validators import MaxValueValidator

from .constants import CURRENCY_CHOICES, TRANSACTION_CATEGORIES, INCOME_CATEGORIES
from .financial_semantics import category_kind, normalize_transaction_amount
# ``update_FX_database`` was imported here for ``FX.update_fx_rates``.
# Task 10 moved that body into ``rentals.services.fx``; the yfinance
# helper is now imported locally inside ``services.fx.update_rates``.

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
    # Per-user "as-of" date that drives every effective-date lookup in the
    # app (replaces the former process-global ``effective_current_date`` in
    # ``rentals.utils``). null=True so existing users and the migration do
    # not break; ``get_effective_date(user)`` falls back to ``date.today()``
    # when this is unset.
    effective_date = models.DateField(null=True, blank=True)

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
        
        # Get all rent transactions for this specific tenant
        # Use Q object to handle both tenant-specific transactions and legacy transactions without tenant assigned
        transactions = Transaction.objects.filter(
            property=property, 
            category='rent'
        ).filter(
            Q(tenant=self) | Q(tenant__isnull=True)
        )

        if start_date is None:
            start_date = self.lease_start  # Default to self.lease_start if start_date is not provided
        else:
            start_date = max(start_date, self.lease_start)
        
        # Only limit end_date to lease_end if include_post_vacation is False
        # This allows us to see rent payments made after tenant vacated
        if self.lease_end and not include_post_vacation:
            end_date = min(end_date, self.lease_end)

        transactions = transactions.filter(date__range=(start_date, end_date))

        # Same-currency short-circuit: when no target currency is requested or
        # it matches the property's currency, sum at face value via SQL
        # ``aggregate(Sum)``. Pinned by
        # ``test_tenant_rent_total_same_currency`` — DO NOT collapse this into
        # ``convert_transactions`` (which has a per-row short-circuit on
        # ``transaction.currency == target_currency``; the rent_total contract
        # is property-level, not per-row, and the silent fallback to face value
        # is a known latent quirk deliberately preserved here).
        if target_currency == None or property.currency == target_currency:
            total_rent = transactions.aggregate(models.Sum('amount'))['amount__sum'] or 0
        else:
            # Cross-currency path: delegate the FX loop to the canonical
            # ``services.financials.convert_transactions`` helper (Phase 1
            # Task 11). Pre-filtering (date range, category, tenant) stays
            # here; only the FX math is delegated. The helper iterates model
            # instances reading ``.amount`` / ``.currency`` / ``.date``
            # directly (no ``.values()`` projection needed) and multiplies
            # each row by ``services.fx.get_rate(...)['FX']`` when the row
            # currency differs from ``target_currency`` — identical
            # arithmetic to the inline loop it replaces.
            from rentals.services.financials import convert_transactions
            total_rent = convert_transactions(transactions.all(), target_currency, end_date)

        return total_rent
    
    # Calculate tenant's debt for specified date
    def debt(self, as_of_date=None):
        """Delegate to ``services.scheduler.debt`` (Task 13; Phase 4
        unified the two scheduler functions into one parameterized
        ``debt(tenant, as_of_date=None, method='standard')``).

        ``method='standard'`` reproduces the pre-Phase-4 behavior
        exactly: 3-day grace window for the current month. Char test
        ``test_financials_char.py::test_tenant_debt_arrears_scenario``
        pins the output to ``-2000.00``. Lazy import avoids a
        module-load circular import (``services.scheduler`` references
        ``tenant.rent_total`` / ``tenant.rent_history`` lazily at call
        time, but the import-time cycle is still safer this way and
        matches the pattern used by the other service delegates).
        """
        from rentals.services.scheduler import debt as _debt
        return _debt(self, as_of_date, method='standard')

    # Alternative debt calculation for advance payment scenarios
    def debt_advance_payment(self, as_of_date=None):
        """Delegate to ``services.scheduler.debt`` with
        ``method='advance'`` (Task 13; Phase 4 unified the two scheduler
        functions into one parameterized ``debt``).

        ``method='advance'`` reproduces the pre-Phase-4 behavior
        exactly: 7-day grace window for the current month (more
        conservative — only counts the current month as due once the
        payday is at least a week behind us). Char test
        ``test_financials_char.py::test_tenant_debt_advance_payment_scenario``
        pins the output to ``-2000.00``.
        """
        from rentals.services.scheduler import debt as _debt
        return _debt(self, as_of_date, method='advance')
    
    # Extract lease rent for the specific date
    def lease_rent(self, as_of_date=None):
        as_of_date = as_of_date if as_of_date is not None else date.today()
        
        # If tenant has been vacated before the as_of_date, return no rent
        if self.lease_end and self.lease_end < as_of_date:
            return 'Tenant vacated'
            
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
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, related_name='transactions', null=True, blank=True)
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
    def financials(cls, end_date, target_currency=None, properties=None, tenants=None, start_date=None, transaction_type=None, category=None):
        """Delegate to ``services.financials.aggregate`` (Task 11).

        Body moved verbatim into ``rentals.services.financials.aggregate``;
        the inline FX-conversion loop is replaced there by the canonical
        ``convert_transactions`` helper. Characterization tests in
        ``test_financials_char.py`` and ``test_charts_char.py`` pin the
        output byte-for-byte. Lazy import avoids a module-load circular
        import (``services.financials`` imports ``rentals.models``
        lazily for the same reason).
        """
        from rentals.services.financials import aggregate
        return aggregate(
            cls,
            end_date=end_date,
            target_currency=target_currency,
            properties=properties,
            tenants=tenants,
            start_date=start_date,
            transaction_type=transaction_type,
            category=category,
        )
    
    def __str__(self):
        return self.property.name + ": " + self.category

    def save(self, *args, **kwargs):
        self.type = category_kind(self.category)
        self.amount = normalize_transaction_amount(self.category, self.amount)
        self.comment = '–' if not self.comment else self.comment
        super(Transaction, self).save(*args, **kwargs)
        
# Table with FX data
class FXManager(models.Manager):
    """Custom manager for ``FX`` whose ``bulk_create`` emits
    ``post_save`` per created row.

    Django's stock ``QuerySet.bulk_create`` deliberately skips the
    per-row ``save()`` path AND skips ``post_save`` signals (the docs
    say so explicitly). For ``FX`` that is a problem because cache
    invalidation is signal-driven (Phase 4 Task 3): without a manual
    signal, a bulk insert would leave the graph cache stale and the
    next ``get_rate`` would return rates computed from the PRE-bulk
    snapshot. Overriding ``bulk_create`` here to emit ``post_save``
    per row closes that gap and matches the contract every other FX
    write (``save()``, ``delete()``) already satisfies.

    The override is intentionally minimal: it delegates to the parent
    ``bulk_create`` for the actual INSERT (so we keep the single-query
    performance win) and then emits one ``post_save`` per row with
    ``created=True`` and ``raw=False``. ``update_fields`` is omitted
    (it's a create, not an update).
    """

    def bulk_create(self, objs, batch_size=None, ignore_conflicts=False):
        objs = list(objs)
        # Ignore_conflicts=True can leave PKs unset on the returned
        # instances when a row was actually a no-op conflict — in that
        # case the signal handler still fires, which is the conservative
        # choice (an upsert no-op can't make the cache stale, but it
        # also can't hurt to invalidate).
        result = super().bulk_create(
            objs, batch_size=batch_size, ignore_conflicts=ignore_conflicts
        )
        # Lazy import: ``models`` is imported by ``rentals.signals`` at
        # module load, and ``signals`` is imported by ``apps.ready`` —
        # importing ``signals`` here at module scope would close a
        # circular import.
        from django.db.models.signals import post_save

        for instance in result:
            post_save.send(
                sender=self.model,
                instance=instance,
                created=True,
                raw=False,
                using=self.db,
                update_fields=None,
            )
        return result


# Table with FX data
class FX(models.Model):
    # Long format (Task 9): one row per (date, currency pair). Adding a
    # new currency pair is now a row insert, not a schema migration. The
    # graph builder in ``services.fx.get_rate`` reads
    # ``from_currency``/``to_currency`` directly instead of introspecting
    # ``_meta.fields``.
    #
    # Task 10: the graph-build + Bellman-Ford traversal lives in
    # ``rentals.services.fx`` so it can be cached (Django cache framework
    # as of Phase 4 Task 3, 2026-07-19). This model is now a thin
    # delegate: ``get_rate`` / ``update_fx_rates`` forward to the service.
    # Cache invalidation is handled by ``post_save`` / ``post_delete``
    # signal handlers in ``rentals.signals`` (registered in
    # ``RentalsConfig.ready``), so an FX write — including
    # ``bulk_create`` (via the ``FXManager`` override below) and the
    # ``save()`` / ``delete()`` paths that previously used model overrides
    # — always forces the next ``get_rate`` to rebuild.
    date = models.DateField()
    from_currency = models.CharField(max_length=3)
    to_currency = models.CharField(max_length=3)
    rate = models.DecimalField(max_digits=20, decimal_places=10)

    objects = FXManager()

    @classmethod
    def update_fx_rates(cls, property_id):
        # Delegate to ``services.fx.update_rates`` (body moved there
        # verbatim in Task 10). Kept as a classmethod so existing
        # callers (views, tests) don't need to change.
        from rentals.services.fx import update_rates
        return update_rates(property_id)

    # Get FX quote for date
    @classmethod
    def get_rate(cls, from_currency, to_currency, as_of):
        # Delegate to ``services.fx.get_rate`` — the body (Bellman-Ford
        # traversal, the unconditional tail inversion quirk, and the
        # dict return shape) moved there verbatim in Task 10. The char
        # tests in ``test_fx_char.py`` / ``test_fx_migration.py`` pin
        # the output values byte-for-byte; the cache is transparent.
        from rentals.services.fx import get_rate as _get_rate
        return _get_rate(from_currency, to_currency, as_of)
