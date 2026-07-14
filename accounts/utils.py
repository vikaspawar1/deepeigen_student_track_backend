"""
Utility functions for the accounts app.
"""
from rest_framework_simplejwt.tokens import RefreshToken

def get_tokens_for_user(user):
    """
    Generate JWT access and refresh tokens for a specific user instance.

    Args:
        user (Account): The user instance for which to generate tokens.

    Returns:
        dict: A dictionary containing 'refresh' and 'access' token strings.
    """
    refresh = RefreshToken.for_user(user)
    return {
        'refresh': str(refresh),
        'access': str(refresh.access_token),
    }
