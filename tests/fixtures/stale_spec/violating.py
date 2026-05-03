import pydantic
import requests


class Item(pydantic.BaseModel):
    name: str


def fetch(url):
    return Item(name=requests.get(url).text)
