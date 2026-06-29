document.addEventListener('DOMContentLoaded', () => {
    function getCSRF() {
        const el = document.querySelector('[name=csrfmiddlewaretoken]');
        if (el) return el.value;
        const name = 'csrftoken';
        const cookie = document.cookie.split(';').map(c => c.trim()).find(c => c.startsWith(name + '='));
        return cookie ? decodeURIComponent(cookie.split('=')[1]) : '';
    }

    // Toggle facility availability
    document.querySelectorAll('.toggle-availability').forEach(btn => {
        btn.addEventListener('click', async (e) => {
            const hotelId = btn.dataset.hotelId;
            btn.disabled = true;
            const form = new FormData();
            form.append('hotel_id', hotelId);

            try {
                const res = await fetch('/affiliates/toggle-availability/', {
                    method: 'POST',
                    headers: {'X-CSRFToken': getCSRF()},
                    body: form,
                    credentials: 'same-origin'
                });
                const data = await res.json();
                if (res.ok && data.status === 'ok') {
                    btn.classList.toggle('btn-success', data.is_active);
                    btn.classList.toggle('btn-outline-secondary', !data.is_active);
                    btn.textContent = data.is_active ? 'Available' : 'Offline';
                } else {
                    alert(data.message || 'Unable to update availability');
                }
            } catch (err) {
                console.error(err);
                alert('Network error');
            } finally {
                btn.disabled = false;
            }
        });
    });

    // Confirm or cancel reservation
    document.querySelectorAll('.confirm-reservation').forEach(btn => {
        btn.addEventListener('click', async (e) => {
            const bookingId = btn.dataset.bookingId;
            const action = btn.dataset.action;
            btn.disabled = true;
            const form = new FormData();
            form.append('booking_id', bookingId);
            form.append('action', action);

            try {
                const res = await fetch('/affiliates/confirm-reservation/', {
                    method: 'POST',
                    headers: {'X-CSRFToken': getCSRF()},
                    body: form,
                    credentials: 'same-origin'
                });
                const data = await res.json();
                if (res.ok && data.status === 'ok') {
                    // small UI feedback: remove item or update text
                    const item = btn.closest('.list-group-item');
                    if (action === 'confirm') {
                        item.querySelector('small').textContent = 'Status: confirmed';
                        btn.classList.remove('btn-primary');
                        btn.classList.add('btn-success');
                    } else {
                        item.querySelector('small').textContent = 'Status: cancelled';
                        btn.classList.remove('btn-outline-danger');
                        btn.classList.add('btn-secondary');
                    }
                } else {
                    alert(data.message || 'Unable to update reservation');
                }
            } catch (err) {
                console.error(err);
                alert('Network error');
            } finally {
                btn.disabled = false;
            }
        });
    });
});