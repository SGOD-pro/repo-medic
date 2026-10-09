import os
import shutil

docs_dir = 'docs'
archive_dir = 'docs/archive'
os.makedirs(archive_dir, exist_ok=True)

# List of docs to review
docs = [
    'ARCHITECTURE.md',
    'DATABASE.md',
    'PRD.md',
    'UI-UX.md',
    'API.md',
    'WORK_PACKAGE_A_FRONTEND.md',
    'WORK_PACKAGE_B_BACKEND.md',
    'WORK_PACKAGE_C_ENGINE.md',
]

for doc in docs:
    path = os.path.join(docs_dir, doc)
    if not os.path.exists(path):
        continue
    with open(path, 'r') as f:
        content = f.read()
    
    conflict = False
    # Check for conflicts
    if 'access-code' in content.lower() or 'session' in content.lower():
        conflict = True
    if 'sqlite' in content.lower() and 'd1' not in content.lower():
        conflict = True
    
    if conflict:
        # Check if we should archive it. Actually, if they are meant to be in the repo, 
        # moving them leaves the repo without the 12 docs.
        # But the prompt says "archive conflicting older instructions".
        print(f"Archiving {doc}")
        shutil.move(path, os.path.join(archive_dir, f"{doc}_old"))

