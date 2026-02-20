from tools.responses import tool_response
from tools.schemas import TextTransformInput
import re


def run_text(data: TextTransformInput):
    try:
        text = data.text or ""
        operation = data.operation

        if operation == "word_count":
            result =  len(text.split())
            

        elif operation == "char_count":
            result =  len(text)
            

        elif operation == "sentence_count":
            sentences = re.split(r"[.!?]+", text)
            result =  len([s for s in sentences if s.strip()])
            

        elif operation == "uppercase":
            result =  text.upper()
            

        elif operation == "lowercase":
            result =  text.lower()
            

        elif operation == "titlecase":
            result =  text.title()
        

        else:
            raise ValueError(f"Invalid text operation: {operation}")

        return tool_response(
            tool="text_transform",
            success=True,
            data=result,
            meta=data.operation
        )

    except Exception as e:
        return tool_response(
            tool="text_transform",
            success=False,
            error=str(e)
        )












