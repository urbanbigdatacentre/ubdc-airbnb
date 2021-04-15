# Generated by Django 3.2b1 on 2021-03-26 12:50

import django.contrib.postgres.fields
import django.core.serializers.json
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('app', '0005_auto_20210325_1029'),
    ]

    operations = [
        migrations.CreateModel(
            name='AirBnBReview',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('review_id', models.IntegerField(help_text='AirBNB Review id', unique=True)),
                ('created_at', models.DateTimeField(help_text='as reported by AirBNB')),
                ('timestamp', models.DateTimeField(auto_now_add=True, verbose_name='Date of row creation.')),
                ('review_text', models.TextField()),
                ('language', models.CharField(default='', max_length=10)),
            ],
        ),
        migrations.CreateModel(
            name='AirBnBUser',
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
        migrations.RemoveField(
            model_name='user',
            name='listings',
        ),
        migrations.RemoveField(
            model_name='airbnblisting',
            name='price_quote_updated_at',
        ),
        migrations.AddField(
            model_name='airbnblisting',
            name='booking_quote_updated_at',
            field=models.DateTimeField(blank=True, help_text='Datetime of latest booking quote update', null=True),
        ),
        migrations.AlterField(
            model_name='airbnblisting',
            name='notes',
            field=models.JSONField(default=dict, encoder=django.core.serializers.json.DjangoJSONEncoder, help_text='Notes about this listing'),
        ),
        migrations.AlterField(
            model_name='airbnbresponse',
            name='ubdc_task',
            field=models.ForeignKey(null=True, on_delete=django.db.models.deletion.DO_NOTHING, to='app.ubdctask', to_field='task_id'),
        ),
        migrations.DeleteModel(
            name='Review',
        ),
        migrations.DeleteModel(
            name='User',
        ),
        migrations.AddField(
            model_name='airbnbuser',
            name='listings',
            field=models.ManyToManyField(related_name='users', to='app.AirBnBListing'),
        ),
        migrations.AddField(
            model_name='airbnbuser',
            name='responses',
            field=models.ManyToManyField(to='app.AirBnBResponse'),
        ),
        migrations.AddField(
            model_name='airbnbreview',
            name='author',
            field=models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='comments_authored', to='app.airbnbuser', to_field='user_id', verbose_name='Author (airbnb user id) of Review'),
        ),
        migrations.AddField(
            model_name='airbnbreview',
            name='listing',
            field=models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='comments', to='app.airbnblisting', verbose_name='(AirBNB) Listing id.'),
        ),
        migrations.AddField(
            model_name='airbnbreview',
            name='recipient',
            field=models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='comments_received', to='app.airbnbuser', to_field='user_id', verbose_name='recipient (airbnb user id) of the comment/review'),
        ),
        migrations.AddField(
            model_name='airbnbreview',
            name='response',
            field=models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='comments', to='app.airbnbresponse'),
        ),
    ]