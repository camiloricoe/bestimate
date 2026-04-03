"""Realistic Chrome browser headers for anti-detection."""

import random

# Current Chrome versions (update monthly)
CHROME_VERSIONS = [
    "124.0.0.0",
    "123.0.0.0",
    "122.0.0.0",
    "125.0.0.0",
]

PLATFORMS = [
    ("Windows", '"Windows"'),
    ("macOS", '"macOS"'),
]

ACCEPT_LANGUAGES = [
    "en-US,en;q=0.9",
    "en-US,en;q=0.8",
    "en-US,en;q=0.9,es;q=0.8",
    "en,en-US;q=0.9",
]


def generate_chrome_headers(referer: str | None = None) -> dict[str, str]:
    """Generate headers that exactly match a real Chrome browser.

    The order of headers matters - Chrome sends them in a specific sequence.
    """
    version = random.choice(CHROME_VERSIONS)
    major = version.split(".")[0]
    platform_name, platform_hint = random.choice(PLATFORMS)

    headers = {
        "accept": (
            "text/html,application/xhtml+xml,application/xml;q=0.9,"
            "image/avif,image/webp,image/apng,*/*;q=0.8,"
            "application/signed-exchange;v=b3;q=0.7"
        ),
        "accept-language": random.choice(ACCEPT_LANGUAGES),
        "accept-encoding": "gzip, deflate, br, zstd",
        "cache-control": "max-age=0",
        "sec-ch-ua": f'"Chromium";v="{major}", "Google Chrome";v="{major}", "Not-A.Brand";v="99"',
        "sec-ch-ua-mobile": "?0",
        "sec-ch-ua-platform": platform_hint,
        "sec-fetch-dest": "document",
        "sec-fetch-mode": "navigate",
        "sec-fetch-site": "same-origin" if referer and "zillow.com" in referer else "none",
        "sec-fetch-user": "?1",
        "upgrade-insecure-requests": "1",
        "user-agent": (
            f"Mozilla/5.0 ({_os_string(platform_name)}) "
            f"AppleWebKit/537.36 (KHTML, like Gecko) "
            f"Chrome/{version} Safari/537.36"
        ),
    }

    if referer:
        headers["referer"] = referer

    return headers


def _os_string(platform_name: str) -> str:
    if platform_name == "Windows":
        return "Windows NT 10.0; Win64; x64"
    return "Macintosh; Intel Mac OS X 10_15_7"
