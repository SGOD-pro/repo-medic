import * as fs from 'fs';
import { TaskRecipe, RepairResult } from './src/lib/contracts';

function test_fixtures() {
    const taskJson = fs.readFileSync('../fixtures/tasks/example-task-1.json', 'utf-8');
    const task: TaskRecipe = JSON.parse(taskJson);
    if (!task.task_id) throw new Error("Missing task_id");

    const runJson = fs.readFileSync('../fixtures/runs/success.json', 'utf-8');
    const run = JSON.parse(runJson);
    const result: RepairResult = { state: run.state, reason: run.reason };
    if (!result.state) throw new Error("Missing state");

    console.log("TypeScript smoke test passed");
}

test_fixtures();
