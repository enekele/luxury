import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ('bookings', '0006_booking_room_inventory'),
        ('payments', '0003_subscriptionpackage_price_currency'),
    ]

    operations = [
        migrations.AddField(
            model_name='paymenttransaction',
            name='booking',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='payment_transactions',
                to='bookings.booking',
            ),
        ),
    ]
