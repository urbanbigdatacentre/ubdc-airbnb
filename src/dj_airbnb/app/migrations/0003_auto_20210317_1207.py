# Generated by Django 3.2b1 on 2021-03-17 12:07

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('app', '0002_auto_20210315_1630'),
    ]

    operations = [
        migrations.AddField(
            model_name='worldshape',
            name='md5_checksum',
            field=models.CharField(default='', editable=False, max_length=255, unique=True),
            preserve_default=False,
        ),
        migrations.AlterField(
            model_name='ubdctask',
            name='status',
            field=models.TextField(choices=[('SUBMITTED', 'Submitted'), ('STARTED', 'Started'), ('SUCCESS', 'Success'), ('FAILURE', 'Failure'), ('REVOKED', 'Revoked'), ('RETRY', 'Retry'), ('UNKNOWN', 'Unknown')], db_index=True, default='SUBMITTED'),
        ),
    ]
