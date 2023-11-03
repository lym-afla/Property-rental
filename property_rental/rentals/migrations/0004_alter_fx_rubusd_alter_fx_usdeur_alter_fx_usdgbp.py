# Generated by Django 4.2.4 on 2023-10-13 17:18

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('rentals', '0003_fx'),
    ]

    operations = [
        migrations.AlterField(
            model_name='fx',
            name='RUBUSD',
            field=models.DecimalField(blank=True, decimal_places=4, max_digits=10, null=True),
        ),
        migrations.AlterField(
            model_name='fx',
            name='USDEUR',
            field=models.DecimalField(blank=True, decimal_places=4, max_digits=10, null=True),
        ),
        migrations.AlterField(
            model_name='fx',
            name='USDGBP',
            field=models.DecimalField(blank=True, decimal_places=4, max_digits=10, null=True),
        ),
    ]