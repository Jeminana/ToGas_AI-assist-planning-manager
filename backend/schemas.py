"""Shared API validation; the decision engine does not write to the database."""
from datetime import date, datetime
import re
from typing import Annotated, Literal
from uuid import UUID
from pydantic import BaseModel, BeforeValidator, ConfigDict, Field, StrictBool, StringConstraints, field_validator


def parse_date(value):
    if isinstance(value, date) and not isinstance(value, datetime):
        return value
    if not isinstance(value, str) or not re.fullmatch(r'\d{4}-\d{2}-\d{2}', value):
        raise ValueError('Use a date in YYYY-MM-DD format')
    return date.fromisoformat(value)


ISODate = Annotated[date, BeforeValidator(parse_date)]
TaskTitle = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=250)]
TaskCategory = Literal['study', 'work', 'personal', 'health', 'other']
UrgencyScore = Annotated[float, Field(ge=0, le=3, allow_inf_nan=False, strict=True)]


class RequestInput(BaseModel):
    model_config = ConfigDict(extra='forbid')


class JournalInput(RequestInput):
    text: str = Field(min_length=1, max_length=10000)

    @field_validator('text')
    @classmethod
    def reject_blank_text(cls, value):
        if not value.strip():
            raise ValueError('Journal text cannot be blank')
        return value


class JournalCreate(JournalInput):
    request_id: UUID | None = None


class AnalysisInput(JournalInput):
    reference_date: ISODate | None = None
    journal_id: int | None = Field(default=None, ge=1, strict=True)


class PriorityInput(RequestInput):
    reference_date: ISODate | None = None


class TaskInput(RequestInput):
    title: TaskTitle
    category: TaskCategory = 'other'
    urgency_score: UrgencyScore = 1
    due_date: ISODate | None = None
    journal_id: int | None = Field(default=None, ge=1, strict=True)


class TaskPatch(RequestInput):
    title: TaskTitle | None = None
    done: StrictBool | None = None
    category: TaskCategory | None = None
    urgency_score: UrgencyScore | None = None
    due_date: ISODate | None = None
