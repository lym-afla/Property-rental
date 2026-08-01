"""Upgrade-path coverage for transaction category canonicalization."""

from datetime import date
from decimal import Decimal

import pytest
from django.db import connection
from django.db.migrations.executor import MigrationExecutor


@pytest.mark.django_db(transaction=True)
def test_latest_migration_canonicalizes_legacy_other_income_rows():
    """Upgrading an existing 0021 database must recategorize legacy income."""
    executor = MigrationExecutor(connection)
    migrate_from = [("rentals", "0021_alter_transaction_category")]
    executor.migrate(migrate_from)
    old_apps = executor.loader.project_state(migrate_from).apps

    User = old_apps.get_model("rentals", "User")
    Landlord = old_apps.get_model("rentals", "Landlord")
    Property = old_apps.get_model("rentals", "Property")
    Transaction = old_apps.get_model("rentals", "Transaction")
    user = User.objects.create(username="legacy-category-owner")
    landlord = Landlord.objects.create(user=user)
    property_ = Property.objects.create(
        owned_by=landlord,
        name="Legacy House",
        location="London",
        num_bedrooms=1,
        currency="USD",
    )
    transaction = Transaction.objects.create(
        property=property_,
        date=date(2025, 1, 1),
        category="other_income",
        currency="USD",
        amount=Decimal("250.00"),
        type="income",
    )

    executor = MigrationExecutor(connection)
    migrate_to = executor.loader.graph.leaf_nodes("rentals")
    executor.migrate(migrate_to)
    new_apps = executor.loader.project_state(migrate_to).apps
    migrated = new_apps.get_model("rentals", "Transaction").objects.get(
        pk=transaction.pk
    )

    assert migrated.category == "cost_reimbursement"
    assert migrated.type == "expense"


@pytest.mark.django_db(transaction=True)
def test_latest_migration_normalizes_legacy_predated_lease_rent_currency():
    """Predated legacy rent rows with matching native receipts should not FX-inflate expected rent."""
    executor = MigrationExecutor(connection)
    migrate_from = [("rentals", "0025_normalize_cost_reimbursement_signs")]
    executor.migrate(migrate_from)
    old_apps = executor.loader.project_state(migrate_from).apps

    User = old_apps.get_model("rentals", "User")
    Landlord = old_apps.get_model("rentals", "Landlord")
    Property = old_apps.get_model("rentals", "Property")
    Tenant = old_apps.get_model("rentals", "Tenant")
    LeaseRent = old_apps.get_model("rentals", "Lease_rent")
    Transaction = old_apps.get_model("rentals", "Transaction")

    user = User.objects.create(username="legacy-rent-owner")
    landlord = Landlord.objects.create(user=user)
    property_ = Property.objects.create(
        owned_by=landlord,
        name="Anokhina",
        location="Moscow",
        num_bedrooms=1,
        currency="RUB",
    )
    tenant = Tenant.objects.create(
        property=property_,
        first_name="Anna",
        last_name="Korshunova",
        phone="",
        lease_start=date(2025, 7, 17),
        payday=17,
    )
    legacy_rent = LeaseRent.objects.create(
        tenant=tenant,
        date_rent_set=date(2015, 7, 17),
        rent=Decimal("85000.00"),
        currency="GBP",
    )
    Transaction.objects.create(
        property=property_,
        tenant=tenant,
        date=date(2025, 7, 17),
        category="rent",
        amount=Decimal("85000.00"),
        currency="RUB",
        type="income",
    )

    cross_currency_tenant = Tenant.objects.create(
        property=property_,
        first_name="Cross",
        last_name="Currency",
        phone="",
        lease_start=date(2026, 1, 1),
        payday=1,
    )
    deliberate_foreign_rent = LeaseRent.objects.create(
        tenant=cross_currency_tenant,
        date_rent_set=date(2026, 1, 1),
        rent=Decimal("1000.00"),
        currency="GBP",
    )

    unmatched_tenant = Tenant.objects.create(
        property=property_,
        first_name="No",
        last_name="Receipt",
        phone="",
        lease_start=date(2025, 7, 17),
        payday=17,
    )
    unmatched_predated_rent = LeaseRent.objects.create(
        tenant=unmatched_tenant,
        date_rent_set=date(2015, 7, 17),
        rent=Decimal("85000.00"),
        currency="GBP",
    )

    executor = MigrationExecutor(connection)
    migrate_to = executor.loader.graph.leaf_nodes("rentals")
    executor.migrate(migrate_to)
    new_apps = executor.loader.project_state(migrate_to).apps
    MigratedLeaseRent = new_apps.get_model("rentals", "Lease_rent")

    assert MigratedLeaseRent.objects.get(pk=legacy_rent.pk).currency == "RUB"
    assert (
        MigratedLeaseRent.objects.get(pk=deliberate_foreign_rent.pk).currency
        == "GBP"
    )
    assert (
        MigratedLeaseRent.objects.get(pk=unmatched_predated_rent.pk).currency
        == "GBP"
    )
