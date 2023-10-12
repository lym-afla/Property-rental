# Generated by Django 4.2.4 on 2023-09-26 23:00

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('rentals', '0007_tenant_email_tenant_first_name_tenant_last_name_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='tenant',
            name='lease_currency',
            field=models.CharField(choices=[('USD', 'US$'), ('EUR', '€'), ('GBP', '£'), ('RUB', '₽')], default='USD', max_length=3, null=True),
        ),
    ]