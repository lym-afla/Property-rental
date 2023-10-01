# from typing import Any
from django.db import models
from django.contrib.auth.models import AbstractUser

from .constants import CURRENCY_CHOICES, TRANSACTION_TYPES

# Amending default AbstractUser to differentiate between Landlord and Tenant
class User(AbstractUser):
    is_landlord = models.BooleanField(default=False)
    is_tenant = models.BooleanField(default=False)
    # Add additional fields as needed

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        if self.is_landlord:
            Landlord.objects.get_or_create(user=self)
        elif self.is_tenant:
            Tenant.objects.get_or_create(user=self)

class Landlord(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='landlord')

class Tenant(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='tenant', blank=True, null=True)
    
    # Fields specific to the tenant user type
    first_name = models.CharField(max_length=30)
    last_name = models.CharField(max_length=30, blank=True, null=True)
    phone = models.CharField(max_length=15)
    email = models.EmailField(blank=True, null=True)
    lease_start = models.DateField()
    lease_end = models.DateField(blank=True, null=True)
    currency = models.CharField(max_length=3, choices=CURRENCY_CHOICES, default='USD', null=True, blank=False)
    lease_rent = models.DecimalField(max_digits=10, decimal_places=2)

    def __str__(self):
        return f"{self.first_name} {self.last_name}"
    
class Property(models.Model):
    owned_by = models.ForeignKey(Landlord, on_delete=models.CASCADE, related_name='properties')
    tenant = models.OneToOneField(Tenant, on_delete=models.SET_NULL, related_name='property', blank=True, null=True)
    name = models.CharField(max_length=50)
    location = models.CharField(max_length=50)
    address = models.CharField(max_length=150, null=True, blank=True)
    num_bedrooms = models.PositiveIntegerField()
    area = models.DecimalField(max_digits=8, decimal_places=2, null=True, blank=True)
    property_value = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    currency = models.CharField(max_length=3, choices=CURRENCY_CHOICES, default='USD', null=True, blank=False)
    
    STATUS_CHOICES = (
        ('rented', 'Rented out'),
        ('not_rented', 'Idle'),
    )
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='not_rented')

    def __str__(self):
        return self.name
    
class Transaction(models.Model):
    property = models.ForeignKey(Property, on_delete=models.CASCADE, related_name='transactions')
    currency = models.CharField(max_length=3, choices=CURRENCY_CHOICES, default='USD', null=True, blank=False)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    type = models.CharField(max_length=20, choices=TRANSACTION_TYPES, default='rent')
    comment = models.TextField(max_length=250, blank=True, null=True)
    
    def __str__(self):
        return self.property.name + ": " + self.type
