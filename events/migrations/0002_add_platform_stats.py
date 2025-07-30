# Generated manually for PlatformStats model

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('events', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='PlatformStats',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('total_events_created', models.PositiveIntegerField(default=0, help_text='Total events ever created')),
                ('total_rsvps_created', models.PositiveIntegerField(default=0, help_text='Total RSVPs ever created')),
                ('total_users_registered', models.PositiveIntegerField(default=0, help_text='Total users ever registered')),
                ('total_groups_created', models.PositiveIntegerField(default=0, help_text='Total groups ever created')),
                ('last_updated', models.DateTimeField(auto_now=True)),
            ],
            options={
                'verbose_name': 'Platform Statistics',
                'verbose_name_plural': 'Platform Statistics',
            },
        ),
    ] 