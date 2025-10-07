"""
Apple Wallet coupon pass generation service.
"""
import json
import logging
import uuid
import zipfile
import tempfile
import os
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa, padding
from cryptography import x509
from cryptography.x509.oid import NameOID
import plistlib

from app.core.config import settings
from app.schemas.wallets import AppleWalletCouponData

logger = logging.getLogger(__name__)


class AppleWalletService:
    """Service for Apple Wallet coupon pass generation and management."""
    
    def __init__(self):
        self.private_key = None
        self.certificate = None
        self._initialize_certificates()
    
    def _initialize_certificates(self):
        """Initialize Apple Wallet certificates."""
        try:
            # In production, you would load certificates from secure storage
            # For now, we'll use environment variables or file paths
            if hasattr(settings, 'APPLE_WALLET_PRIVATE_KEY_PATH'):
                with open(settings.APPLE_WALLET_PRIVATE_KEY_PATH, 'rb') as key_file:
                    self.private_key = serialization.load_pem_private_key(
                        key_file.read(),
                        password=None
                    )
            
            if hasattr(settings, 'APPLE_WALLET_CERTIFICATE_PATH'):
                with open(settings.APPLE_WALLET_CERTIFICATE_PATH, 'rb') as cert_file:
                    self.certificate = x509.load_pem_x509_certificate(cert_file.read())
            
            logger.info("Apple Wallet certificates initialized successfully")
            
        except Exception as e:
            logger.error(f"Failed to initialize Apple Wallet certificates: {e}")
            self.private_key = None
            self.certificate = None
    
    def generate_serial_number(self) -> str:
        """Generate a unique serial number for the pass."""
        return f"77x_{uuid.uuid4().hex[:16].upper()}"
    
    def create_pass_manifest(self, pass_files: Dict[str, bytes]) -> Dict[str, str]:
        """Create the manifest.json file for the pass."""
        manifest = {}
        for filename, content in pass_files.items():
            manifest[filename] = self._sha1_hash(content)
        return manifest
    
    def _sha1_hash(self, data: bytes) -> str:
        """Calculate SHA1 hash of data."""
        digest = hashes.Hash(hashes.SHA1())
        digest.update(data)
        return digest.finalize().hex()
    
    def sign_manifest(self, manifest: Dict[str, str]) -> bytes:
        """Sign the manifest with the private key."""
        if not self.private_key:
            raise Exception("Apple Wallet private key not initialized")
        
        manifest_json = json.dumps(manifest, sort_keys=True).encode('utf-8')
        
        signature = self.private_key.sign(
            manifest_json,
            padding.PKCS1v15(),
            hashes.SHA1()
        )
        
        return signature
    
    def create_coupon_json(self, pass_data: AppleWalletCouponData, serial_number: str) -> Dict[str, Any]:
        """Create the pass.json file for Apple Wallet coupon."""
        coupon_json = {
            "formatVersion": 1,
            "passTypeIdentifier": pass_data.pass_type_identifier,
            "serialNumber": serial_number,
            "teamIdentifier": pass_data.team_identifier,
            "organizationName": pass_data.organization_name,
            "description": pass_data.description,
            "logoText": pass_data.logo_text,
            "foregroundColor": pass_data.foreground_color or "rgb(255, 255, 255)",
            "backgroundColor": pass_data.background_color or "rgb(60, 65, 76)",
            "labelColor": pass_data.label_color or "rgb(255, 255, 255)",
            "barcode": {
                "message": f"77x://coupon/{serial_number}",
                "format": "PKBarcodeFormatQR",
                "messageEncoding": "iso-8859-1"
            },
            "barcodes": [
                {
                    "message": f"77x://coupon/{serial_number}",
                    "format": "PKBarcodeFormatQR",
                    "messageEncoding": "iso-8859-1"
                }
            ]
        }
        
        # Add optional fields
        if pass_data.relevant_date:
            coupon_json["relevantDate"] = pass_data.relevant_date.isoformat() + "Z"
        
        if pass_data.expiration_date:
            coupon_json["expirationDate"] = pass_data.expiration_date.isoformat() + "Z"
        
        if pass_data.voided is not None:
            coupon_json["voided"] = pass_data.voided
        
        if pass_data.locations:
            coupon_json["locations"] = pass_data.locations
        
        # Add coupon-specific data
        if pass_data.coupon:
            coupon_json["coupon"] = pass_data.coupon
        
        return coupon_json
    
    def create_coupon_package(self, pass_data: AppleWalletCouponData, images: Dict[str, bytes] = None) -> bytes:
        """Create a complete Apple Wallet coupon package (.pkpass file)."""
        try:
            serial_number = self.generate_serial_number()
            
            # Create coupon.json
            coupon_json = self.create_coupon_json(pass_data, serial_number)
            coupon_json_bytes = json.dumps(coupon_json, indent=2).encode('utf-8')
            
            # Prepare files for the coupon
            coupon_files = {
                "pass.json": coupon_json_bytes
            }
            
            # Add images if provided
            if images:
                for filename, image_data in images.items():
                    coupon_files[filename] = image_data
            
            # Create manifest
            manifest = self.create_pass_manifest(coupon_files)
            manifest_bytes = json.dumps(manifest, indent=2).encode('utf-8')
            coupon_files["manifest.json"] = manifest_bytes
            
            # Sign the manifest
            signature = self.sign_manifest(manifest)
            coupon_files["signature"] = signature
            
            # Create the .pkpass file (ZIP archive)
            with tempfile.NamedTemporaryFile(delete=False, suffix='.pkpass') as temp_file:
                with zipfile.ZipFile(temp_file.name, 'w', zipfile.ZIP_DEFLATED) as zip_file:
                    for filename, content in coupon_files.items():
                        zip_file.writestr(filename, content)
                
                # Read the created file
                with open(temp_file.name, 'rb') as f:
                    pkpass_data = f.read()
                
                # Clean up
                os.unlink(temp_file.name)
                
                return pkpass_data
                
        except Exception as e:
            logger.error(f"Failed to create Apple Wallet coupon package: {e}")
            raise
    
    def generate_coupon_pass(self, user_id: str, coupon_data: Dict[str, Any]) -> Dict[str, Any]:
        """Generate a discount coupon for Apple Wallet."""
        try:
            # Create coupon data
            pass_data = AppleWalletCouponData(
                pass_type_identifier=settings.APPLE_WALLET_PASS_TYPE_IDENTIFIER,
                team_identifier=settings.APPLE_WALLET_TEAM_IDENTIFIER,
                organization_name=settings.APPLE_WALLET_ORGANIZATION_NAME,
                description=coupon_data.get("description", "77x Discount Coupon"),
                logo_text=coupon_data.get("logo_text", "77x"),
                foreground_color=coupon_data.get("foreground_color", "rgb(255, 255, 255)"),
                background_color=coupon_data.get("background_color", "rgb(60, 65, 76)"),
                label_color=coupon_data.get("label_color", "rgb(255, 255, 255)"),
                expiration_date=datetime.utcnow() + timedelta(days=30),  # Default 30 days
                coupon={
                    "primaryFields": [
                        {
                            "key": "discount",
                            "label": "Discount",
                            "value": coupon_data.get("discount", f"{coupon_data.get('discount_percentage', '10')}% OFF")
                        }
                    ],
                    "secondaryFields": [
                        {
                            "key": "description",
                            "label": "Description",
                            "value": coupon_data.get("description", f"Save {coupon_data.get('discount_percentage', '10')}% on your purchase")
                        }
                    ],
                    "auxiliaryFields": [
                        {
                            "key": "expires",
                            "label": "Expires",
                            "value": (datetime.utcnow() + timedelta(days=30)).strftime("%Y-%m-%d")
                        }
                    ],
                    "backFields": [
                        {
                            "key": "terms",
                            "label": "Terms & Conditions",
                            "value": coupon_data.get("terms", "Valid for 30 days from issue date. Show at checkout.")
                        }
                    ]
                }
            )
            
            # Create the coupon package
            pkpass_data = self.create_coupon_package(pass_data)
            
            return {
                "pass_id": f"apple_coupon_{user_id}_{uuid.uuid4().hex[:8]}",
                "serial_number": pass_data.serial_number if hasattr(pass_data, 'serial_number') else self.generate_serial_number(),
                "pass_data": pkpass_data,
                "pass_type": "apple",
                "pass_class": "coupon",
                "user_id": user_id,
                "created_at": datetime.utcnow(),
                "expires_at": datetime.utcnow() + timedelta(days=30)
            }
            
        except Exception as e:
            logger.error(f"Failed to generate Apple Wallet discount coupon: {e}")
            raise
    
    def validate_pass_signature(self, pkpass_data: bytes) -> bool:
        """Validate the signature of an Apple Wallet pass."""
        try:
            with tempfile.NamedTemporaryFile(suffix='.pkpass') as temp_file:
                temp_file.write(pkpass_data)
                temp_file.flush()
                
                with zipfile.ZipFile(temp_file.name, 'r') as zip_file:
                    # Read manifest and signature
                    manifest_data = zip_file.read('manifest.json')
                    signature_data = zip_file.read('signature')
                    
                    # Verify signature
                    if not self.private_key:
                        return False
                    
                    self.private_key.verify(
                        signature_data,
                        manifest_data,
                        padding.PKCS1v15(),
                        hashes.SHA1()
                    )
                    
                    return True
                    
        except Exception as e:
            logger.error(f"Failed to validate Apple Wallet pass signature: {e}")
            return False
