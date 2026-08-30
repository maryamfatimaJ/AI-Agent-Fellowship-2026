from datetime import datetime

from sqlalchemy.orm import Session

from app.models.revoked_token import RevokedToken


def revoke_token(jti: str, expires_at: datetime, db: Session) -> None:
    if db.get(RevokedToken, jti) is not None:
        return
    db.add(RevokedToken(jti=jti, expires_at=expires_at))
    db.commit()


def is_token_revoked(jti: str, db: Session) -> bool:
    return db.get(RevokedToken, jti) is not None
