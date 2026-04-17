from pydantic import BaseModel, Field


class RunCreateBody(BaseModel):
    company_name: str | None = Field(default=None)
    company_url: str | None = Field(default=None)
