"""Migration-correctness tests for the FX wide->long schema migration
(Task 9).

These are the "did the migration actually happen and is it value
preserving?" tests. They sit alongside ``test_fx_char.py`` (the golden
master of ``get_rate``) but assert about the schema shape itself, so a
regression in the migration (e.g. someone re-introducing a per-pair
column or breaking the long-format graph builder) is caught here even
if ``get_rate`` happens to return the same value by coincidence.

What's pinned here:

* The ``FX`` model exposes ``from_currency`` / ``to_currency`` / ``rate``
  / ``date`` and does NOT expose the old per-pair columns (``EURUSD`` /
  ``GBPUSD`` / ``USDRUB``).
* ``get_rate`` on the long schema returns the EXACT same values that
  ``test_fx_char.py`` pinned on the wide schema — including the tail
  inversion quirk. This re-asserts the same expected numbers as
  ``test_fx_char.py`` but builds FX rows in the new shape, so a
  regression here proves the migration drifted ``get_rate`` output.
"""

from datetime import date
from decimal import Decimal

import networkx.exception
import pytest

from rentals.models import FX


# ---------------------------------------------------------------------------
# Schema shape: long format fields exist, per-pair columns are gone
# ---------------------------------------------------------------------------

@pytest.mark.django_db
def test_fx_model_has_long_format_fields():
    """Schema migration: FX must have from_currency/to_currency/rate,
    not per-pair columns."""
    field_names = {f.name for f in FX._meta.get_fields()}
    assert "from_currency" in field_names
    assert "to_currency" in field_names
    assert "rate" in field_names
    assert "date" in field_names
    # Old per-pair columns must be gone.
    assert "EURUSD" not in field_names
    assert "GBPUSD" not in field_names
    assert "USDRUB" not in field_names


# ---------------------------------------------------------------------------
# get_rate on the long schema must produce IDENTICAL output to the wide
# schema (the values below mirror what test_fx_char.py pins).
#
# Graph:
#     EUR ---1.10--- USD ---90.00--- RUB
#                  /
#                1.25
#               /
#             GBP
# ---------------------------------------------------------------------------

_AS_OF = date(2024, 1, 15)


def build_fx_graph_long():
    """Seed the FX table with the same graph as ``test_fx_char`` but in
    the long format (one row per currency pair)."""
    FX.objects.create(
        date=date(2024, 1, 10),
        from_currency="EUR",
        to_currency="USD",
        rate=Decimal("1.10"),
    )
    FX.objects.create(
        date=date(2024, 1, 10),
        from_currency="GBP",
        to_currency="USD",
        rate=Decimal("1.25"),
    )
    FX.objects.create(
        date=date(2024, 1, 10),
        from_currency="USD",
        to_currency="RUB",
        rate=Decimal("90.00"),
    )
    return _AS_OF


@pytest.mark.django_db
def test_get_rate_direct_unchanged_after_migration():
    """get_rate('EUR','USD') must return 0.909091 (the tail inversion of
    the stored 1.10), identical to test_fx_char.test_get_rate_direct."""
    as_of = build_fx_graph_long()
    result = FX.get_rate("EUR", "USD", as_of)
    assert result["FX"] == Decimal("0.909091")
    assert result["conversions"] == 1


@pytest.mark.django_db
def test_get_rate_reverse_unchanged_after_migration():
    """get_rate('USD','EUR') must return 1.100000 (tail inversion flips
    the divide back to a multiply), identical to test_fx_char."""
    as_of = build_fx_graph_long()
    result = FX.get_rate("USD", "EUR", as_of)
    assert result["FX"] == Decimal("1.100000")
    assert result["conversions"] == 1


@pytest.mark.django_db
def test_get_rate_two_hop_unchanged_after_migration():
    """Two-hop EUR->RUB via USD must return 0.010101 (round(1/99, 6)),
    identical to test_fx_char.test_get_rate_two_hop."""
    as_of = build_fx_graph_long()
    result = FX.get_rate("EUR", "RUB", as_of)
    assert result["FX"] == Decimal("0.010101")
    assert result["conversions"] == 2


@pytest.mark.django_db
def test_get_rate_no_path_unchanged_after_migration():
    """A currency not in the graph still raises NodeNotFound verbatim."""
    as_of = build_fx_graph_long()
    with pytest.raises(networkx.exception.NodeNotFound):
        FX.get_rate("USD", "JPY", as_of)


# ---------------------------------------------------------------------------
# Cross-currency pair preserved: GBP -> USD pinned by test_financials_char
# ---------------------------------------------------------------------------

@pytest.mark.django_db
def test_get_rate_gbp_usd_matches_financials_char_pin():
    """test_financials_char pins GBP->USD = 0.800000 on the wide schema
    (stored GBPUSD=1.25, tail inversion round(1/1.25, 6) = 0.8). The long
    schema must produce the same number so the financials golden master
    stays byte-identical."""
    FX.objects.create(
        date=date(2024, 1, 1),
        from_currency="GBP",
        to_currency="USD",
        rate=Decimal("1.25"),
    )
    result = FX.get_rate("GBP", "USD", date(2024, 2, 15))
    assert result["FX"] == Decimal("0.800000")
