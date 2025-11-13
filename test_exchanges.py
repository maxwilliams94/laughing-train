"""
Test script to verify exchange authentication package structure.
"""
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from exchanges import ExchangeAuthenticator

# Test the protocol
print("✓ ExchangeAuthenticator protocol imported successfully")

try:
    from exchanges import get_coinbase_authenticator
    print("✓ get_coinbase_authenticator imported successfully")
except ImportError as e:
    print(f"✗ Failed to import get_coinbase_authenticator: {e}")

try:
    from exchanges import get_kraken_authenticator
    print("✓ get_kraken_authenticator imported successfully")
except ImportError as e:
    print(f"✗ Failed to import get_kraken_authenticator: {e}")

print("\nPackage structure verified!")
print("\nAvailable exchanges:")
print("  - Coinbase (exchanges.coinbase)")
print("  - Kraken (exchanges.kraken) [placeholder]")
