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
