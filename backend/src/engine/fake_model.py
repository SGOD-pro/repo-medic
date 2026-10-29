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

JWT_VALID_PATCH = """--- a/src/auth/tokens.py
+++ b/src/auth/tokens.py
@@ -1,7 +1,7 @@
 import jwt

 def generate_token(user_id: str, role: str, secret: str, algorithm: str = "HS256") -> str:
-    payload = {"sub": user_id, "role": role}
-    raw = jwt.encode(payload, secret, algorithm=algorithm)
-    return raw.decode("utf-8")
+    payload = {"sub": user_id, "role": role}
+    encoded = jwt.encode(payload, secret, algorithm=algorithm)
+    return encoded

 def decode_token(token: str, secret: str, algorithms: list = None) -> dict:
     if algorithms is None:
"""

SHOP_VALID_PATCH = """--- a/src/shop/database.py
+++ b/src/shop/database.py
@@ -6,16 +6,17 @@
-def init_db():
-    engine.execute(
-        text(
-            "CREATE TABLE products (id INTEGER PRIMARY KEY, name TEXT, price REAL, stock INTEGER)"
-        )
-    )
-    engine.execute(
-        text(
-            "INSERT INTO products (name, price, stock) VALUES ('Espresso Mug', 12.99, 50)"
-        )
-    )
-    engine.execute(
-        text(
-            "INSERT INTO products (name, price, stock) VALUES ('Coffee Beans', 18.50, 100)"
-        )
-    )
+def init_db():
+    with engine.begin() as conn:
+        conn.execute(
+            text(
+                "CREATE TABLE products (id INTEGER PRIMARY KEY, name TEXT, price REAL, stock INTEGER)"
+            )
+        )
+        conn.execute(
+            text(
+                "INSERT INTO products (name, price, stock) VALUES ('Espresso Mug', 12.99, 50)"
+            )
+        )
+        conn.execute(
+            text(
+                "INSERT INTO products (name, price, stock) VALUES ('Coffee Beans', 18.50, 100)"
+            )
+        )
@@ -24,3 +24,4 @@
-def get_product_count():
-    res = engine.execute(text("SELECT count(*) FROM products"))
-    return res.scalar()
+def get_product_count():
+    with engine.connect() as conn:
+        res = conn.execute(text("SELECT count(*) FROM products"))
+        return res.scalar()
@@ -29,9 +29,10 @@
-def get_product(product_id: int):
-    res = engine.execute(
-        text("SELECT id, name, price, stock FROM products WHERE id = :id"),
-        {"id": product_id},
-    )
-    row = res.fetchone()
-    if row:
-        return {"id": row[0], "name": row[1], "price": row[2], "stock": row[3]}
-    return None
+def get_product(product_id: int):
+    with engine.connect() as conn:
+        res = conn.execute(
+            text("SELECT id, name, price, stock FROM products WHERE id = :id"),
+            {"id": product_id},
+        )
+        row = res.fetchone()
+        if row:
+            return {"id": row[0], "name": row[1], "price": row[2], "stock": row[3]}
+        return None
"""

CLICK_VALID_PATCH = """--- a/src/cli/terminal.py
+++ b/src/cli/terminal.py
@@ -1,5 +1,5 @@
-import click
+import shutil

 def get_width():
-    return click.get_terminal_size()[0]
+    return shutil.get_terminal_size((80, 24))[0]
"""

PYDANTIC_VALID_PATCH = """--- a/src/users/schemas.py
+++ b/src/users/schemas.py
@@ -1,6 +1,6 @@
 from pydantic import BaseModel, Field

 class User(BaseModel):
     username: str
-    email: str = Field(..., regex=r"^[\\w\\.-]+@[\\w\\.-]+\\.\\w+$")
+    email: str = Field(..., pattern=r"^[\\w\\.-]+@[\\w\\.-]+\\.\\w+$")
"""

DEMO_TASK_CANNED_PATCHES = {
    "TASK-DEMO-JWT": JWT_VALID_PATCH,
    "TASK-DEMO-SHOP": SHOP_VALID_PATCH,
    "TASK-DEMO-CLICK": CLICK_VALID_PATCH,
    "TASK-DEMO-PYDANTIC": PYDANTIC_VALID_PATCH,
}


def get_canned_patch_for_recipe(recipe: any) -> Optional[str]:
    """Returns task-specific canned patch for offline simulation or None if unsupported."""
    task_id = getattr(recipe, "task_id", "")
    if task_id in DEMO_TASK_CANNED_PATCHES:
        return DEMO_TASK_CANNED_PATCHES[task_id]

    # For unit tests using synthetic recipes with allowed paths containing src/app.py
    allowed = getattr(recipe, "allowed_source_paths", []) or []
    for p in allowed:
        norm = p.replace("\\", "/").strip().lstrip("/")
        if norm == "src/app.py" or norm == "src/":
            return DEFAULT_VALID_PATCH

    return None


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
