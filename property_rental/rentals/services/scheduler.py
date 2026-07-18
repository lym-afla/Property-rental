"""Tenant rent-scheduling service layer.

Task 13 (Phase 1 Foundation). Moves the month-by-month debt / grace-period
calculation that used to live as two instance methods on ``Tenant``:

* ``Tenant.debt`` (``rentals/models.py``) — the "is rent due as of this
  date?" loop with the payday edge cases (Feb, 30-day months), the
  first-month / current-month / middle-month branches, and a 3-day
  grace window for the current month.
* ``Tenant.debt_advance_payment`` (``rentals/models.py``) — the more
  conservative variant that only counts completed months plus the
  current month when ``check_date`` is 7+ days past the payday. Used for
  tenants who pay in advance.

Both bodies are moved here VERBATIM with the single mechanical change
of ``self`` -> ``tenant``. The two functions are intentionally NOT
deduplicated in this phase even though they share the large
month-iteration block: the char tests in
``test_financials_char.py`` pin both to ``-2000.00`` for the arrears
scenario, and Phase 4 will unify them once the surrounding call sites
are stable. Do not consolidate here.

Public surface:

* :func:`debt` — body of the old ``Tenant.debt``. Returns
  ``total_rent_paid - total_rent_due`` (negative => tenant in arrears).
* :func:`debt_advance_payment` — body of the old
  ``Tenant.debt_advance_payment``. Same return shape, different due-date
  rule set.

Behavior preservation
---------------------
The bodies below are copies of the pre-Task-13 code with two mechanical
changes only:

1. ``self`` -> ``tenant`` everywhere (the function's first parameter).
2. The ``self.rent_total(...)`` call becomes ``tenant.rent_total(...)``;
   ``Tenant.rent_total`` itself was moved into a service-style delegate
   only as far as needed to call through — it remains an instance method
   that takes ``self``, so passing ``tenant`` works unchanged.

``relativedelta``, ``date`` and the FK lookups (``tenant.rent_history``,
``tenant.lease_start``, ``tenant.lease_end``, ``tenant.payday``) all
resolve exactly as before. No ``self.__class__`` / ``self.objects``
usage exists in either body, so no further adjustments were required.
"""

from datetime import date

from dateutil.relativedelta import relativedelta


def debt(tenant, as_of_date=None):
    """Body moved verbatim from ``Tenant.debt`` (``self`` -> ``tenant``).

    ``rentals/tests/test_financials_char.py::test_tenant_debt_arrears_scenario``
    pins the output to ``-2000.00`` for the standard arrears scenario.
    Do not change the payday / grace-period logic without updating that
    pin.
    """

    check_date = date.today() if as_of_date is None else as_of_date

    # Count months from lease start to check date, considering payday
    # Rent is due on payday of each month during the lease period
    total_rent_due = 0

    # Start from the first month of the lease
    current_month = tenant.lease_start.replace(day=1)  # First day of lease start month

    # End at the month of check_date
    end_month = check_date.replace(day=1)  # First day of check month

    # If the lease ended, don't count months after lease end
    if tenant.lease_end:
        lease_end_month = tenant.lease_end.replace(day=1)
        end_month = min(end_month, lease_end_month)

    # Iterate through each month and check if rent is due
    while current_month <= end_month:
        # Determine the due date for this month
        try:
            # Handle edge case where payday might not exist in the month (e.g., payday=31 in February)
            if current_month.month == 2 and tenant.payday > 28:
                # For February, use the last day of the month if payday doesn't exist
                if current_month.year % 4 == 0 and (current_month.year % 100 != 0 or current_month.year % 400 == 0):
                    due_date = current_month.replace(day=29)  # Leap year
                else:
                    due_date = current_month.replace(day=28)  # Non-leap year
            elif current_month.month in [4, 6, 9, 11] and tenant.payday > 30:
                # For months with 30 days, use day 30 if payday is 31
                due_date = current_month.replace(day=30)
            else:
                due_date = current_month.replace(day=tenant.payday)
        except ValueError:
            # Fallback: use the last day of the month
            if current_month.month == 12:
                due_date = current_month.replace(year=current_month.year + 1, month=1, day=1) - relativedelta(days=1)
            else:
                due_date = current_month.replace(month=current_month.month + 1, day=1) - relativedelta(days=1)

        # Check if this rent payment is due
        rent_is_due = False

        if current_month == tenant.lease_start.replace(day=1):
            # First month: rent is due if lease started before or on the payday
            rent_is_due = tenant.lease_start <= due_date and due_date <= check_date
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
        if tenant.lease_end and due_date > tenant.lease_end:
            rent_is_due = False

        if rent_is_due:
            # Get the rent rate for this month
            monthly_rate_obj = tenant.rent_history.filter(date_rent_set__lte=due_date).order_by('-date_rent_set').first()
            if monthly_rate_obj:
                total_rent_due += monthly_rate_obj.rent

        # Move to next month
        if current_month.month == 12:
            current_month = current_month.replace(year=current_month.year + 1, month=1)
        else:
            current_month = current_month.replace(month=current_month.month + 1)

    total_rent_paid = tenant.rent_total(
        end_date=check_date,
        start_date=tenant.lease_start,
        include_post_vacation=True
    )

    # Debt is amount due minus amount paid (negative means tenant owes money)
    debt = total_rent_paid - total_rent_due

    return debt


def debt_advance_payment(tenant, as_of_date=None):
    """Body moved verbatim from ``Tenant.debt_advance_payment``
    (``self`` -> ``tenant``).

    ``rentals/tests/test_financials_char.py::test_tenant_debt_advance_payment_scenario``
    pins the output to ``-2000.00`` for the standard arrears scenario.
    Do not change the 7-day threshold / completed-months rule without
    updating that pin.
    """

    check_date = date.today() if as_of_date is None else as_of_date
    total_rent_due = 0

    # Calculate completed months (not including current month unless well past due date)
    current_month = tenant.lease_start.replace(day=1)

    # For advance payments, only count months that are definitely completed
    # Current month should not be counted unless we're well past the due date
    end_month = (check_date - relativedelta(months=1)).replace(day=1)

    # If lease ended, don't count months after lease end
    if tenant.lease_end:
        lease_end_month = tenant.lease_end.replace(day=1)
        end_month = min(end_month, lease_end_month)

    # Count completed months
    while current_month <= end_month:
        # Get rent rate for this month
        try:
            if current_month.month == 2 and tenant.payday > 28:
                if current_month.year % 4 == 0 and (current_month.year % 100 != 0 or current_month.year % 400 == 0):
                    due_date = current_month.replace(day=29)
                else:
                    due_date = current_month.replace(day=28)
            elif current_month.month in [4, 6, 9, 11] and tenant.payday > 30:
                due_date = current_month.replace(day=30)
            else:
                due_date = current_month.replace(day=tenant.payday)
        except ValueError:
            if current_month.month == 12:
                due_date = current_month.replace(year=current_month.year + 1, month=1, day=1) - relativedelta(days=1)
            else:
                due_date = current_month.replace(month=current_month.month + 1, day=1) - relativedelta(days=1)

        # Check if this month should count (only if within lease period)
        if current_month == tenant.lease_start.replace(day=1):
            # First month: only count if lease started before or on due date
            if tenant.lease_start <= due_date:
                monthly_rate_obj = tenant.rent_history.filter(date_rent_set__lte=due_date).order_by('-date_rent_set').first()
                if monthly_rate_obj:
                    total_rent_due += monthly_rate_obj.rent
        else:
            # Other completed months: always count
            monthly_rate_obj = tenant.rent_history.filter(date_rent_set__lte=due_date).order_by('-date_rent_set').first()
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
            if check_date.month == 2 and tenant.payday > 28:
                if check_date.year % 4 == 0 and (check_date.year % 100 != 0 or check_date.year % 400 == 0):
                    current_due_date = check_date.replace(day=29)
                else:
                    current_due_date = check_date.replace(day=28)
            elif check_date.month in [4, 6, 9, 11] and tenant.payday > 30:
                current_due_date = check_date.replace(day=30)
            else:
                current_due_date = check_date.replace(day=tenant.payday)
        except ValueError:
            current_due_date = check_date.replace(day=28)  # Fallback

        # Only count current month if we're significantly past due (e.g., 7+ days)
        days_past_due = (check_date - current_due_date).days
        if days_past_due >= 7:  # More conservative threshold for advance payments
            monthly_rate_obj = tenant.rent_history.filter(date_rent_set__lte=current_due_date).order_by('-date_rent_set').first()
            if monthly_rate_obj:
                total_rent_due += monthly_rate_obj.rent

    # Calculate payments (including post-vacation payments)
    total_rent_paid = tenant.rent_total(
        end_date=check_date,
        start_date=tenant.lease_start,
        include_post_vacation=True
    )

    # Debt is payments minus what's due
    debt = total_rent_paid - total_rent_due

    return debt
