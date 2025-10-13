"""Configuration utilities for SEC filings toolkit."""

import os
import sys
from pathlib import Path
from typing import Optional


def load_user_agent_from_env() -> str:
    """Load user agent information from .env file.

    The SEC requires a User-Agent header with contact information.
    This function reads SEC_USER_NAME and SEC_USER_EMAIL from a .env file.

    Returns:
        User agent string in format: "Name email@example.com"

    Raises:
        SystemExit: If .env file is missing or required values not configured
    """
    # Look for .env file in project root
    env_file = Path(__file__).parent.parent.parent / ".env"

    if not env_file.exists():
        print("ERROR: .env file not found!")
        print(f"Expected location: {env_file}")
        print("\nPlease create a .env file with your contact information:")
        print("  SEC_USER_NAME=Your Name")
        print("  SEC_USER_EMAIL=your.email@example.com")
        print("\nThe SEC requires this information for API access.")
        sys.exit(1)

    # Read .env file
    user_name: Optional[str] = None
    user_email: Optional[str] = None

    with open(env_file, 'r') as f:
        for line in f:
            line = line.strip()
            # Skip comments and empty lines
            if not line or line.startswith('#'):
                continue

            # Parse KEY=VALUE format
            if '=' in line:
                key, value = line.split('=', 1)
                key = key.strip()
                value = value.strip().strip('"').strip("'")  # Remove quotes if present

                if key == 'SEC_USER_NAME':
                    user_name = value
                elif key == 'SEC_USER_EMAIL':
                    user_email = value

    # Validate required fields
    if not user_name or not user_email:
        print("ERROR: Missing required configuration in .env file!")
        print(f"Location: {env_file}")
        print("\nRequired fields:")
        if not user_name:
            print("  ✗ SEC_USER_NAME is not set")
        else:
            print(f"  ✓ SEC_USER_NAME={user_name}")
        if not user_email:
            print("  ✗ SEC_USER_EMAIL is not set")
        else:
            print(f"  ✓ SEC_USER_EMAIL={user_email}")
        print("\nPlease update your .env file with both values.")
        sys.exit(1)

    return f"{user_name} {user_email}"
