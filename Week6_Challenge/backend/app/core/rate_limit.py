from slowapi import Limiter
from slowapi.util import get_remote_address

# Per-IP limiter. Applied to auth endpoints only (see app/api/routers/auth.py) — those
# are the brute-force/spam-signup surface; other endpoints are already gated by JWT auth,
# which is a much stronger throttle than an anonymous IP-based limit would add.
limiter = Limiter(key_func=get_remote_address)
