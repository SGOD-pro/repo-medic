from pydantic import BaseModel, Field


class UserProfile(BaseModel):
    username: str = Field(..., regex="^[a-zA-Z0-9_]+$")
    display_name: str = Field(..., max_length=50)
    age: int = Field(..., ge=0, le=150)


def create_user_profile(username: str, display_name: str, age: int) -> dict:
    profile = UserProfile(username=username, display_name=display_name, age=age)
    return {
        "username": profile.username,
        "display_name": profile.display_name,
        "age": profile.age,
    }
