# Generated by Django 4.2.4 on 2023-10-01 21:40

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('rentals', '0012_alter_transaction_amount'),
    ]

    operations = [
        migrations.AlterField(
            model_name='transaction',
            name='comment',
            field=models.TextField(blank=True, max_length=250, null=True),
        ),
    ]