
from app.services.tool_registry import registry

def run_agent_step(command: dict):
    tool = command.get("tool")
    args = command.get("args", {})

    if not tool:
        return {"error": "No tool specified"}

    try:
        result = registry.execute(tool, **args)
        return {"result": result}
    except Exception as e:
        return {"error": str(e)}
