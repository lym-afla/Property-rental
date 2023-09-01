from django.contrib import admin

from .models import User, Landlord, Tenant, Property

admin.site.register(User)
admin.site.register(Landlord)
admin.site.register(Tenant)
admin.site.register(Property)