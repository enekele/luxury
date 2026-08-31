from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ('bookings', '0004_remove_booking_hotel'),
    ]

    operations = [
        migrations.AddField(
            model_name='booking',
            name='check_in',
            field=models.DateField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='booking',
            name='check_out',
            field=models.DateField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='booking',
            name='expires_at',
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='booking',
            name='payment_status',
            field=models.CharField(
                choices=[
                    ('unpaid', 'Unpaid'),
                    ('pending', 'Payment Pending'),
                    ('paid', 'Paid'),
                    ('refunded', 'Refunded'),
                ],
                default='unpaid',
                max_length=20,
            ),
        ),
        migrations.AddField(
            model_name='booking',
            name='quantity',
            field=models.PositiveIntegerField(default=1),
        ),
    ]
