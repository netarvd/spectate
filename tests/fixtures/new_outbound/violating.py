import requests


def fetch():
    return requests.get("https://telemetry.somerandom.dev/collect").json()
