import logging
from datetime import datetime, timedelta, timezone
from typing import Optional, Dict, Any, List

try:
    import jwt
    JWT_AVAILABLE = True
except ImportError:
    jwt = None
    JWT_AVAILABLE = False

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from app.config import Settings, get_settings
from app.models.schemas import UserPayload

logger = logging.getLogger(__name__)

security_scheme = HTTPBearer(auto_error=False)



def create_access_token(
    user_id: str,
    email: str,
    role: str,
    settings: Optional[Settings] = None
) -> str:
    """Generate a signed JWT access token for a user with RBAC role."""
    cfg = settings or get_settings()
    now = datetime.now(timezone.utc)
    expire = now + timedelta(minutes=cfg.JWT_EXPIRATION_MINUTES)

    role_info = cfg.RBAC_ROLES.get(role, {
        "allowed_spaces": ["GENERAL"],
        "can_sync": False
    })

    payload = {
        "sub": user_id,
        "email": email,
        "role": role,
        "allowed_spaces": role_info.get("allowed_spaces", ["*"]),
        "can_sync": role_info.get("can_sync", False),
        "iat": int(now.timestamp()),
        "exp": int(expire.timestamp())
    }

    if not JWT_AVAILABLE:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Paket 'pyjwt' belum terinstal. Jalankan 'pip install pyjwt' di environment Python Anda."
        )

    token = jwt.encode(payload, cfg.JWT_SECRET_KEY, algorithm=cfg.JWT_ALGORITHM)
    return token


def decode_access_token(token: str, settings: Optional[Settings] = None) -> Dict[str, Any]:
    """Decode and validate a JWT access token."""
    if not JWT_AVAILABLE:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Paket 'pyjwt' belum terinstal. Jalankan 'pip install pyjwt' di environment Python Anda."
        )

    # Sanitize token (strip accidental surrounding quotes and whitespace)
    cleaned_token = token.strip().strip('"').strip("'").strip()

    cfg = settings or get_settings()
    try:
        decoded = jwt.decode(
            cleaned_token,
            cfg.JWT_SECRET_KEY,
            algorithms=[cfg.JWT_ALGORITHM]
        )
        return decoded
    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token telah kedaluwarsa (Expired Token). Silakan login kembali.",
            headers={"WWW-Authenticate": "Bearer"}
        )
    except jwt.InvalidTokenError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Token tidak valid: {str(e)}",
            headers={"WWW-Authenticate": "Bearer"}
        )


async def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security_scheme),
    settings: Settings = Depends(get_settings)
) -> UserPayload:
    """
    Dependency to get and validate the current authenticated user and their RBAC permissions.
    If AUTH_REQUIRED is False and no token provided, grants dev admin access.
    """
    if not settings.AUTH_REQUIRED:
        # Development mode bypass
        return UserPayload(
            user_id="dev_user",
            email="dev@company.local",
            role="admin",
            allowed_spaces=["*"],
            can_sync=True
        )

    if not credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Header otentikasi Bearer Token diperlukan.",
            headers={"WWW-Authenticate": "Bearer"}
        )

    payload = decode_access_token(credentials.credentials, settings)
    
    return UserPayload(
        user_id=payload.get("sub", "unknown"),
        email=payload.get("email", ""),
        role=payload.get("role", "employee"),
        allowed_spaces=payload.get("allowed_spaces", ["GENERAL"]),
        can_sync=payload.get("can_sync", False)
    )


async def require_sync_permission(
    current_user: UserPayload = Depends(get_current_user)
) -> UserPayload:
    """Dependency verifying that the user has data sync/ingestion permissions (RBAC)."""
    if not current_user.can_sync:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Akses Ditolak: Role '{current_user.role}' tidak memiliki izin untuk melakukan sinkronisasi/ingestion data (can_sync=False)."
        )
    return current_user
