"""
SMS Service Module - Handles SMS communication via Twilio.
Includes production Twilio service and mock service for testing.
"""

import logging
import os
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional

# Twilio imports (optional, gracefully handles missing dependency)
try:
    from twilio.rest import Client
    TWILIO_AVAILABLE = True
except ImportError:
    TWILIO_AVAILABLE = False
    logger = logging.getLogger(__name__)
    logger.warning("Twilio not installed - using mock SMS service")

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class SMSService(ABC):
    """Abstract base class for SMS services."""
    
    @abstractmethod
    def send_sms(self, to_number: str, message: str, metadata: Optional[Dict] = None) -> bool:
        """Send SMS message."""
        pass


class TwilioSMSService(SMSService):
    """Twilio SMS service implementation."""
    
    def __init__(self, account_sid: Optional[str] = None, auth_token: Optional[str] = None, from_number: Optional[str] = None):
        """
        Initialize Twilio SMS service.
        
        Args:
            account_sid: Twilio account SID (defaults to TWILIO_ACCOUNT_SID env var)
            auth_token: Twilio auth token (defaults to TWILIO_AUTH_TOKEN env var)
            from_number: Twilio phone number (defaults to TWILIO_PHONE_NUMBER env var)
        """
        if not TWILIO_AVAILABLE:
            raise ImportError("Twilio SDK not installed. Install with: pip install twilio")
        
        self.account_sid = account_sid or os.getenv("TWILIO_ACCOUNT_SID")
        self.auth_token = auth_token or os.getenv("TWILIO_AUTH_TOKEN")
        self.from_number = from_number or os.getenv("TWILIO_PHONE_NUMBER")
        
        if not all([self.account_sid, self.auth_token, self.from_number]):
            raise ValueError(
                "Missing Twilio credentials. Set TWILIO_ACCOUNT_SID, "
                "TWILIO_AUTH_TOKEN, and TWILIO_PHONE_NUMBER environment variables"
            )
        
        self.client = Client(self.account_sid, self.auth_token)
        logger.info("Twilio SMS service initialized")
    
    def send_sms(self, to_number: str, message: str, metadata: Optional[Dict] = None) -> bool:
        """
        Send SMS via Twilio.
        
        Args:
            to_number: Recipient phone number
            message: Message text
            metadata: Optional metadata for logging
            
        Returns:
            True if sent successfully, False otherwise
        """
        try:
            msg = self.client.messages.create(
                body=message,
                from_=self.from_number,
                to=to_number
            )
            
            logger.info(
                f"SMS sent to {to_number} - SID: {msg.sid} "
                f"{f'(Metadata: {metadata})' if metadata else ''}"
            )
            return True
            
        except Exception as e:
            logger.error(f"Error sending SMS to {to_number}: {str(e)}", exc_info=True)
            return False


class MockSMSService(SMSService):
    """Mock SMS service for testing and development."""
    
    def __init__(self):
        """Initialize mock SMS service."""
        self.sent_messages = []
        logger.info("Mock SMS service initialized (for testing)")
    
    def send_sms(self, to_number: str, message: str, metadata: Optional[Dict] = None) -> bool:
        """
        Mock SMS send - logs message instead of sending.
        
        Args:
            to_number: Recipient phone number
            message: Message text
            metadata: Optional metadata for logging
            
        Returns:
            Always returns True
        """
        mock_message = {
            "to": to_number,
            "body": message,
            "metadata": metadata or {},
            "timestamp": str(__import__('datetime').datetime.now())
        }
        
        self.sent_messages.append(mock_message)
        
        logger.info(
            f"[MOCK] SMS sent to {to_number}: {message} "
            f"{f'(Metadata: {metadata})' if metadata else ''}"
        )
        
        return True
    
    def get_sent_messages(self):
        """Get all sent messages (for testing)."""
        return self.sent_messages
    
    def clear_sent_messages(self):
        """Clear sent messages history (for testing)."""
        self.sent_messages = []


def get_sms_service(use_mock: bool = False) -> SMSService:
    """
    Factory function to get appropriate SMS service.
    
    Args:
        use_mock: If True, use mock service; otherwise use Twilio
        
    Returns:
        SMS service instance
    """
    if use_mock or not TWILIO_AVAILABLE:
        return MockSMSService()
    else:
        try:
            return TwilioSMSService()
        except (ImportError, ValueError) as e:
            logger.warning(f"Could not initialize Twilio service: {e}. Falling back to mock.")
            return MockSMSService()


if __name__ == "__main__":
    print("SMS Service module - for use in your application")
