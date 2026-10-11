import re
from typing import List, Tuple

# Regex to detect python tracebacks
TRACEBACK_PATTERN = re.compile(
    r"(Traceback \(most recent call last\):[\s\S]*?(?:[A-Za-z0-9_]+Error|Exception):[^\n]+)",
    re.MULTILINE,
)

# Regex to detect pytest failure headers and failure lines
PYTEST_FAILURE_BLOCK = re.compile(
    r"_{3,}\s+[^\n]+\s+_{3,}[\s\S]*?(?=(?:_{3,}|\Z|=+ short test summary info =+))",
    re.MULTILINE,
)

PYTEST_SUMMARY_LINE = re.compile(r"FAILED\s+([^\s:]+)(?:::([^\s]+))?\s*-\s*([^\n]+)")

FILE_PATH_PATTERN = re.compile(
    r'(?:File "([^"]+)", line \d+|([a-zA-Z0-9_\-./\\]+\.py)(?::\d+)?)'
)


def extract_error_context(log_text: str) -> Tuple[str, List[str]]:
    """
    Extracts concise error traceback blocks and failing file names from execution logs.
    Falls back to a bounded tail of the log when structured tracebacks are not detected.
    """
    if not log_text or not log_text.strip():
        return "", []

    extracted_blocks: List[str] = []
    detected_files: set[str] = set()

    # 1. Search for standard python tracebacks
    tb_matches = TRACEBACK_PATTERN.findall(log_text)
    for tb in tb_matches:
        extracted_blocks.append(tb.strip())

    # 2. Search for pytest failure sections if no traceback found
    if not extracted_blocks:
        pytest_matches = PYTEST_FAILURE_BLOCK.findall(log_text)
        for pm in pytest_matches:
            extracted_blocks.append(pm.strip())

    # 3. Search for summary lines
    summary_matches = PYTEST_SUMMARY_LINE.findall(log_text)
    if summary_matches and not extracted_blocks:
        for sm in summary_matches:
            file_part = sm[0]
            err_part = sm[2]
            extracted_blocks.append(f"FAILED {file_part} - {err_part}")

    # Fallback to bounded tail of log if regex finds nothing
    if not extracted_blocks:
        lines = log_text.strip().splitlines()
        tail_lines = lines[-50:] if len(lines) > 50 else lines
        extracted_text = "\n".join(tail_lines)
    else:
        extracted_text = "\n\n".join(extracted_blocks)

    # Extract referenced file paths
    file_matches = FILE_PATH_PATTERN.findall(extracted_text)
    for m1, m2 in file_matches:
        f = m1 or m2
        if f and not f.startswith("<") and f.endswith(".py"):
            detected_files.add(f)

    return extracted_text, sorted(list(detected_files))
