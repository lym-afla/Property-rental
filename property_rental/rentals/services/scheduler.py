"""Tenant rent-scheduling service layer.

Task 13 (Phase 1 Foundation) moved the month-by-month debt / grace-period
calculation that used to live as two instance methods on ``Tenant`` into
this module. Phase 4 (this file's current state) unifies the two
~90%-identical bodies into a single parameterized function:

* :func:`debt` — unified debt calculation. ``method='standard'`` matches
  the old ``Tenant.debt`` body (3-day grace period; current month due
  from day 1 of the grace window). ``method='advance'`` matches the old
  ``Tenant.debt_advance_payment`` body (7-day grace period; current
  month due only when 7+ days past the payday — used for tenants who
  pay in advance).

Public surface:

* :func:`debt` — unified function. Returns
  ``total_rent_paid - total_rent_due`` (negative => tenant in arrears).

Behavior preservation
---------------------
Both ``method='standard'`` and ``method='advance'`` produce the exact
same outputs the pre-Phase-4 separate functions did — the char tests in
``test_financials_char.py`` pin both paths to ``-2000.00`` for the
arrears scenario. The unification is mechanical:

1. The two threshold values that differed between the old functions
   (grace-period days: 3 vs 7) become entries in ``_METHOD_CONFIG``.
2. The "completed months only" vs "current month included" loop shape
   is normalized to always iterate through to the current month —
   whether the current month actually accrues is then decided by the
   same ``due_date <= check_date - grace_days`` check both bodies used
   (the old ``advance`` body computed this as
   ``(check_date - current_due_date).days >= 7``, which is the same
   predicate with the threshold swapped).
3. The local ``debt`` accumulator (which shadowed the function name in
   the pre-Phase-4 bodies) is renamed to ``balance``.

``relativedelta``, ``date`` and the FK lookups (``tenant.rent_history``,
``tenant.lease_start``, ``tenant.lease_end``, ``tenant.payday``) all
resolve exactly as before.
"""

from datetime import date

from dateutil.relativedelta import relativedelta


# Per-method configuration: the ONLY two values that differed between
# the pre-Phase-4 ``debt`` and ``debt_advance_payment`` bodies. Kept at
# module scope (not inside the function) so the values are easy to audit
# alongside the docstring above. The function still takes ``method`` as
# an argument so each call is self-documenting.
_METHOD_CONFIG = {
    # The old ``Tenant.debt`` body: 3-day grace window for the current
    # month. Pinned by ``test_tenant_debt_arrears_scenario``.
    'standard': {'grace_days': 3},
    # The old ``Tenant.debt_advance_payment`` body: 7-day grace window
    # (more conservative — only counts the current month as due when the
    # payday is at least a week behind us). Pinned by
    # ``test_tenant_debt_advance_payment_scenario``.
    'advance': {'grace_days': 7},
}


def debt(tenant, as_of_date=None, method='standard'):
    """Unified debt calculation for a tenant.

    Returns ``total_rent_paid - total_rent_due`` (negative => tenant in
    arrears).

    Args:
        tenant: The ``Tenant`` instance. ``rent_total``, ``rent_history``,
            ``lease_start``, ``lease_end`` and ``payday`` are read off it.
        as_of_date: The "current" date to compute debt as of. Defaults
            to ``date.today()``.
        method: Either ``'standard'`` (3-day grace window; matches the
            pre-Phase-4 ``Tenant.debt``) or ``'advance'`` (7-day grace
            window; matches ``Tenant.debt_advance_payment``). Unknown
            values fall back to ``'standard'``.

    The two methods differ ONLY in the grace-period threshold for the
    current month: ``standard`` accrues the current month's rent once
    the payday is 3+ days behind us, ``advance`` only does so once it's
    7+ days behind. All other logic (first-month / middle-month /
    payday edge cases / lease-end cutoff / post-vacation payments) is
    shared.

    Char tests in ``test_financials_char.py`` pin both ``method='standard'``
    (``test_tenant_debt_arrears_scenario``) and ``method='advance'``
    (``test_tenant_debt_advance_payment_scenario``) to ``-2000.00``.
    Do not change the payday / grace-period logic without updating
    those pins.
    """
    config = _METHOD_CONFIG.get(method, _METHOD_CONFIG['standard'])
    grace_days = config['grace_days']

    check_date = date.today() if as_of_date is None else as_of_date

    # Accumulate the total rent that has come due as of ``check_date``
    # across every month of the lease so far.
    total_rent_due = 0

    # Start from the first month of the lease.
    current_month = tenant.lease_start.replace(day=1)
    # End at the month of check_date (the current-month branch below
    # applies the grace-day threshold, so iterating up to and including
    # the current month is correct for BOTH methods — the grace window
    # decides whether the current month actually accrues).
    end_month = check_date.replace(day=1)

    # If the lease ended, don't count months after lease end.
    if tenant.lease_end:
        lease_end_month = tenant.lease_end.replace(day=1)
        end_month = min(end_month, lease_end_month)

    # Iterate through each month and check if rent is due.
    while current_month <= end_month:
        # Determine the due date for this month, handling payday edge
        # cases (Feb with payday > 28, 30-day months with payday 31).
        try:
            if current_month.month == 2 and tenant.payday > 28:
                # February — use the last valid day for the payday.
                if current_month.year % 4 == 0 and (current_month.year % 100 != 0 or current_month.year % 400 == 0):
                    due_date = current_month.replace(day=29)  # Leap year
                else:
                    due_date = current_month.replace(day=28)  # Non-leap year
            elif current_month.month in [4, 6, 9, 11] and tenant.payday > 30:
                # 30-day months — use day 30 if payday is 31.
                due_date = current_month.replace(day=30)
            else:
                due_date = current_month.replace(day=tenant.payday)
        except ValueError:
            # Fallback: use the last day of the month.
            if current_month.month == 12:
                due_date = current_month.replace(year=current_month.year + 1, month=1, day=1) - relativedelta(days=1)
            else:
                due_date = current_month.replace(month=current_month.month + 1, day=1) - relativedelta(days=1)

        # Decide whether rent for this month has come due yet.
        rent_is_due = False

        if current_month == tenant.lease_start.replace(day=1):
            # First month of the lease: rent is due if lease started
            # before or on the payday, and the payday has passed (or is
            # within the grace window) by check_date.
            rent_is_due = tenant.lease_start <= due_date and due_date <= check_date
        elif current_month == check_date.replace(day=1):
            # Current month: only count as due if we're past the payday
            # by at least ``grace_days``. This is the single branch that
            # differs between the two methods — ``grace_days`` is 3 for
            # ``standard`` and 7 for ``advance``.
            rent_is_due = due_date <= (check_date - relativedelta(days=grace_days))
        else:
            # Middle months: rent is always due (subject to the
            # lease-end cutoff below).
            rent_is_due = True

        # If the lease ended before this month's payday, don't count it.
        if tenant.lease_end and due_date > tenant.lease_end:
            rent_is_due = False

        if rent_is_due:
            # Get the rent rate for this month (the most recent rate
            # set on or before the payday).
            monthly_rate_obj = tenant.rent_history.filter(date_rent_set__lte=due_date).order_by('-date_rent_set').first()
            if monthly_rate_obj:
                total_rent_due += monthly_rate_obj.rent

        # Move to next month.
        if current_month.month == 12:
            current_month = current_month.replace(year=current_month.year + 1, month=1)
        else:
            current_month = current_month.replace(month=current_month.month + 1)

    total_rent_paid = tenant.rent_total(
        end_date=check_date,
        start_date=tenant.lease_start,
        include_post_vacation=True
    )

    # Balance is amount paid minus amount due (negative => tenant owes).
    # Renamed from the pre-Phase-4 ``debt`` local to avoid shadowing the
    # function name.
    balance = total_rent_paid - total_rent_due

    return balance
