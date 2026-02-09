#!/usr/bin/env python3

import ssl
import sys
import urllib.request
import urllib.error

HEALTH_URL = "https://localhost:8080/health"
TIMEOUT = 2

# Allow self-signed certificates for HTTPS requests (if needed)
ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE


def main() -> None:
    try:
        with urllib.request.urlopen(HEALTH_URL, timeout=TIMEOUT, context=ctx) as response:
            if response.status != 200:
                sys.exit(1)
    except (urllib.error.URLError, TimeoutError):
        sys.exit(1)


if __name__ == "__main__":
    main()
