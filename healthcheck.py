#!/usr/bin/env python3

import sys
import urllib.request
import urllib.error

HEALTH_URL = "http://localhost:8080/health"
TIMEOUT = 2


def main() -> None:
    try:
        with urllib.request.urlopen(HEALTH_URL, timeout=TIMEOUT) as response:
            if response.status != 200:
                sys.exit(1)
    except (urllib.error.URLError, TimeoutError):
        sys.exit(1)


if __name__ == "__main__":
    main()
