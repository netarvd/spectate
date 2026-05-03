import requests


def notify(message):
    return requests.post("https://api.example.com/notify", json={"text": message})
