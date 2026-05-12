from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from server.auth import verify_token
from server.models import AddPasswordRequest, PasswordEntryModel, UpdatePasswordRequest

router = APIRouter(dependencies=[Depends(verify_token)])


@router.get("/", response_model=list[PasswordEntryModel])
def list_passwords() -> list[PasswordEntryModel]:
    from archivetools.config.passwords import get_password_store

    store = get_password_store()
    return [
        PasswordEntryModel(id=e.id, label=e.label, hint=e.hint) for e in store.entries()
    ]


@router.post("/", response_model=PasswordEntryModel)
def add_password(req: AddPasswordRequest) -> PasswordEntryModel:
    from archivetools.config.passwords import get_password_store

    entry = get_password_store().add(req.label, req.password, req.hint)
    return PasswordEntryModel(id=entry.id, label=entry.label, hint=entry.hint)


@router.put("/{entry_id}")
def update_password(entry_id: str, req: UpdatePasswordRequest) -> dict:
    from archivetools.config.passwords import get_password_store

    try:
        get_password_store().update(entry_id, req.label, req.password, req.hint)
    except (KeyError, RuntimeError) as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return {"ok": True}


@router.delete("/{entry_id}")
def delete_password(entry_id: str) -> dict:
    from archivetools.config.passwords import get_password_store

    try:
        get_password_store().delete(entry_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return {"ok": True}


@router.get("/{entry_id}/secret")
def get_secret(entry_id: str) -> dict:
    from archivetools.config.passwords import get_password_store

    try:
        pwd = get_password_store().get_password(entry_id)
    except (KeyError, RuntimeError) as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return {"password": pwd}


@router.get("/keyring-status")
def keyring_status() -> dict:
    from archivetools.config.passwords import get_password_store

    return {"keyring_available": get_password_store().keyring_available}
