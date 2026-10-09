import * as fs from 'fs';
import { TaskRecipe, RepairResult, RunDetail, ReconnectResult, RunHistoryItem } from './src/lib/contracts';

function test_fixtures() {
    const taskJson = fs.readFileSync('../fixtures/tasks/example-task-1.json', 'utf-8');
    const task: TaskRecipe = JSON.parse(taskJson);
    if (!task.task_id) throw new Error("Missing task_id");

    const runJson = fs.readFileSync('../fixtures/runs/success.json', 'utf-8');
    const run = JSON.parse(runJson);
    const result: RepairResult = { state: run.state, reason: run.reason };
    if (!result.state) throw new Error("Missing state");

    const failureJson = fs.readFileSync('../fixtures/runs/failure.json', 'utf-8');
    const failure: RunDetail = JSON.parse(failureJson);
    if (!failure.state) throw new Error("Missing state in failure");

    const cancelJson = fs.readFileSync('../fixtures/runs/cancel.json', 'utf-8');
    const cancel: RunDetail = JSON.parse(cancelJson);
    if (!cancel.state) throw new Error("Missing state in cancel");

    const reconnectJson = fs.readFileSync('../fixtures/runs/reconnect.json', 'utf-8');
    const reconnect: ReconnectResult = JSON.parse(reconnectJson);
    if (!reconnect.events) throw new Error("Missing events in reconnect");

    const historyJson = fs.readFileSync('../fixtures/runs/history.json', 'utf-8');
    const history: RunHistoryItem[] = JSON.parse(historyJson);
    if (!history[0].state) throw new Error("Missing state in history");

    console.log("TypeScript smoke test passed");
}

test_fixtures();
