import json
import sys
from src.contracts import TaskRecipe, RepairRequest, RepairResult

def test_fixtures():
    # Load fixtures
    with open('../fixtures/tasks/example-task-1.json') as f:
        TaskRecipe.model_validate_json(f.read())
        
    with open('../fixtures/runs/success.json') as f:
        data = json.load(f)
        # Verify run_id exists before we map it to RepairRequest?
        # Our success.json doesn't match RepairResult, it matches a subset of Run. Wait, success.json has "state", "reason".
        RepairResult.model_validate({"state": data["state"], "reason": data.get("reason")})
        
    print("Python smoke test passed")

if __name__ == "__main__":
    test_fixtures()
