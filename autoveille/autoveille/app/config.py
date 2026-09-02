import os
import yaml

CONFIG_PATH = os.environ.get("CONFIG_PATH", "config.yml")


def charger():
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)
