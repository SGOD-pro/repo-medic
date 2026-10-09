import os
import json

fixtures_dir = 'fixtures'

with open(f'{fixtures_dir}/runs/failure.json', 'w') as f:
    json.dump({
        "run_id": "run-fail-1",
        "task_id": "example-task-1",
        "mode": "offline",
        "search_mode": "sequential",
        "max_run_usd": 10.0,
        "state": "failed",
        "reason": "Baseline check failed"
    }, f, indent=2)

with open(f'{fixtures_dir}/runs/cancel.json', 'w') as f:
    json.dump({
        "run_id": "run-cancel-1",
        "task_id": "example-task-1",
        "mode": "offline",
        "search_mode": "sequential",
        "max_run_usd": 10.0,
        "state": "cancelled",
        "reason": "User cancelled"
    }, f, indent=2)

with open(f'{fixtures_dir}/runs/history.json', 'w') as f:
    json.dump([
        {"run_id": "run-success-1", "state": "succeeded"},
        {"run_id": "run-fail-1", "state": "failed"},
        {"run_id": "run-cancel-1", "state": "cancelled"}
    ], f, indent=2)

with open(f'{fixtures_dir}/runs/reconnect.json', 'w') as f:
    json.dump({
        "run_id": "run-reconnect-1",
        "events": [
            {"seq": 1, "type": "status", "payload": {"message": "Starting repair"}},
            {"seq": 2, "type": "status", "payload": {"message": "Baseline check passed"}}
        ]
    }, f, indent=2)

print("More fixtures generated")
