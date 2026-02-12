import logging
import os
import re

import requests

logger = logging.getLogger(__name__)

WEBSHARE_CONFIG_URL = "https://proxy.webshare.io/api/v2/proxy/config/"
WEBSHARE_DOWNLOAD_URL = (
    "https://proxy.webshare.io/api/v2/proxy/list/download"
    "/{token}/-/any/username/direct/-/"
)
REQUEST_TIMEOUT_SECONDS = 30


class _ProxyCredentialFilter(logging.Filter):
    """Strip user:password from proxy URLs in log messages."""

    _pattern = re.compile(r"://[^@]+@")

    def filter(self, record: logging.LogRecord) -> bool:
        if record.msg and isinstance(record.msg, str):
            record.msg = self._pattern.sub("://***:***@", record.msg)
        if record.args:
            record.args = tuple(
                self._pattern.sub("://***:***@", str(a)) if isinstance(a, str) else a
                for a in record.args
            )
        return True


# Prevent rotating_proxies from logging proxy credentials
logging.getLogger("rotating_proxies").addFilter(_ProxyCredentialFilter())


def fetch_proxy_list() -> list[str]:
    """Fetch proxy list from Webshare API.

    Returns a list of proxy URLs in http://user:pwd@ip:port format.
    Returns an empty list if PROXY_TOKEN is unset or the API call fails,
    allowing the spider to run without proxies.
    """
    token = os.getenv("PROXY_TOKEN")
    if not token:
        logger.info("PROXY_TOKEN not set; running without proxies")
        return []

    try:
        resp = requests.get(
            WEBSHARE_CONFIG_URL,
            headers={"Authorization": f"Token {token}"},
            timeout=REQUEST_TIMEOUT_SECONDS,
        )
        resp.raise_for_status()
        download_token = resp.json()["proxy_list_download_token"]
    except requests.RequestException:
        logger.exception("Failed to fetch proxy config from Webshare")
        return []
    except (KeyError, ValueError):
        logger.exception("Unexpected response format from Webshare config API")
        return []

    try:
        resp = requests.get(
            WEBSHARE_DOWNLOAD_URL.format(token=download_token),
            timeout=REQUEST_TIMEOUT_SECONDS,
        )
        resp.raise_for_status()
    except requests.RequestException:
        logger.error(
            "Failed to download proxy list from Webshare (HTTP %s)",
            getattr(resp, "status_code", "N/A"),
        )
        return []

    body = resp.text.strip()
    if not body:
        logger.info("Webshare returned an empty proxy list")
        return []

    proxies: list[str] = []
    for line in body.splitlines():
        parts = line.split(":")
        if len(parts) == 4:
            ip, port, user, pwd = parts
            proxies.append(f"http://{user}:{pwd}@{ip}:{port}")
        else:
            logger.warning(
                "Skipping malformed proxy line (%d parts, expected 4)",
                len(parts),
            )

    logger.info("Fetched %d proxies from Webshare", len(proxies))
    return proxies
