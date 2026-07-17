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
