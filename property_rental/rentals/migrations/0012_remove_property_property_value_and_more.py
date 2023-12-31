# Generated by Django 4.2.4 on 2023-12-09 19:48

from django.db import migrations, models
import django.db.models.deletion
import django.utils.timezone


class Migration(migrations.Migration):

    dependencies = [
        ('rentals', '0011_alter_user_digits'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='property',
            name='property_value',
        ),
        migrations.CreateModel(
            name='Property_capital_structure',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('date', models.DateField(default=django.utils.timezone.now)),
                ('value', models.DecimalField(blank=True, decimal_places=2, max_digits=10, null=True)),
                ('debt', models.DecimalField(blank=True, decimal_places=2, max_digits=10, null=True)),
                ('property', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='capital', to='rentals.property')),
            ],
        ),
    ]
