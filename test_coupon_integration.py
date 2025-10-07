#!/usr/bin/env python3
"""
Simple test script for discount coupon wallet integration.
This script tests the simplified coupon functionality without payment logic.
"""

import requests
import json
import sys
from typing import Optional

BASE_URL = "http://localhost:8000"

def print_step(step: str, description: str):
    print(f"\n{'='*50}")
    print(f"STEP {step}: {description}")
    print('='*50)

def print_result(success: bool, message: str):
    status = "✅" if success else "❌"
    print(f"{status} {message}")

def get_auth_token() -> Optional[str]:
    """Register a test user and get auth token."""
    print_step("1", "User Registration and Authentication")
    
    # Try to register a new user
    register_data = {
        "email": "coupon_test@example.com",
        "name": "Coupon Test User",
        "password": "testpassword123"
    }
    
    try:
        response = requests.post(f"{BASE_URL}/auth/register", json=register_data, timeout=10)
        
        if response.status_code == 200:
            auth_data = response.json()
            token = auth_data["access_token"]
            print_result(True, f"User registered successfully: {auth_data['user']['email']}")
            return token
        elif response.status_code == 400 and "already exists" in response.text:
            # User already exists, try to login
            print_result(True, "User already exists, attempting login...")
            login_data = {
                "email": register_data["email"],
                "password": register_data["password"]
            }
            
            login_response = requests.post(f"{BASE_URL}/auth/login", json=login_data, timeout=10)
            if login_response.status_code == 200:
                auth_data = login_response.json()
                token = auth_data["access_token"]
                print_result(True, f"User logged in successfully: {auth_data['user']['email']}")
                return token
            else:
                print_result(False, f"Login failed: {login_response.text}")
                return None
        else:
            print_result(False, f"Registration failed: {response.text}")
            return None
            
    except requests.exceptions.RequestException as e:
        print_result(False, f"Network error: {e}")
        return None

def test_discount_coupon_generation(token: str):
    """Test discount coupon generation for both Google and Apple Wallet."""
    headers = {"Authorization": f"Bearer {token}"}
    
    print_step("2", "Testing Discount Coupon Generation")
    
    # Test Google Wallet discount coupon
    google_coupon_data = {
        "pass_type": "google",
        "coupon_data": {
            "title": "77x Special Discount",
            "discount_percentage": 20,
            "description": "Get 20% off your next purchase",
            "background_color": "#4285f4",
            "terms": "Valid for 30 days. Show at checkout."
        }
    }
    
    try:
        response = requests.post(f"{BASE_URL}/wallets/coupons/generate", json=google_coupon_data, headers=headers, timeout=10)
        
        if response.status_code == 200:
            coupon_data = response.json()
            print_result(True, f"Google Wallet discount coupon generated successfully!")
            print(f"   Coupon ID: {coupon_data['pass_id']}")
            print(f"   Serial Number: {coupon_data['serial_number']}")
            print(f"   Pass Type: {coupon_data['pass_type']}")
            print(f"   Pass Class: {coupon_data['pass_class']}")
            print(f"   Created At: {coupon_data['created_at']}")
            if coupon_data.get('pass_url'):
                print(f"   Pass URL: {coupon_data['pass_url']}")
            else:
                print("   Pass URL: Not available (credentials not configured)")
        else:
            print_result(False, f"Google Wallet coupon generation failed: {response.text}")
            
    except requests.exceptions.RequestException as e:
        print_result(False, f"Network error during Google Wallet test: {e}")
    
    # Test Apple Wallet discount coupon
    print("\n" + "-"*30)
    apple_coupon_data = {
        "pass_type": "apple",
        "coupon_data": {
            "title": "77x Apple Discount",
            "discount_percentage": 15,
            "description": "Save 15% on your next purchase",
            "background_color": "rgb(60, 65, 76)",
            "foreground_color": "rgb(255, 255, 255)",
            "logo_text": "77x",
            "terms": "Valid for 30 days. Show at checkout."
        }
    }
    
    try:
        response = requests.post(f"{BASE_URL}/wallets/coupons/generate", json=apple_coupon_data, headers=headers, timeout=10)
        
        if response.status_code == 200:
            coupon_data = response.json()
            print_result(True, f"Apple Wallet discount coupon generated successfully!")
            print(f"   Coupon ID: {coupon_data['pass_id']}")
            print(f"   Serial Number: {coupon_data['serial_number']}")
            print(f"   Pass Type: {coupon_data['pass_type']}")
            print(f"   Pass Class: {coupon_data['pass_class']}")
            print(f"   Created At: {coupon_data['created_at']}")
        else:
            print_result(False, f"Apple Wallet coupon generation failed: {response.text}")
            
    except requests.exceptions.RequestException as e:
        print_result(False, f"Network error during Apple Wallet test: {e}")

def test_coupon_management(token: str):
    """Test coupon listing and management."""
    headers = {"Authorization": f"Bearer {token}"}
    
    print_step("3", "Testing Coupon Management")
    
    # List user's coupons
    try:
        response = requests.get(f"{BASE_URL}/wallets/coupons", headers=headers, timeout=10)
        
        if response.status_code == 200:
            coupons_data = response.json()
            print_result(True, f"Retrieved {coupons_data['total']} discount coupons")
            print(f"   Page: {coupons_data['page']}/{coupons_data['page_size']}")
            
            for i, coupon_obj in enumerate(coupons_data['coupons'], 1):
                print(f"   {i}. {coupon_obj['pass_type'].upper()} Coupon - {coupon_obj['serial_number']}")
                print(f"      Class: {coupon_obj['pass_class']}")
                print(f"      Active: {coupon_obj['is_active']}")
                print(f"      Created: {coupon_obj['created_at']}")
        else:
            print_result(False, f"Failed to list coupons: {response.text}")
            
    except requests.exceptions.RequestException as e:
        print_result(False, f"Network error during coupon listing: {e}")

def test_coupon_templates(token: str):
    """Test coupon template creation and listing."""
    headers = {"Authorization": f"Bearer {token}"}
    
    print_step("4", "Testing Coupon Templates")
    
    # Create a discount coupon template
    template_data = {
        "template_name": "Standard Discount Template",
        "pass_type": "google",
        "template_data": {
            "title": "Standard Discount",
            "discount_percentage": 10,
            "description": "Standard 10% discount coupon",
            "background_color": "#ff6b6b",
            "terms": "Valid for 30 days from issue date."
        }
    }
    
    try:
        response = requests.post(f"{BASE_URL}/wallets/templates", json=template_data, headers=headers, timeout=10)
        
        if response.status_code == 200:
            template = response.json()
            print_result(True, f"Discount coupon template created successfully!")
            print(f"   Template ID: {template['template_id']}")
            print(f"   Template Name: {template['template_name']}")
            print(f"   Pass Type: {template['pass_type']}")
            print(f"   Pass Class: {template['pass_class']}")
        else:
            print_result(False, f"Template creation failed: {response.text}")
            
    except requests.exceptions.RequestException as e:
        print_result(False, f"Network error during template creation: {e}")
    
    # List templates
    print("\n" + "-"*30)
    try:
        response = requests.get(f"{BASE_URL}/wallets/templates", headers=headers, timeout=10)
        
        if response.status_code == 200:
            templates = response.json()
            print_result(True, f"Retrieved {len(templates)} discount coupon templates")
            
            for i, template in enumerate(templates, 1):
                print(f"   {i}. {template['template_name']} ({template['pass_type']})")
                print(f"      Class: {template['pass_class']}")
                print(f"      Active: {template['is_active']}")
        else:
            print_result(False, f"Failed to list templates: {response.text}")
            
    except requests.exceptions.RequestException as e:
        print_result(False, f"Network error during template listing: {e}")

def test_error_handling():
    """Test error handling scenarios."""
    print_step("5", "Testing Error Handling")
    
    # Test invalid wallet type
    try:
        response = requests.post(f"{BASE_URL}/wallets/coupons/generate", json={
            "pass_type": "invalid_wallet",
            "coupon_data": {}
        }, timeout=10)
        
        if response.status_code == 400:
            print_result(True, "Invalid wallet type correctly rejected")
        else:
            print_result(False, f"Expected 400, got {response.status_code}")
            
    except requests.exceptions.RequestException as e:
        print_result(False, f"Network error during error testing: {e}")
    
    # Test missing authentication
    try:
        response = requests.post(f"{BASE_URL}/wallets/coupons/generate", json={
            "pass_type": "google",
            "coupon_data": {}
        }, timeout=10)
        
        if response.status_code == 401:
            print_result(True, "Missing authentication correctly rejected")
        else:
            print_result(False, f"Expected 401, got {response.status_code}")
            
    except requests.exceptions.RequestException as e:
        print_result(False, f"Network error during auth testing: {e}")

def check_server_status():
    """Check if the server is running."""
    print_step("0", "Checking Server Status")
    
    try:
        response = requests.get(f"{BASE_URL}/health", timeout=5)
        if response.status_code == 200:
            print_result(True, f"Server is running at {BASE_URL}")
            return True
        else:
            print_result(False, f"Server responded with status {response.status_code}")
            return False
    except requests.exceptions.RequestException as e:
        print_result(False, f"Cannot connect to server at {BASE_URL}")
        print(f"   Error: {e}")
        print(f"   Make sure to start the server with: uvicorn app.main:app --reload")
        return False

def main():
    print("🎫 Discount Coupon Wallet Integration Test Script")
    print("This script tests the simplified coupon functionality.")
    print("Make sure your FastAPI server is running on http://localhost:8000")
    
    # Check server status
    if not check_server_status():
        sys.exit(1)
    
    # Get authentication token
    token = get_auth_token()
    if not token:
        print("\n❌ Cannot proceed without authentication token")
        sys.exit(1)
    
    # Run tests
    test_discount_coupon_generation(token)
    test_coupon_management(token)
    test_coupon_templates(token)
    test_error_handling()
    
    print("\n" + "="*50)
    print("🎉 Discount Coupon Testing Complete!")
    print("="*50)
    print("\nKey Features Tested:")
    print("✅ Google Wallet discount coupon generation")
    print("✅ Apple Wallet discount coupon generation")
    print("✅ Coupon listing and management")
    print("✅ Coupon template creation and listing")
    print("✅ Error handling and validation")
    print("\nNext steps:")
    print("1. Set up Google Wallet credentials for real Google Wallet coupons")
    print("2. Set up Apple Wallet certificates for real Apple Wallet coupons")
    print("3. Test with actual mobile wallet apps")
    print("4. Check the API documentation at http://localhost:8000/docs")

if __name__ == "__main__":
    main()
