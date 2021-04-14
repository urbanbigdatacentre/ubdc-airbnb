# Generated by Django 3.2b1 on 2021-03-15 16:30

import django.contrib.gis.db.models.fields
import django.contrib.postgres.fields
import django.contrib.postgres.indexes
import django.core.serializers.json
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('app', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='AirBnBListing',
            fields=[
                ('listing_id', models.IntegerField(help_text='(PK) Airbnb ListingID', primary_key=True, serialize=False, unique=True)),
                ('geom_3857', django.contrib.gis.db.models.fields.PointField(help_text="Current Geom Point ('3857') of listing's location", srid=3857)),
                ('timestamp', models.DateTimeField(auto_now_add=True, help_text='Datetime of entry')),
                ('listing_updated_at', models.DateTimeField(blank=True, help_text='Datetime of last listing update', null=True)),
                ('calendar_updated_at', models.DateTimeField(blank=True, help_text='Datetime of last calendar update', null=True)),
                ('price_quote_updated_at', models.DateTimeField(blank=True, help_text='Datetime of last price quote update', null=True)),
                ('comment_updated_at', models.DateTimeField(blank=True, help_text='Datetime of last comment update', null=True)),
                ('notes', models.JSONField(decoder=django.core.serializers.json.DjangoJSONEncoder, default=dict, encoder=django.core.serializers.json.DjangoJSONEncoder, help_text='Notes about this listing')),
            ],
        ),
        migrations.CreateModel(
            name='AirBnbListingLocations',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('listing_id', models.IntegerField(db_index=True, help_text='Airbnb ListingID')),
                ('geom_3857', django.contrib.gis.db.models.fields.PointField(help_text="Current Geom Point ('3857') of listing's location", srid=3857)),
                ('current', models.BooleanField(db_index=True, default=True)),
                ('timestamp', models.DateTimeField(auto_now_add=True, help_text='Datetime of entry')),
            ],
            options={
                'ordering': ['timestamp'],
            },
        ),
        migrations.CreateModel(
            name='AirBnBResponse',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('listing_id', models.IntegerField(db_index=True, null=True)),
                ('purpose_type', models.CharField(choices=[('UNK', 'Unknown'), ('BDT', 'Booking Detail'), ('CAL', 'Calendar'), ('CMT', 'Comment'), ('LST', 'Listings'), ('QUO', 'Price Quote'), ('SRH', 'Search'), ('USR', 'User')], db_index=True, default='UKN', max_length=3, verbose_name='Response Type')),
                ('status_code', models.IntegerField(db_index=True, help_text='Status code of the response')),
                ('resource_url', models.TextField()),
                ('payload', models.JSONField(default=dict)),
                ('url', models.TextField()),
                ('query_params', models.JSONField(default=dict)),
                ('seconds_to_complete', models.IntegerField(help_text='Time in seconds for the response to come back.')),
                ('timestamp', models.DateTimeField(auto_now_add=True, db_index=True, verbose_name='Date of row creation.')),
            ],
        ),
        migrations.CreateModel(
            name='AOIShape',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('geom_3857', django.contrib.gis.db.models.fields.MultiPolygonField(editable=False, help_text='Geometry column. Defined at EPSG:3857', srid=3857)),
                ('name', models.TextField(default='', help_text='Name to display.')),
                ('notes', models.JSONField(decoder=django.core.serializers.json.DjangoJSONEncoder, default=dict, encoder=django.core.serializers.json.DjangoJSONEncoder, help_text='Notes.')),
                ('timestamp', models.DateTimeField(auto_now_add=True, verbose_name='Date of entry')),
                ('collect_calendars', models.BooleanField(db_index=True, default=True)),
                ('collect_listing_details', models.BooleanField(db_index=True, default=True)),
                ('collect_reviews', models.BooleanField(db_index=True, default=True)),
            ],
        ),
        migrations.CreateModel(
            name='Review',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('comment_id', models.IntegerField(help_text='AirBNB Review id', unique=True)),
                ('created_at', models.DateTimeField(help_text='as reported by AirBNB')),
                ('timestamp', models.DateTimeField(auto_now_add=True, verbose_name='Date of row creation.')),
                ('comment_text', models.TextField()),
                ('language', models.CharField(default='', max_length=10)),
            ],
        ),
        migrations.CreateModel(
            name='UBDCGrid',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('geom_3857', django.contrib.gis.db.models.fields.PolygonField(srid=3857)),
                ('quadkey', models.TextField(blank=True, db_index=True, editable=False, unique=True)),
                ('tile_x', models.IntegerField()),
                ('tile_y', models.IntegerField()),
                ('tile_z', models.IntegerField()),
                ('x_distance_m', models.FloatField()),
                ('y_distance_m', models.FloatField()),
                ('bbox_ll_ur', models.TextField()),
                ('area', models.FloatField()),
                ('timestamp', models.DateTimeField(auto_now_add=True)),
                ('datetime_last_estimated_listings_scan', models.DateTimeField(blank=True, db_index=True, null=True)),
                ('estimated_listings', models.IntegerField(default=-1, verbose_name='Estimated Listings reported from AirBnB')),
            ],
        ),
        migrations.CreateModel(
            name='UBDCGroupTask',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('group_task_id', models.UUIDField(db_index=True, editable=False, unique=True)),
                ('root_id', models.UUIDField(db_index=True, editable=False, null=True)),
                ('timestamp', models.DateTimeField(auto_now_add=True)),
                ('datetime_started', models.DateTimeField(null=True)),
                ('datetime_finished', models.DateTimeField(null=True)),
                ('op_name', models.TextField(blank=True, null=True)),
                ('op_args', django.contrib.postgres.fields.ArrayField(base_field=models.CharField(max_length=255), blank=True, null=True, size=None)),
                ('op_kwargs', models.JSONField(default=dict)),
                ('op_initiator', models.TextField(default='', max_length=255)),
            ],
        ),
        migrations.CreateModel(
            name='UBDCTask',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('task_id', models.UUIDField(db_index=True, editable=False, unique=True)),
                ('status', models.TextField(choices=[('SUBMITTED', 'Submitted'), ('STARTED', 'Started'), ('SUCCESS', 'Success'), ('FAILURE', 'Failure'), ('REVOKED', 'Revoked'), ('RETRY', 'Retry'), ('UNKNOWN', 'Unknown')], default='SUBMITTED', null=True)),
                ('datetime_submitted', models.DateTimeField(auto_now_add=True, db_index=True)),
                ('datetime_started', models.DateTimeField(blank=True, null=True)),
                ('datetime_finished', models.DateTimeField(blank=True, null=True)),
                ('time_to_complete', models.TextField(blank=True, default='')),
                ('retries', models.IntegerField(default=0)),
                ('task_name', models.TextField()),
                ('task_args', models.TextField(default='[]')),
                ('task_kwargs', models.JSONField(default=dict)),
                ('parent_id', models.UUIDField(db_index=True, editable=False, null=True)),
                ('root_id', models.UUIDField(db_index=True, editable=False, null=True)),
            ],
        ),
        migrations.CreateModel(
            name='User',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('user_id', models.IntegerField(blank=True, help_text='Airbnb User id', unique=True)),
                ('first_name', models.TextField(default='')),
                ('about', models.TextField(default='')),
                ('airbnb_listing_count', models.IntegerField(default=0, help_text='as reported by airbnb')),
                ('location', models.TextField()),
                ('verifications', django.contrib.postgres.fields.ArrayField(base_field=models.CharField(max_length=255), blank=True, null=True, size=None)),
                ('picture_url', models.TextField()),
                ('is_superhost', models.BooleanField(default=False, help_text='if the user is super host')),
                ('created_at', models.DateTimeField(blank=True, help_text='profile created at airbnb', null=True)),
                ('timestamp', models.DateTimeField(auto_now_add=True, verbose_name='Date of row creation.')),
                ('last_updated', models.DateTimeField(auto_now=True, verbose_name='Latest update.')),
            ],
        ),
        migrations.RemoveIndex(
            model_name='worldshape',
            name='dj_airbnb_w_iso3_al_eef0cc_btree',
        ),
        migrations.AlterField(
            model_name='worldshape',
            name='id',
            field=models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID'),
        ),
        migrations.AlterField(
            model_name='worldshape',
            name='iso3_alpha',
            field=models.CharField(db_index=True, max_length=3),
        ),
        migrations.AlterField(
            model_name='worldshape',
            name='name_0',
            field=models.CharField(db_index=True, max_length=255),
        ),
        migrations.AddField(
            model_name='user',
            name='listings',
            field=models.ManyToManyField(related_name='users', to='app.AirBnBListing'),
        ),
        migrations.AddField(
            model_name='ubdctask',
            name='group_task',
            field=models.ForeignKey(null=True, on_delete=django.db.models.deletion.DO_NOTHING, related_name='ubdc_tasks', related_query_name='ubdc_task', to='app.ubdcgrouptask', to_field='group_task_id'),
        ),
        migrations.AlterUniqueTogether(
            name='ubdcgrouptask',
            unique_together={('group_task_id', 'root_id')},
        ),
        migrations.AddField(
            model_name='review',
            name='author',
            field=models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='comments_authored', to='app.user', to_field='user_id', verbose_name='Author (airbnb user id) of Review'),
        ),
        migrations.AddField(
            model_name='review',
            name='listing',
            field=models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='comments', to='app.airbnblisting', verbose_name='(AirBNB) Listing id.'),
        ),
        migrations.AddField(
            model_name='review',
            name='recipient',
            field=models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='comments_received', to='app.user', to_field='user_id', verbose_name='recipient (airbnb user id) of the comment/review'),
        ),
        migrations.AddField(
            model_name='review',
            name='response',
            field=models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='comments', to='app.airbnbresponse'),
        ),
        migrations.AddField(
            model_name='airbnbresponse',
            name='ubdc_task',
            field=models.ForeignKey(on_delete=django.db.models.deletion.DO_NOTHING, to='app.ubdctask', to_field='task_id'),
        ),
        migrations.AddField(
            model_name='airbnblistinglocations',
            name='response',
            field=models.ForeignKey(on_delete=django.db.models.deletion.DO_NOTHING, to='app.airbnbresponse'),
        ),
        migrations.AddField(
            model_name='airbnblisting',
            name='response',
            field=models.ForeignKey(on_delete=django.db.models.deletion.DO_NOTHING, to='app.airbnbresponse'),
        ),
        migrations.AddIndex(
            model_name='ubdctask',
            index=django.contrib.postgres.indexes.GinIndex(fields=['task_kwargs'], name='app_ubdctas_task_kw_1b31ae_gin'),
        ),
    ]
