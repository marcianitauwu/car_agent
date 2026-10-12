"""Contratos estrictos para las decisiones de las llamadas a modelos."""
from typing import Literal
from pydantic import BaseModel, Field, ConfigDict, field_validator

AgentKey = Literal['comfort', 'consumption', 'economy']
PolicyCategory = Literal[
    'allowed', 'off_topic', 'code_request', 'prompt_injection',
    'secrets', 'privacy', 'external_source', 'unsafe_output', 'unknown',
]


class ChatRequest(BaseModel):
    message: str = Field(min_length=3, max_length=700)


class ApprovedQuestion(BaseModel):
    question: str


class PolicyDecision(BaseModel):
    model_config = ConfigDict(extra='forbid')
    allowed: bool
    category: PolicyCategory
    refined_question: str | None = Field(default=None, min_length=3, max_length=700)

    @field_validator('category')
    @classmethod
    def category_compatible(cls, value: str, info):
        allowed = info.data.get('allowed')
        if allowed is True and value != 'allowed':
            raise ValueError('decision inconsistente')
        if allowed is False and value == 'allowed':
            raise ValueError('decision inconsistente')
        return value


class PolicyReview(BaseModel):
    model_config = ConfigDict(extra='forbid')
    approved: bool
    category: PolicyCategory


class RoutingDecision(BaseModel):
    question: str
    agents: list[AgentKey] = Field(min_length=1, max_length=2)
    reason: str = Field(max_length=180)

    @field_validator('agents')
    @classmethod
    def unique_agents(cls, value: list[str]) -> list[str]:
        if len(value) != len(set(value)):
            raise ValueError('Agentes duplicados')
        return value
