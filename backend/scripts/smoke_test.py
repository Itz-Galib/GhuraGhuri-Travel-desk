"""Smoke test script against a deployed API URL (T6.4)."""

import sys

import httpx


def main() -> int:
    base_url = sys.argv[1].rstrip("/") if len(sys.argv) > 1 else "http://localhost:8000"
    with httpx.Client(base_url=base_url, timeout=15.0) as client:
        for path in ("/health", "/health/ready", "/api/v1/tours", "/api/v1/offers"):
            res = client.get(path)
            print(f"GET {path} -> {res.status_code}")
            res.raise_for_status()
    print("Smoke test passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
