"""
Google Wallet coupon pass generation service.
"""
import json
import logging
import uuid
from datetime import datetime, timedelta
from typing import Dict, Any, Optional
from google.oauth2 import service_account
from googleapiclient.discovery import build

from app.core.config import settings
from app.schemas.wallets import GoogleWalletCouponData

logger = logging.getLogger(__name__)


class GoogleWalletService:
    """Service for Google Wallet coupon pass generation and management."""
    
    def __init__(self):
        self.service = None
        self._initialize_service()
    
    def _initialize_service(self):
        """Initialize Google Wallet API service."""
        try:
            # In production, you would load credentials from a secure location
            # For now, we'll use environment variables
            credentials_info = {
                "type": "service_account",
                "project_id": settings.GOOGLE_WALLET_PROJECT_ID,
                "private_key_id": settings.GOOGLE_WALLET_PRIVATE_KEY_ID,
                "private_key": settings.GOOGLE_WALLET_PRIVATE_KEY.replace('\\n', '\n'),
                "client_email": settings.GOOGLE_WALLET_CLIENT_EMAIL,
                "client_id": settings.GOOGLE_WALLET_CLIENT_ID,
                "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                "token_uri": "https://oauth2.googleapis.com/token",
                "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
                "client_x509_cert_url": f"https://www.googleapis.com/robot/v1/metadata/x509/{settings.GOOGLE_WALLET_CLIENT_EMAIL}"
            }
            
            credentials = service_account.Credentials.from_service_account_info(
                credentials_info,
                scopes=['https://www.googleapis.com/auth/wallet_object.issuer']
            )
            
            self.service = build('walletobjects', 'v1', credentials=credentials)
            logger.info("Google Wallet service initialized successfully")
            
        except Exception as e:
            logger.error(f"Failed to initialize Google Wallet service: {e}")
            self.service = None
    
    def generate_serial_number(self) -> str:
        """Generate a unique serial number for the pass."""
        return f"77x_{uuid.uuid4().hex[:16].upper()}"
    
    def create_pass_class(self, class_id: str, class_data: Dict[str, Any]) -> Dict[str, Any]:
        """Create a Google Wallet pass class."""
        if not self.service:
            raise Exception("Google Wallet service not initialized")
        
        try:
            class_object = {
                "id": f"{settings.GOOGLE_WALLET_ISSUER_ID}.{class_id}",
                "classTemplateInfo": {
                    "cardTemplateOverride": {
                        "cardRowTemplateInfos": class_data.get("card_row_template_infos", [])
                    }
                },
                "reviewStatus": "UNDER_REVIEW",
                "issuerName": settings.GOOGLE_WALLET_ISSUER_NAME,
                "hexBackgroundColor": class_data.get("hex_background_color", "#4285f4"),
                "logo": {
                    "sourceUri": {
                        "uri": class_data.get("logo_uri", "")
                    }
                }
            }
            
            response = self.service.genericclass().insert(body=class_object).execute()
            logger.info(f"Created Google Wallet class: {class_id}")
            return response
            
        except Exception as e:
            logger.error(f"Failed to create Google Wallet class: {e}")
            raise
    
    def create_coupon_object(self, class_id: str, pass_data: GoogleWalletCouponData) -> Dict[str, Any]:
        """Create a Google Wallet coupon object."""
        if not self.service:
            raise Exception("Google Wallet service not initialized")
        
        try:
            serial_number = self.generate_serial_number()
            
            # Build the coupon object
            coupon_object = {
                "id": f"{settings.GOOGLE_WALLET_ISSUER_ID}.{pass_data.object_id}",
                "classId": f"{settings.GOOGLE_WALLET_ISSUER_ID}.{pass_data.class_id}",
                "state": "ACTIVE",
                "textModulesData": pass_data.text_modules_data or [],
                "linksModuleData": {
                    "uris": [
                        {
                            "uri": settings.GOOGLE_WALLET_APP_LINK,
                            "description": "View Details"
                        }
                    ]
                },
                "imageModulesData": [],
                "barcode": {
                    "type": "QR_CODE",
                    "value": f"77x://coupon/{serial_number}"
                },
                "locations": [],
                "hasUsers": False,
                "hasLinkedDevice": False,
                "disableExpirationNotification": False
            }
            
            # Add card title and subtitle for coupon
            if pass_data.card_title:
                coupon_object["cardTitle"] = {
                    "defaultValue": {
                        "language": "en-US",
                        "value": pass_data.card_title
                    }
                }
            
            if pass_data.card_subtitle:
                coupon_object["cardSubtitle"] = {
                    "defaultValue": {
                        "language": "en-US",
                        "value": pass_data.card_subtitle
                    }
                }
            
            # Add header fields for discount information
            if pass_data.card_header:
                coupon_object["cardHeader"] = {
                    "defaultValue": {
                        "language": "en-US",
                        "value": pass_data.card_header
                    }
                }
            
            # Add detail fields for coupon terms
            if pass_data.card_details:
                coupon_object["cardDetails"] = {
                    "defaultValue": {
                        "language": "en-US",
                        "value": pass_data.card_details
                    }
                }
            
            response = self.service.genericobject().insert(body=coupon_object).execute()
            logger.info(f"Created Google Wallet coupon: {pass_data.object_id}")
            
            return {
                "coupon_object": response,
                "serial_number": serial_number,
                "pass_url": f"https://pay.google.com/gp/v/save/{response['id']}"
            }
            
        except Exception as e:
            logger.error(f"Failed to create Google Wallet object: {e}")
            raise
    
    def generate_coupon_pass(self, user_id: str, coupon_data: Dict[str, Any]) -> Dict[str, Any]:
        """Generate a discount coupon for Google Wallet."""
        try:
            # Create coupon data
            pass_data = GoogleWalletCouponData(
                issuer_id=settings.GOOGLE_WALLET_ISSUER_ID,
                class_id=f"discount_coupon_class_{user_id}",
                object_id=f"discount_coupon_{user_id}_{uuid.uuid4().hex[:8]}",
                card_title=coupon_data.get("title", "77x Discount Coupon"),
                card_subtitle=coupon_data.get("subtitle", f"{coupon_data.get('discount_percentage', '10')}% Off"),
                card_header=coupon_data.get("header", "Discount Applied"),
                card_details=coupon_data.get("details", "Show this coupon at checkout"),
                hex_background_color=coupon_data.get("background_color", "#4285f4"),
                text_modules_data=[
                    {
                        "header": "Discount Details",
                        "body": coupon_data.get("description", f"Save {coupon_data.get('discount_percentage', '10')}% on your purchase"),
                        "id": "discount_details"
                    },
                    {
                        "header": "Valid Until",
                        "body": coupon_data.get("expiry_date", (datetime.utcnow() + timedelta(days=30)).strftime("%Y-%m-%d")),
                        "id": "expiry_date"
                    }
                ]
            )
            
            # Create the coupon object
            result = self.create_coupon_object(pass_data.class_id, pass_data)
            
            return {
                "pass_id": result["coupon_object"]["id"],
                "serial_number": result["serial_number"],
                "pass_url": result["pass_url"],
                "pass_type": "google",
                "pass_class": "coupon",
                "user_id": user_id,
                "created_at": datetime.utcnow(),
                "expires_at": datetime.utcnow() + timedelta(days=30)  # Default 30 days
            }
            
        except Exception as e:
            logger.error(f"Failed to generate Google Wallet discount coupon: {e}")
            raise
    
    def update_coupon_object(self, object_id: str, updates: Dict[str, Any]) -> Dict[str, Any]:
        """Update an existing Google Wallet coupon object."""
        if not self.service:
            raise Exception("Google Wallet service not initialized")
        
        try:
            response = self.service.genericobject().patch(
                resourceId=f"{settings.GOOGLE_WALLET_ISSUER_ID}.{object_id}",
                body=updates
            ).execute()
            
            logger.info(f"Updated Google Wallet coupon: {object_id}")
            return response
            
        except Exception as e:
            logger.error(f"Failed to update Google Wallet coupon: {e}")
            raise
    
    def expire_coupon_object(self, object_id: str) -> Dict[str, Any]:
        """Expire a Google Wallet coupon object."""
        return self.update_coupon_object(object_id, {"state": "EXPIRED"})
    
    def void_coupon_object(self, object_id: str) -> Dict[str, Any]:
        """Void a Google Wallet coupon object."""
        return self.update_coupon_object(object_id, {"state": "INACTIVE"})
