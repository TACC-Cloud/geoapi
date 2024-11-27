from typing import Dict
import jwt
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
import base64
import time
from geoapi.settings import settings
from geoapi.log import logging


logger = logging.getLogger(__name__)

# when acquiring lock to refresh token, its possible someone else has already
# refreshed the token, so we want to check if that was recently done. so if
# token lasts longer then 14100s (i.e. 3hr55min) then token was probably just
# refreshed recently (because tokens are refreshed for a 4-hour period)
BUFFER_TIME_WHEN_CHECKING_IF_ACCESS_TOKEN_WAS_RECENTLY_REFRESHED = 14100

#  tokens are about to expire in a certain amount of time, we should update them.
BUFFER_TIME_FOR_EXPIRING_TOKENS = 300  # 5 minutes


def generate_rsa_key_pair():
    """Generate rsa key pair

    Note: to only be used by unit tests
    """
    private_key = rsa.generate_private_key(
        public_exponent=65537,
        key_size=2048,
    )
    public_key = private_key.public_key()

    # Serialize private key
    private_pem = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    ).decode("utf-8")

    # Serialize public key
    public_pem = public_key.public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    ).decode("utf-8")

    return private_pem, public_pem


PRIVATE_KEY_FOR_TESTING, PUBLIC_KEY_FOR_TESTING = generate_rsa_key_pair()


def get_pub_key():
    """Get production public key for signed tokens"""
    pkey = base64.b64decode(settings.TAPIS_PUB_KEY_FOR_VALIDATION)
    pub_key = serialization.load_der_public_key(pkey, backend=default_backend())
    return pub_key


def get_jwt(headers: Dict) -> str:
    """
    Extract the jwt from the header

    :param headers: Dict
    :return: jwt
    """
    if "X-Tapis-Token" in headers:
        return headers["X-Tapis-Token"]
    else:
        raise ValueError("No JWT could be found")


def decode_token(token: str, verify=True) -> Dict:
    """
    Validate and get a decoded jwt
    """
    pub_key = get_pub_key() if not settings.TESTING else PUBLIC_KEY_FOR_TESTING
    options = {"verify_signature": verify}
    decoded = jwt.decode(token, pub_key, algorithms=["RS256"], options=options)
    return decoded


def get_token_expiry(token: str) -> int:
    """
    Extract the expiration time from the JWT token.

    :param token: str
    :return: int (expiration time as a Unix timestamp) or None if no expiration time
    """
    decoded_token = decode_token(token, verify=False)
    return decoded_token.get("exp")


def token_will_expire_soon(token: str) -> bool:
    """
    Check if the token will expire in the next few minutes.

    :param token: str
    :return: bool
    """
    exp = get_token_expiry(token)
    current_time = int(time.time())
    return current_time > exp - BUFFER_TIME_FOR_EXPIRING_TOKENS


def compare_token_expiry(token_a, token_b):
    """
    Compare the expiration times of two JWT tokens.

    Returns:
    bool: `True` if token A expires after token B, `False` otherwise.
    """
    try:
        # Extract expiration times
        exp_a = get_token_expiry(token_a)
        exp_b = get_token_expiry(token_b)

        # Check if both tokens have expiration times
        if exp_a is None or exp_b is None:
            raise ValueError("One or both tokens do not have an expiration time.")

        # Compare expiration times
        return exp_a > exp_b

    except jwt.InvalidTokenError:
        raise ValueError("One or both tokens are invalid.")


def is_token_valid(token: str) -> bool:
    """
    Check if the JWT token is valid and not expired.

    :param token: str
    :return: bool
    """
    try:
        # Decode the token and automatically validate the exp claim
        decode_token(token)
        return True  # Token is valid and not expired
    except (jwt.ExpiredSignatureError, jwt.InvalidTokenError) as e:
        logger.error(f"token not valid: {e}")
        return False  # Token is expired or invalid


def create_token_expiry_hours_from_now(token: str, hours_from_now: int = 4) -> str:
    """
    Modify the expiration time of a JWT token to a specified number of hours from now.

    Note: this is for testing purposes only
    """
    try:
        decoded_token = jwt.decode(token, options={"verify_signature": False})

        new_expiry = int(time.time()) + hours_from_now * 3600
        decoded_token["exp"] = new_expiry
        # Re-encode the token but sign with our testing-only keys
        modified_token = jwt.encode(
            decoded_token, PRIVATE_KEY_FOR_TESTING, algorithm="RS256"
        )
        return modified_token
    except jwt.InvalidTokenError:
        raise ValueError("Invalid token provided.")
