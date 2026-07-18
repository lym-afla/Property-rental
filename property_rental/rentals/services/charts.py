"""Chart-dataset service layer.

Task 12 (Phase 1 Foundation). Moves the chart-dataset builder that used
to live in ``rentals/views.py`` as ``get_chart_data`` (the ~120-line
function consumed by the ``index``, ``handle_element`` (property +
tenant branches), ``chart_data_request`` and ``property_valuation``
views).

Public surface:

* :func:`get_chart_data` — signature unchanged from the pre-Task-12
  ``views.get_chart_data``:
  ``get_chart_data(type, element_id, frequency, from_date, to_date,
  currency, properties=None)`` returning the
  ``{'labels': [...], 'datasets': [...], 'currency': '...'}`` dict
  consumed by the front-end Chart.js harness.

Behavior preservation
---------------------
The body below is a VERBATIM copy of the pre-Task-12 ``views.get_chart_data``.
The only changes are mechanical:

1. Module-scope imports are dropped where they would create circular
   imports (``rentals.models``, ``rentals.utils``) and replaced with
   lazy imports inside the function — same pattern
   ``services.financials`` uses. ``dateutil.relativedelta.relativedelta``
   is imported eagerly at module scope (no circular risk).
2. ``django.db.models`` is imported eagerly (used for
   ``models.Sum('amount')`` in the tenant monthly branch); no circular
   risk.

Latent quirks preserved (NOT fixed here — pinned by
``test_charts_char.py``):

* The tenant branch initializes ``single_dataset_data = {'data': []}``
  with NO ``'label'`` key, so the tenant dataset comes back unlabeled
  (pinned by ``test_get_chart_data_tenant``).
* The property branch appends ``'k'`` to the currency string and
  divides values by 1000 (pinned by ``test_get_chart_data_property``).
* Decimal-vs-int mixing in dataset values (``round(Decimal, 0)`` for
  non-empty buckets vs ``int`` 0 for empty) is preserved.
* ``homePage`` is gated on truthy ``properties`` (passing ``None``
  silently yields an empty ``datasets`` list).
* ``Transaction.financials`` may still raise ``ValueError`` when
  ``currency`` is None — preserved verbatim.
"""

from dateutil.relativedelta import relativedelta
from django.db import models
from django.shortcuts import get_object_or_404


def get_chart_data(type, element_id, frequency, from_date, to_date, currency, properties=None):
    # ``Tenant``, ``Property``, ``Transaction`` are imported lazily to
    # avoid a module-load circular import (the same pattern
    # ``services.financials`` uses): ``rentals.models`` imports back into
    # the app's request path, and ``rentals.utils`` is imported by views
    # that this service delegates back to.
    from rentals.models import Property, Tenant, Transaction, FX
    from rentals.utils import (
        get_currency_symbol,
        chart_dates,
        chart_labels,
    )

    # Create an empty data dictionary
    chart_data = {
        'labels': [],
        'datasets': [],
    }

    # Get the correct starting date for "All time" category
    if type == 'tenant':
        tenant = Tenant.objects.get(id=element_id)
        if from_date == '1900-01-01':
            from_date = tenant.property.activity_start_date() - relativedelta(months=1)
    elif type == 'property':
        # Get the property or return a 404 response if not found
        property = get_object_or_404(Property, id=element_id)
        if from_date == '1900-01-01':
            from_date = property.activity_start_date() - relativedelta(months=1)
    elif type == 'homePage' and properties:
        if from_date == '1900-01-01':
            from_date = Transaction.objects.filter(property__in=properties).order_by('date').first().date

    # Create set of dates and labels for the chart
    dates = chart_dates(from_date, to_date, frequency)
    chart_data['labels']= chart_labels(dates, frequency)

    time_delta = {
        'M': 1,
        'Q': 3,
        'Y': 12
        }

    # Define currency
    chart_data['currency'] = get_currency_symbol(currency)

    if type == 'homePage' and properties:
        # Filter transactions for the specified date range
        filtered_transactions = Transaction.objects.filter(date__range=(from_date, to_date), property__in=properties)
        # Get a list of unique categories from the filtered transactions
        unique_categories = list(filtered_transactions.values_list('category', flat=True).distinct()) or []

        for category in unique_categories:
            single_dataset_data = {'label': category, 'data': []}  # Initialize for each category

            for d in dates:
                start_date = d - relativedelta(months = time_delta[frequency])
                transactions = Transaction.financials(end_date = d, target_currency=currency, properties=properties, start_date=start_date, category=category)
                single_dataset_data['data'].append(round(transactions, 0))

            chart_data['datasets'].append(single_dataset_data)

    if type == 'tenant':
        single_dataset_data = {'data': []}

        for d in dates:
            # For monthly charts, we want to show rent payments for the specific month
            # Calculate the start and end of the month for this date
            if frequency == 'M':
                # Get the start of the month
                month_start = d.replace(day=1)
                # Get the end of the month
                if d.month == 12:
                    month_end = d.replace(year=d.year + 1, month=1, day=1) - relativedelta(days=1)
                else:
                    month_end = d.replace(month=d.month + 1, day=1) - relativedelta(days=1)

                # Get rent transactions for this specific month only
                rent_transactions = Transaction.objects.filter(
                    property=tenant.property,
                    tenant=tenant,
                    category='rent',
                    date__range=(month_start, month_end)
                )

                # Calculate total for this month with currency conversion if needed
                if currency == None or tenant.property.currency == currency:
                    month_total = rent_transactions.aggregate(models.Sum('amount'))['amount__sum'] or 0
                else:
                    month_total = 0
                    for transaction in rent_transactions:
                        fx_rate = FX.get_rate(transaction.currency, currency, transaction.date)['FX']
                        month_total += transaction.amount * fx_rate

                single_dataset_data['data'].append(round(month_total, 0))
            else:
                # For non-monthly frequencies, use rent_total with include_post_vacation=True
                if frequency == 'Y':
                    # For yearly, use calendar year (Jan 1 to Dec 31)
                    year_start = d.replace(month=1, day=1)
                    year_end = d.replace(month=12, day=31)
                    total_rent = tenant.rent_total(end_date=year_end, start_date=year_start, target_currency=currency, include_post_vacation=True)
                else:
                    # For quarterly, use rolling period
                    start_date = d - relativedelta(months = time_delta[frequency])
                    total_rent = tenant.rent_total(end_date=d, start_date=start_date, target_currency=currency, include_post_vacation=True)
                single_dataset_data['data'].append(round(total_rent, 0))

        chart_data['datasets'].append(single_dataset_data)

    if type == 'property':

        # Initializing dataset for Chart.js
        datasets = [
            {
                'label': 'Debt',
                'data': [],
            },
            {
                'label': 'Equity',
                'data': [],
            },
        ]

        for d in dates:
            start_date = d - relativedelta(months = time_delta[frequency])
            value, debt = property.property_value(d)
            datasets[0]['data'].append(round(debt / 1000, 0))
            datasets[1]['data'].append(round((value - debt) / 1000, 0))

        chart_data['datasets'] = datasets
        chart_data['currency'] += 'k'

    return chart_data
