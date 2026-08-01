from django.contrib import admin
from django.conf import settings
from django.contrib.auth.admin import UserAdmin as DjangoUserAdmin
from django.core.exceptions import PermissionDenied

from .models import User, Landlord, Tenant, Property
from .oidc import ADMIN_GROUP


_django_admin_has_permission = admin.site.has_permission


def _has_lifeos_admin_permission(request):
    return _django_admin_has_permission(request) and ADMIN_GROUP in request.session.get(
        "oidc_authorized_groups", ()
    )


admin.site.has_permission = _has_lifeos_admin_permission


class RentalUserAdmin(DjangoUserAdmin):
    """Admin projection of local users whose identity is owned by Life OS."""

    fieldsets = DjangoUserAdmin.fieldsets + (
        (
            "Rental roles",
            {"fields": ("is_landlord", "is_tenant")},
        ),
        (
            "Rent preferences",
            {
                "fields": (
                    "default_currency",
                    "use_default_currency_for_all_data",
                    "chart_frequency",
                    "chart_timeline",
                    "digits",
                    "effective_date",
                )
            },
        ),
    )
    list_display = (
        "username",
        "email",
        "first_name",
        "last_name",
        "is_staff",
        "is_landlord",
        "is_tenant",
    )

    def has_add_permission(self, request):
        if not settings.LOCAL_PASSWORD_AUTH_ENABLED:
            return False
        return super().has_add_permission(request)

    def get_readonly_fields(self, request, obj=None):
        fields = list(super().get_readonly_fields(request, obj))
        if not settings.LOCAL_PASSWORD_AUTH_ENABLED:
            fields.extend(
                ["username", "first_name", "last_name", "email", "password"]
            )
        return tuple(dict.fromkeys(fields))

    def user_change_password(self, request, id, form_url=""):
        if not settings.LOCAL_PASSWORD_AUTH_ENABLED:
            raise PermissionDenied("Django password changes are disabled in production")
        return super().user_change_password(request, id, form_url)


admin.site.register(User, RentalUserAdmin)
admin.site.register(Landlord)
admin.site.register(Tenant)
admin.site.register(Property)
