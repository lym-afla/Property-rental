from decimal import Decimal

import pytest
from django.db import IntegrityError

from rentals.financial_semantics import deposit_signed_amount


@pytest.mark.parametrize(
    "kind,expected",
    [
        ("received", Decimal("500")),
        ("returned", Decimal("-500")),
        ("applied", Decimal("-500")),
    ],
)
def test_deposit_signed_amount(kind, expected):
    assert deposit_signed_amount(kind, Decimal("500")) == expected


def test_deposit_signed_amount_rejects_unknown_kind():
    with pytest.raises(ValueError):
        deposit_signed_amount("rent", Decimal("1"))


@pytest.mark.django_db
def test_amount_must_be_positive():
    from rentals.models import DepositMovement
    from rentals.tests.factories import TenantFactory

    with pytest.raises(IntegrityError):
        DepositMovement.objects.create(
            tenant=TenantFactory(),
            date="2026-01-01",
            kind="received",
            currency="GBP",
            amount=Decimal("0"),
        )


@pytest.mark.django_db
def test_applied_requires_applied_to():
    from rentals.models import DepositMovement
    from rentals.tests.factories import TenantFactory

    with pytest.raises(IntegrityError):
        DepositMovement.objects.create(
            tenant=TenantFactory(),
            date="2026-01-01",
            kind="applied",
            currency="GBP",
            amount=Decimal("10"),
        )
