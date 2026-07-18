import pytest
from django.urls import reverse


def test_landlord_cannot_delete_other_landlords_property(auth_client, sample_property, other_landlord_user):
    # sample_property is owned by landlord_user (the auth_client's user).
    # Attempt to delete it as other_landlord_user's session.
    from django.test import Client
    other_client = Client()
    other_client.force_login(other_landlord_user)
    url = reverse("rentals:handle_element", kwargs={"data_type": "property", "element_id": sample_property.id})
    resp = other_client.delete(url)
    assert resp.status_code == 403
    # Confirm the property still exists
    from rentals.models import Property
    assert Property.objects.filter(pk=sample_property.pk).exists()


def test_landlord_cannot_delete_other_landlords_tenant(auth_client, sample_property, other_landlord_user):
    # Tenant lives in sample_property, which is owned by landlord_user.
    # other_landlord_user must not be able to delete it.
    from django.test import Client
    from rentals.models import Tenant
    from rentals.tests.factories import TenantFactory

    tenant = TenantFactory(property=sample_property)
    other_client = Client()
    other_client.force_login(other_landlord_user)
    url = reverse("rentals:handle_element", kwargs={"data_type": "tenant", "element_id": tenant.id})
    resp = other_client.delete(url)
    assert resp.status_code == 403
    # The tenant row must survive the unauthorized delete.
    assert Tenant.objects.filter(pk=tenant.pk).exists()


def test_landlord_cannot_delete_other_landlords_transaction(auth_client, sample_property, other_landlord_user):
    # Transaction is booked against sample_property, owned by landlord_user.
    # other_landlord_user must not be able to delete it.
    from django.test import Client
    from rentals.models import Transaction
    from rentals.tests.factories import TransactionFactory

    transaction = TransactionFactory(property=sample_property, category="rent")
    other_client = Client()
    other_client.force_login(other_landlord_user)
    url = reverse("rentals:handle_element", kwargs={"data_type": "transaction", "element_id": transaction.id})
    resp = other_client.delete(url)
    assert resp.status_code == 403
    # The transaction row must survive the unauthorized delete.
    assert Transaction.objects.filter(pk=transaction.pk).exists()


def test_landlord_cannot_delete_other_landlords_property_valuation(auth_client, sample_property, other_landlord_user):
    # propertyValuation (Property_capital_structure) is attached to sample_property,
    # which is owned by landlord_user. other_landlord_user must not be able to delete it.
    from django.test import Client
    from rentals.models import Property_capital_structure
    from rentals.tests.factories import PropertyCapitalStructureFactory

    valuation = PropertyCapitalStructureFactory(property=sample_property)
    other_client = Client()
    other_client.force_login(other_landlord_user)
    url = reverse("rentals:handle_element", kwargs={"data_type": "propertyValuation", "element_id": valuation.id})
    resp = other_client.delete(url)
    assert resp.status_code == 403
    # The valuation row must survive the unauthorized delete.
    assert Property_capital_structure.objects.filter(pk=valuation.pk).exists()
