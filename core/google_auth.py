"""
Google OAuth2 Authentication Service
Handles Google token verification and user creation/authentication
"""

import os
import secrets
from datetime import timedelta
from typing import Optional, Dict, Tuple

from google.oauth2 import id_token
from google.auth.exceptions import GoogleAuthError

from .models import Usuario
from .db import SessionLocal
from . import auth_service, security


def verify_google_token(id_token_str: str) -> Optional[Dict]:
    """
    Verifies a Google ID token and extracts user information.
    
    Returns:
        dict with keys: email, name, or None if verification fails
    """
    try:
        google_client_id = os.getenv("GOOGLE_CLIENT_ID")
        if not google_client_id:
            print("ERROR: GOOGLE_CLIENT_ID environment variable not set")
            return None
        
        # Verify the token with Google
        id_info = id_token.verify_oauth2_token(
            id_token_str, 
            request=None, 
            audience=google_client_id
        )
        
        # Extract user information
        email = id_info.get('email', '').lower()
        name = id_info.get('name') or id_info.get('given_name') or email.split('@')[0]
        picture = id_info.get('picture')
        
        if not email:
            print("ERROR: No email found in Google token")
            return None
        
        return {
            'email': email,
            'name': name,
            'picture': picture,
            'raw_token_info': id_info
        }
        
    except GoogleAuthError as e:
        print(f"ERROR: Google token verification failed: {e}")
        return None
    except Exception as e:
        print(f"ERROR: Unexpected error verifying Google token: {e}")
        return None


def get_or_create_user_from_google(
    email: str, 
    name: str, 
    picture: Optional[str] = None
) -> Tuple[bool, Optional[Usuario], str]:
    """
    Gets or creates a user from Google authentication data.
    
    Returns:
        (success: bool, user: Usuario or None, message: str)
    """
    db = SessionLocal()
    try:
        # Look for existing user by email
        existing_user = db.query(Usuario).filter(
            Usuario.correo == email
        ).first()
        
        if existing_user:
            print(f"INFO: Found existing user for {email}")
            return True, existing_user, "User found"
        
        # Create new user
        print(f"INFO: Creating new user from Google for {email}")
        
        # Generate unique username
        base_username = email.split('@')[0]
        username = base_username
        
        # Check if username is already taken, if so add a suffix
        counter = 1
        while db.query(Usuario).filter(Usuario.user == username).first():
            username = f"{base_username}_{secrets.token_hex(3)}"
            counter += 1
            if counter > 10:  # Safety limit
                username = f"{base_username}_{secrets.token_hex(8)}"
                break
        
        # Generate random password for Google-authenticated users
        random_password = auth_service.generate_random_password(20)
        
        # Create new user
        new_user = Usuario(
            nombre=name,
            correo=email,
            user=username,
            password_hash=auth_service.hash_password(random_password),
            rol='estudiante'  # Default role for Google-authenticated users
        )
        
        db.add(new_user)
        db.commit()
        db.refresh(new_user)
        
        print(f"INFO: Successfully created user {username} (ID: {new_user.id})")
        return True, new_user, "User created"
        
    except Exception as e:
        db.rollback()
        print(f"ERROR: Failed to get/create user from Google: {e}")
        return False, None, f"Database error: {str(e)}"
    finally:
        db.close()


def authenticate_with_google(id_token_str: str) -> Tuple[bool, Optional[Dict], str]:
    """
    Complete Google authentication flow.
    
    Returns:
        (success: bool, result_dict with access_token/user info or None, error_message: str)
    """
    
    # Verify token
    token_info = verify_google_token(id_token_str)
    if not token_info:
        return False, None, "Invalid or expired Google token"
    
    email = token_info.get('email')
    name = token_info.get('name')
    
    # Get or create user
    success, user, message = get_or_create_user_from_google(email, name)
    
    if not success or not user:
        return False, None, message
    
    # Create JWT token
    try:
        expires = timedelta(minutes=security.ACCESS_TOKEN_EXPIRE_MINUTES)
        token_data = {
            "sub": user.user,
            "rol": user.rol,
            "id": user.id
        }
        access_token = security.create_access_token(
            data=token_data,
            expires_delta=expires
        )
        
        result = {
            "access_token": access_token,
            "token_type": "bearer",
            "user": {
                "id": user.id,
                "nombre": user.nombre,
                "user": user.user,
                "correo": user.correo,
                "rol": user.rol
            }
        }
        
        return True, result, "Authentication successful"
        
    except Exception as e:
        print(f"ERROR: Failed to create access token: {e}")
        return False, None, f"Token creation error: {str(e)}"
