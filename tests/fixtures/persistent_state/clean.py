from pathlib import Path


def load_input():
    return Path("./data/input.json").read_text()
