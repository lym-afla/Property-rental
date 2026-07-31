from django.contrib import admin

from .models import User, Landlord, Tenant, Property
from .oidc import ADMIN_GROUP


_django_admin_has_permission = admin.site.has_permission


def _has_lifeos_admin_permission(request):
    return _django_admin_has_permission(request) and ADMIN_GROUP in request.session.get(
        "oidc_authorized_groups", ()
    )


admin.site.has_permission = _has_lifeos_admin_permission

admin.site.register(User)
admin.site.register(Landlord)
admin.site.register(Tenant)
admin.site.register(Property)
