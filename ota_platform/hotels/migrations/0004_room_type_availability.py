import django.db.models.deletion
from django.db import migrations, models


def link_availability_to_room_types(apps, schema_editor):
    HotelAvailability = apps.get_model('hotels', 'HotelAvailability')
    RoomType = apps.get_model('hotels', 'RoomType')

    for availability in HotelAvailability.objects.all().iterator():
        room_type = RoomType.objects.filter(hotel_id=availability.hotel_id).first()
        if room_type is None:
            room_type = RoomType.objects.create(
                hotel_id=availability.hotel_id,
                name='Standard room',
                description='Room type created while migrating legacy availability.',
                max_occupancy=2,
                price_per_night=availability.price_per_night,
                price_per_night_currency=availability.price_per_night_currency,
                total_rooms=max(availability.available_rooms, 1),
                available_rooms=availability.available_rooms,
            )
        availability.room_type_id = room_type.id
        availability.save(update_fields=['room_type'])


class Migration(migrations.Migration):
    dependencies = [
        ('hotels', '0003_hotelpartner_partner_profile'),
    ]

    operations = [
        migrations.AlterModelOptions(
            name='hotelavailability',
            options={},
        ),
        migrations.AlterUniqueTogether(
            name='hotelavailability',
            unique_together=set(),
        ),
        migrations.AddField(
            model_name='hotelavailability',
            name='room_type',
            field=models.ForeignKey(
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name='availability',
                to='hotels.roomtype',
            ),
        ),
        migrations.RunPython(
            link_availability_to_room_types,
            migrations.RunPython.noop,
        ),
        migrations.RemoveField(
            model_name='hotelavailability',
            name='hotel',
        ),
        migrations.AlterField(
            model_name='hotelavailability',
            name='room_type',
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                related_name='availability',
                to='hotels.roomtype',
            ),
        ),
        migrations.AlterField(
            model_name='hotelavailability',
            name='available_rooms',
            field=models.PositiveIntegerField(default=0),
        ),
        migrations.AddConstraint(
            model_name='hotelavailability',
            constraint=models.UniqueConstraint(
                fields=('room_type', 'date'),
                name='unique_room_type_availability_date',
            ),
        ),
    ]
