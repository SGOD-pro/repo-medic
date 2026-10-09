class FakeProvider:
    async def invoke_model(self, prompt: str) -> str:
        return "Fake patch generated"
        
    async def create_sandbox(self) -> str:
        return "fake_sandbox_id"
        
    async def execute_command(self, sandbox_id: str, command: str) -> str:
        return "Command executed successfully"
