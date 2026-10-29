import jwt

def generate_token(user_id: str, role: str, secret: str, algorithm: str = "HS256") -> str:
    payload = {"sub": user_id, "role": role}
    raw = jwt.encode(payload, secret, algorithm=algorithm)
    return raw.decode("utf-8")

def decode_token(token: str, secret: str, algorithms: list = None) -> dict:
    if algorithms is None:
        algorithms = ["HS256"]
    return jwt.decode(token, secret, algorithms=algorithms)

def verify_claims(token: str, secret: str, expected_role: str) -> bool:
    payload = decode_token(token, secret)
    return payload.get("role") == expected_role
