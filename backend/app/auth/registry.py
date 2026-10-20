from app.auth.base import AuthProvider
from app.auth.providers.standalone import StandaloneAuthProvider
from app.core.config import settings

# name -> provider; register external-IdP providers here, select via AUTH_PROVIDER.
_PROVIDERS: dict[str, AuthProvider] = {
    StandaloneAuthProvider.name: StandaloneAuthProvider(),
}


def get_auth_provider() -> AuthProvider:
    try:
        return _PROVIDERS[settings.AUTH_PROVIDER]
    except KeyError:
        raise RuntimeError(
            f"Unknown AUTH_PROVIDER {settings.AUTH_PROVIDER!r}; "
            f"available: {sorted(_PROVIDERS)}"
        )
