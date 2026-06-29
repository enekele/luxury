from rest_framework.views import exception_handler
from rest_framework.response import Response
from rest_framework import status
import logging

logger = logging.getLogger(__name__)


def custom_exception_handler(exc, context):
    """
    Custom exception handler for API responses
    """
    response = exception_handler(exc, context)
    
    if response is not None:
        custom_response_data = {
            'error': True,
            'message': 'An error occurred',
            'details': response.data,
            'status_code': response.status_code
        }
        
        # Log the error
        logger.error(f"API Error: {exc} - Context: {context}")
        
        # Customize error messages based on status code
        if response.status_code == 400:
            custom_response_data['message'] = 'Bad request. Please check your input.'
        elif response.status_code == 401:
            custom_response_data['message'] = 'Authentication required.'
        elif response.status_code == 403:
            custom_response_data['message'] = 'Permission denied.'
        elif response.status_code == 404:
            custom_response_data['message'] = 'Resource not found.'
        elif response.status_code == 429:
            custom_response_data['message'] = 'Too many requests. Please try again later.'
        elif response.status_code >= 500:
            custom_response_data['message'] = 'Internal server error. Please try again later.'
            # Don't expose internal error details in production
            if not context['request'].user.is_staff:
                custom_response_data['details'] = 'Internal server error'
        
        response.data = custom_response_data
    
    return response


class APIException(Exception):
    """
    Custom API exception class
    """
    def __init__(self, message, status_code=status.HTTP_400_BAD_REQUEST, details=None):
        self.message = message
        self.status_code = status_code
        self.details = details
        super().__init__(message)


class BookingException(APIException):
    """
    Exception for booking-related errors
    """
    pass


class PaymentException(APIException):
    """
    Exception for payment-related errors
    """
    pass


class AvailabilityException(APIException):
    """
    Exception for availability-related errors
    """
    pass