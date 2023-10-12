# Generated by Django 4.2.4 on 2023-09-26 23:07

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('rentals', '0008_tenant_lease_currency'),
    ]

    operations = [
        migrations.RenameField(
            model_name='property',
            old_name='value_currency',
            new_name='currency',
        ),
        migrations.RenameField(
            model_name='tenant',
            old_name='lease_currency',
            new_name='currency',
        ),
    ]
