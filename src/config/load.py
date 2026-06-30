import yaml

def load_config(file="params.yaml"):
    with open(file, "r", encoding="utf-8") as f:
        cfg = yaml.safe_load(f)

    return cfg