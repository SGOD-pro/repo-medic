import json
import sys
from src.contracts import TaskRecipe, RepairRequest, RepairResult, RunDetail

def test_fixtures():
    # Load fixtures
    with open('../fixtures/tasks/example-task-1.json') as f:
        TaskRecipe.model_validate_json(f.read())
        
    with open('../fixtures/runs/success.json') as f:
        RunDetail.model_validate_json(f.read())

    with open('../fixtures/runs/failure.json') as f:
        RunDetail.model_validate_json(f.read())

    with open('../fixtures/runs/cancel.json') as f:
        RunDetail.model_validate_json(f.read())

    with open('../fixtures/runs/reconnect.json') as f:
        from src.contracts import ReconnectResult
        ReconnectResult.model_validate_json(f.read())

    with open('../fixtures/runs/history.json') as f:
        from src.contracts import RunHistoryItem
        import json
        data = json.load(f)
        for item in data:
            RunHistoryItem.model_validate(item)

    print("Python smoke test passed")

if __name__ == "__main__":
    test_fixtures()
