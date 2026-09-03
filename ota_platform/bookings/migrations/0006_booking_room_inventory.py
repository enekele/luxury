import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ('hotels', '0004_room_type_availability'),
        ('bookings', '0005_booking_checkout_fields'),
    ]

    operations = [
        migrations.AddField(
            model_name='booking',
            name='inventory_reserved',
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name='booking',
            name='room_type',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='bookings',
                to='hotels.roomtype',
            ),
        ),
    ]
