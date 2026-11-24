"""Django nastavení privátního archivu na sdílené testovací VM."""
from paperless.settings import *  # noqa: F403

# OIDC discovery, výměna kódu a čtení JWKS sdílejí spojení s privátní hranou.
SOCIALACCOUNT_REQUESTS_TIMEOUT = 30
