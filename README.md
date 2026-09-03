# Luxury Travel Platform

A Django travel marketplace for hotels, flights, cars, tours, events, bookings,
partner inventory, affiliates, payments, and an AI-assisted concierge.

## Run locally

Requirements: Python 3.12 and Git.

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r ota_platform/requirements.txt
cp .env.example .env
set -a && source .env && set +a
python manage.py migrate
python manage.py runserver
```

When `DATABASE_URL` is blank, local development uses SQLite. Open
`http://127.0.0.1:8000/` after the server starts.

Create an administrator with:

```bash
python manage.py createsuperuser
```

## Partner access

Partner access is approval-based. In Django admin, create a normal user and a
linked active `Partner` record. The partner can then sign in at `/accounts/login/`
and is redirected to `/partners/` automatically.

The partner dashboard includes protected tools for:

- creating and editing hotel, flight, car, and tour listings;
- creating hotel room categories with capacity, room counts, amenities, and
  category-level pricing;
- publishing date-based hotel room availability and nightly-rate overrides;
- letting customers select a room category, check live date availability, and
  reserve inventory at the category's date-aware rate;
- opening or closing owned inventory for new reservations;
- searching, filtering, reviewing, and exporting owned reservations;
- confirming, cancelling, or completing reservations through valid status
  transitions; and
- adding countries and cities at `/partners/locations/`.

Reservation operations are available at `/partners/reservations/`. Users
without an active `Partner` record cannot access partner tools, and partners
cannot manage inventory or reservations owned by another partner.

## Verify a change

```bash
python manage.py check
python manage.py makemigrations --check --dry-run
python manage.py test core
python manage.py collectstatic --noinput
```

## Deploy to Render

The repository includes a Render Blueprint in `render.yaml`. In Render, create
a new Blueprint, select this repository, and apply it. The Blueprint provisions
the web service and PostgreSQL database, generates a Django secret key, runs
migrations, collects static assets, and configures the health check.

Add credentials for integrations in the Render service environment:

- `STRIPE_PUBLIC_KEY` and `STRIPE_SECRET_KEY`
- `PAYSTACK_PUBLIC_KEY` and `PAYSTACK_SECRET_KEY` (required for hotel checkout)
- `OPENAI_API_KEY` and `OPENAI_MODEL`
- `AMADEUS_API_KEY` and `AMADEUS_API_SECRET`
- SMTP settings if production email is required

Email verification defaults to `none` so new users are not blocked when SMTP is
unconfigured. After adding working SMTP credentials, set
`ACCOUNT_EMAIL_VERIFICATION=mandatory` to require confirmation emails.

Hotel bookings use Paystack's hosted checkout. Add
`https://<your-domain>/payments/webhook/` as the webhook URL in the Paystack
dashboard so a successful payment still secures the reservation when the
customer does not return through the browser callback. The application verifies
the webhook signature and the transaction reference, amount, currency, booking,
and payer before marking the reservation paid. Unpaid room inventory is held for
15 minutes by default; customize this with `BOOKING_PAYMENT_HOLD_MINUTES`.

Never commit secrets or production databases. Use environment variables in the
hosting dashboard.
