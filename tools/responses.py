def tool_response(*, tool, success, data=None, error=None, meta=None):
    return {
        "tool": tool,
        "success": success,
        "data": {
            "value": data,
            "meta": meta
        },
        "error": error
    }
