"""Smoke test: each factory must persist a valid instance.

If a factory fails with a NOT NULL / integrity error, the corresponding
factory in ``factories.py`` is missing a required field — re-read the
model and add a default.
"""


def test_user_factory(db):
    from rentals.tests.factories import UserFactory

    assert UserFactory().pk


def test_landlord_factory(db):
    from rentals.tests.factories import LandlordFactory

    assert LandlordFactory().pk


def test_property_factory(db):
    from rentals.tests.factories import PropertyFactory

    assert PropertyFactory().pk


def test_property_capital_structure_factory(db):
    from rentals.tests.factories import PropertyCapitalStructureFactory

    assert PropertyCapitalStructureFactory().pk


def test_tenant_factory(db):
    from rentals.tests.factories import TenantFactory

    assert TenantFactory().pk


def test_lease_rent_factory(db):
    from rentals.tests.factories import LeaseRentFactory

    assert LeaseRentFactory().pk


def test_transaction_factory(db):
    from rentals.tests.factories import TransactionFactory

    assert TransactionFactory().pk


def test_fx_factory(db):
    from rentals.tests.factories import FXFactory

    assert FXFactory().pk
