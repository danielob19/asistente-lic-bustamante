from pydantic import BaseModel


class UserInput(BaseModel):
    mensaje: str
    user_id: str
