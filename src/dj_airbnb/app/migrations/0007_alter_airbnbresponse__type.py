# Generated by Django 3.2b1 on 2021-03-30 09:13

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('app', '0006_auto_20210326_1250'),
    ]

    operations = [
        migrations.AlterField(
            model_name='airbnbresponse',
            name='_type',
            field=models.CharField(choices=[('UNK', 'Unknown'), ('BKT', 'Booking Detail'), ('CAL', 'Calendar'), ('RVW', 'Review'), ('LST', 'Listing'), ('QUO', 'Price Quote'), ('SRH', 'Search'), ('SHM', 'Search (MetaOnly)'), ('USR', 'User')], db_column='type', db_index=True, default='UNK', max_length=3, verbose_name='Response Type'),
        ),
    ]
