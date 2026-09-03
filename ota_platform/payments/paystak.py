"""
Minimal Paystack integration helper for Django.

Usage:
- Add to your settings.py:
    PAYSTACK_SECRET_KEY = env('PAYSTACK_SECRET_KEY')
    PAYSTACK_BASE_URL = 'https://api.paystack.co'   # optional

- Example view flow:
    1) POST to a view that calls PaystakClient.initialize_payment(...) -> redirect user to authorization_url
    2) Paystack will redirect back to your callback URL; call PaystakClient.verify_transaction(reference)
    3) Implement webhook view using verify_webhook_signature to trust incoming events.

Notes:
- Paystack expects amount in the smallest currency unit (kobo/cents). Pass integer.
- This module uses `requests`. Ensure requests is installed in your env.
"""

from typing import Optional, Dict, Any
import requests
import uuid
import hmac
import hashlib
import json
import logging

from django.conf import settings
from django.urls import reverse

logger = logging.getLogger(__name__)


class PaystakClient:
    def __init__(self, secret_key: Optional[str] = None, base_url: Optional[str] = None, timeout: int = 10):
        self.secret_key = secret_key or getattr(settings, "PAYSTACK_SECRET_KEY", None)
        if not self.secret_key:
            raise RuntimeError("PAYSTACK_SECRET_KEY is not set in settings")
        self.base_url = base_url or getattr(settings, "PAYSTACK_BASE_URL", "https://api.paystack.co")
        self.timeout = timeout
        self.headers = {
            "Authorization": f"Bearer {self.secret_key}",
            "Content-Type": "application/json",
        }

    @staticmethod
    def _gen_reference(prefix: str = "PSK") -> str:
        return f"{prefix}-{uuid.uuid4().hex}"

    def initialize_payment(
        self,
        email: str,
        amount: int,
        callback_url: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
        reference: Optional[str] = None,
        currency: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Initialize a transaction. `amount` should be an integer in the smallest currency unit (kobo/cents).
        Returns dictionary with full response. On success response['data'] contains 'authorization_url' and 'reference'.
        """
        if not reference:
            reference = self._gen_reference()
        payload = {
            "email": email,
            "amount": int(amount),
            "reference": reference,
        }
        if callback_url:
            payload["callback_url"] = callback_url
        if metadata:
            payload["metadata"] = metadata
        if currency:
            payload["currency"] = currency.upper()

        url = f"{self.base_url.rstrip('/')}/transaction/initialize"
        try:
            res = requests.post(url, headers=self.headers, json=payload, timeout=self.timeout)
            res.raise_for_status()
            return res.json()
        except requests.RequestException as e:
            logger.exception("Paystack initialize_payment failed")
            return {"status": False, "message": str(e)}

    def verify_transaction(self, reference: str) -> Dict[str, Any]:
        """
        Verify a transaction by reference. Returns the response JSON.
        """
        url = f"{self.base_url.rstrip('/')}/transaction/verify/{reference}"
        try:
            res = requests.get(url, headers=self.headers, timeout=self.timeout)
            res.raise_for_status()
            return res.json()
        except requests.RequestException as e:
            logger.exception("Paystack verify_transaction failed")
            return {"status": False, "message": str(e)}

    def charge_authorization(self, authorization_code: str, email: str, amount: int, reference: Optional[str] = None) -> Dict[str, Any]:
        """
        Charge a saved authorization (one-time). authorization_code from previous transaction auth.
        """
        if not reference:
            reference = self._gen_reference("CHG")
        payload = {
            "authorization_code": authorization_code,
            "email": email,
            "amount": int(amount),
            "reference": reference,
        }
        url = f"{self.base_url.rstrip('/')}/transaction/charge_authorization"
        try:
            res = requests.post(url, headers=self.headers, json=payload, timeout=self.timeout)
            res.raise_for_status()
            return res.json()
        except requests.RequestException as e:
            logger.exception("Paystack charge_authorization failed")
            return {"status": False, "message": str(e)}

    def verify_webhook_signature(self, request) -> bool:
        """
        Verify webhook signature. Paystack sends X-Paystack-Signature header (HMAC-SHA512).
        Usage in Django view:
            client = PaystakClient()
            if not client.verify_webhook_signature(request): return HttpResponseForbidden()
            event = json.loads(request.body)
        """
        signature_header = request.META.get("HTTP_X_PAYSTACK_SIGNATURE", "")
        if not signature_header:
            return False
        try:
            body = request.body or b""
            computed = hmac.new(self.secret_key.encode(), body, hashlib.sha512).hexdigest()
            return hmac.compare_digest(computed, signature_header)
        except Exception:
            logger.exception("Error verifying Paystack webhook signature")
            return False

