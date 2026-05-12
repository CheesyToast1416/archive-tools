from __future__ import annotations

from fastapi import Header, HTTPException, status


def verify_token(authorization: str | None = Header(default=None)) -> None:
    from server._token import TOKEN

    if not authorization:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing token"
        )
    scheme, _, tok = authorization.partition(" ")
    if scheme.lower() != "bearer" or tok != TOKEN:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token"
        )
