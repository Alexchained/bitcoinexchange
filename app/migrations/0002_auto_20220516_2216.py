# Generated by Django 2.2.24 on 2022-05-16 20:16

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('app', '0001_initial'),
    ]

    operations = [
        migrations.AlterField(
            model_name='wallet',
            name='available_bitcoin',
            field=models.FloatField(default=3.680633707543035),
        ),
    ]