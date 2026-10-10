import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.Services.Assistant import AssistantService


def test_assistant_process():
    assistant = AssistantService()
    text = "Hello, welcome to the AI Employee Assistant."
    result = assistant.process(text, employee_id="EMP-0013")
    assert result is not None
    assert "response" in result
    assert len(result["response"]) > 0


if __name__ == "__main__":
    test_assistant_process()