"""Unit tests for ``rentals.utils`` helpers.

Task 14 added the first test here for ``calculate_from_date``'s YTD
branch. The branch previously called ``to_date.replace(months=1,
day=1)`` — ``date.replace`` does not accept ``months`` (only ``year``,
``month``, ``day``), so the call raised ``TypeError`` at runtime. The
char tests never exercised the YTD branch directly because the chart
builders feed ``'1Y'`` / ``'6m'`` / etc. through it; the YTD entry
point is the chart-settings timeline selector, which the suite
covers indirectly via ``handle_data``. This test pins the YTD
contract so the regression cannot silently return.
"""

from datetime import date

from rentals.utils import calculate_from_date


def test_calculate_from_date_ytd():
    """YTD timeline must return Jan 1 of the same year as ``to_date``.

    Regression guard for the ``to_date.replace(months=1, day=1)``
    crash — ``date.replace`` rejects ``months``. The fix uses
    ``date(to_date.year, 1, 1)``.
    """
    assert calculate_from_date(date(2025, 6, 15), "YTD") == date(2025, 1, 1)


def test_calculate_from_date_ytd_start_of_year():
    """YTD on Jan 1 must return Jan 1 of the same year (no off-by-one)."""
    assert calculate_from_date(date(2025, 1, 1), "YTD") == date(2025, 1, 1)


def test_calculate_from_date_ytd_string_input():
    """``calculate_from_date`` accepts ISO-date strings; YTD branch must
    still work after the string-to-date conversion at the top of the
    function."""
    assert calculate_from_date("2025-06-15", "YTD") == date(2025, 1, 1)
