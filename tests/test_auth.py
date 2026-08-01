import jwt
from datetime import datetime, timezone
from app.core.security import create_access_token, get_settings

def test_create_access_token_default_expiry():
    data = {"sub": "user@example.com"}
    token = create_access_token(data)
    
    # Decode without verifying signature just to check expiry
    decoded = jwt.decode(token, options={"verify_signature": False})
    
    assert "exp" in decoded
    exp_timestamp = decoded["exp"]
    
    # Calculate expected expiry
    expected_expiry = datetime.now(timezone.utc).timestamp() + (get_settings().ACCESS_TOKEN_EXPIRE_MINUTES * 60)
    
    # Assert expiry is within a small delta of the expected value (e.g. 5 seconds)
    assert abs(exp_timestamp - expected_expiry) < 5
