# Generated by Django 4.2.4 on 2023-10-08 16:15

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('rentals', '0027_transaction_period'),
    ]

    operations = [
        migrations.AlterField(
            model_name='transaction',
            name='period',
            field=models.CharField(blank=True, max_length=20, null=True),
        ),
    ]