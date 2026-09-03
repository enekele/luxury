from datetime import timedelta
from decimal import Decimal

from djmoney.money import Money

from hotels.models import HotelAvailability, RoomType


class RoomInventoryError(ValueError):
    """Raised when a requested hotel-room stay cannot be reserved."""


def stay_dates(check_in, check_out):
    """Return each occupied night, excluding the checkout date."""
    if check_out <= check_in:
        raise RoomInventoryError('Check-out must be after check-in.')
    return [
        check_in + timedelta(days=offset)
        for offset in range((check_out - check_in).days)
    ]


def quote_room_stay(
    room_type,
    check_in,
    check_out,
    *,
    rooms=1,
    guests=1,
    lock_inventory=False,
):
    """Validate room capacity/stock and return a date-aware stay quote."""
    if not room_type.is_active or not room_type.hotel.is_active:
        raise RoomInventoryError('This room category is not available.')
    if not room_type.hotel.is_available:
        raise RoomInventoryError('This hotel is not accepting reservations.')
    if rooms < 1:
        raise RoomInventoryError('Choose at least one room.')
    if guests < 1:
        raise RoomInventoryError('Choose at least one guest.')
    if guests > room_type.max_occupancy * rooms:
        raise RoomInventoryError(
            f'{room_type.name} accommodates up to '
            f'{room_type.max_occupancy * rooms} guests in {rooms} '
            f'room{"s" if rooms != 1 else ""}.'
        )

    dates = stay_dates(check_in, check_out)
    availability = HotelAvailability.objects.filter(
        room_type=room_type,
        date__gte=check_in,
        date__lt=check_out,
    )
    if lock_inventory:
        availability = availability.select_for_update()
    records = {record.date: record for record in availability}

    nightly_inventory = []
    currency_codes = set()
    total_amount = Decimal('0')

    for stay_date in dates:
        record = records.get(stay_date)
        available_rooms = (
            record.available_rooms if record else room_type.available_rooms
        )
        if available_rooms < rooms:
            raise RoomInventoryError(
                f'{room_type.name} does not have {rooms} room'
                f'{"s" if rooms != 1 else ""} available on '
                f'{stay_date:%B %d, %Y}.'
            )

        rate = record.price_per_night if record else room_type.price_per_night
        currency_codes.add(str(rate.currency))
        total_amount += rate.amount * rooms
        nightly_inventory.append(
            {
                'date': stay_date,
                'record': record,
                'available_rooms': available_rooms,
                'rate': rate,
            }
        )

    if len(currency_codes) != 1:
        raise RoomInventoryError(
            'The selected dates use different currencies. Ask the hotel to '
            'publish one currency for the full stay.'
        )

    currency = currency_codes.pop()
    total = Money(total_amount, currency)
    return {
        'room_type': room_type,
        'check_in': check_in,
        'check_out': check_out,
        'rooms': rooms,
        'guests': guests,
        'nights': len(dates),
        'nightly_inventory': nightly_inventory,
        'total': total,
        'average_nightly_rate': Money(total_amount / len(dates) / rooms, currency),
    }


def reserve_room_inventory(quote):
    """Deduct a validated quote from each occupied date."""
    room_type = quote['room_type']
    rooms = quote['rooms']
    for night in quote['nightly_inventory']:
        remaining_rooms = night['available_rooms'] - rooms
        record = night['record']
        if record:
            record.available_rooms = remaining_rooms
            record.save(update_fields=['available_rooms'])
        else:
            HotelAvailability.objects.create(
                room_type=room_type,
                date=night['date'],
                available_rooms=remaining_rooms,
                price_per_night=night['rate'],
            )


def release_booking_room_inventory(booking):
    """Return held hotel inventory once when a reservation is cancelled."""
    if (
        not booking.inventory_reserved
        or not booking.room_type_id
        or not booking.check_in
        or not booking.check_out
    ):
        return False

    room_type = RoomType.objects.select_for_update().filter(
        pk=booking.room_type_id
    ).first()
    if room_type:
        records = HotelAvailability.objects.select_for_update().filter(
            room_type=room_type,
            date__gte=booking.check_in,
            date__lt=booking.check_out,
        )
        for record in records:
            record.available_rooms = min(
                room_type.total_rooms,
                record.available_rooms + booking.quantity,
            )
            record.save(update_fields=['available_rooms'])

    booking.inventory_reserved = False
    booking.save(update_fields=['inventory_reserved', 'updated_at'])
    return True
