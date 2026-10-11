from collections import deque
from typing import Deque, List, Optional
from src.engine.adapters import ModelAdapter

DEFAULT_VALID_PATCH = """--- a/src/app.py
+++ b/src/app.py
@@ -1,3 +1,3 @@
 def fix():
-    return False
+    return True
"""

UNSAFE_TRAVERSAL_PATCH = """--- a/../secret.py
+++ b/../secret.py
@@ -1,2 +1,2 @@
-x = 1
+x = 2
"""

UNSAFE_TEST_PATCH = """--- a/tests/test_app.py
+++ b/tests/test_app.py
@@ -1,2 +1,2 @@
-def test_foo(): assert False
+def test_foo(): pass
"""


REFINED_VALID_PATCH = """--- a/src/app.py
+++ b/src/app.py
@@ -1,3 +1,3 @@
 def fix():
-    return False
+    return "refined_pass"
"""

SECOND_BRANCH_VALID_PATCH = """--- a/src/app.py
+++ b/src/app.py
@@ -1,3 +1,3 @@
 def fix():
-    return False
+    return "branch_2_pass"
"""


class FakeModelAdapter(ModelAdapter):
    """
    In-memory deterministic model adapter for engine testing.
    Returns canned completions and records prompt calls.
    Supports a list of canned_responses to return distinct completions across attempts.
    """

    def __init__(
        self,
        canned_response: Optional[str] = None,
        canned_responses: Optional[List[str]] = None,
    ):
        self.canned_response = (
            canned_response if canned_response is not None else DEFAULT_VALID_PATCH
        )
        self.canned_responses: Deque[str] = deque(canned_responses) if canned_responses else deque()
        self.call_count: int = 0
        self.prompts: List[str] = []

    async def complete(self, prompt: str, max_tokens: int = 2048) -> str:
        self.call_count += 1
        self.prompts.append(prompt)
        if self.canned_responses:
            return self.canned_responses.popleft()
        return self.canned_response
