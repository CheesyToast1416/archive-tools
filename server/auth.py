from __future__ import annotations

from fastapi import Header, HTTPException, Query, status


def verify_token(
    authorization: str | None = Header(default=None),
    token: str = Query(default=""),
) -> None:
    from server._token import TOKEN

    # Accept Bearer token from Authorization header OR ?token= query param
    # (query param is required for media elements that cannot set headers)
    header_tok = ""
    if authorization:
        scheme, _, tok = authorization.partition(" ")
        if scheme.lower() == "bearer":
            header_tok = tok

    provided = token or header_tok
    if not provided or provided != TOKEN:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token"
        )
