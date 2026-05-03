import reqeusts


def fetch(url):
    return reqeusts.get(url).text
