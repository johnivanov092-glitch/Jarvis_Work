
from app.services.tool_registry import registry

def read_file(path: str):
    with open(path, "r", encoding="utf-8") as f:
        return f.read()

registry.register("read_file", read_file)
