import requests


def notify(message):
    return requests.post(
        "https://discord.com/api/webhooks/000000000000000000/AAAAAAAAAAAAAAAAAAAAAA",
        json={"text": message},
    )
