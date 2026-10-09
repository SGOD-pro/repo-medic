from src.contracts import HostPorts

class FakeHost:
    def __init__(self):
        self.events = []
        self.artifacts = []
        self.reservations = {}
        self.settlements = {}
        self.is_cancelled = False
    
    async def emit(self, event_type: str, payload: dict) -> None:
        self.events.append({"type": event_type, "payload": payload})
        
    async def save_artifact(self, kind: str, filename: str, content: bytes) -> str:
        self.artifacts.append({"kind": kind, "filename": filename})
        return f"fake_path/{filename}"
        
    async def reserve(self, operation_id: str, estimated_usd: float) -> bool:
        self.reservations[operation_id] = estimated_usd
        return True
        
    async def settle(self, operation_id: str, actual_or_estimated_usd: float) -> None:
        self.settlements[operation_id] = actual_or_estimated_usd
        
    async def cancelled(self) -> bool:
        return self.is_cancelled
        
    async def record_provider_ref(self, operation_id: str, provider_ref: str) -> None:
        pass
