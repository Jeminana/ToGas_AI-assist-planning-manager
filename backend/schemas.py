"""Shared API validation; the decision engine does not write to the database."""
from datetime import date, datetime, time, timezone, timedelta
import re
from typing import Annotated, Literal
from uuid import UUID
from pydantic import BaseModel, BeforeValidator, ConfigDict, Field, StrictBool, StringConstraints, field_validator, model_validator


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
FivePoint = Annotated[int, Field(ge=1, le=5, strict=True)]
Minutes = Annotated[int, Field(gt=0, le=1440, strict=True)]


def parse_local_datetime(value):
    if not isinstance(value, str) or not re.fullmatch(r'\d{4}-\d{2}-\d{2}T\d{2}:\d{2}(?::\d{2}(?:\.\d{1,6})?)?(?:Z|[+-]\d{2}:\d{2})?', value):
        raise ValueError('Use an ISO datetime, for example 2026-11-14T09:00 (Asia/Seoul)')
    stamp = datetime.fromisoformat(value)
    if stamp.tzinfo:
        stamp = stamp.astimezone(timezone(timedelta(hours=9))).replace(tzinfo=None)
    return stamp


LocalDateTime = Annotated[datetime, BeforeValidator(parse_local_datetime)]


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
    request_id: UUID | None = None
    importance: FivePoint = 3
    estimated_minutes: Minutes | None = None
    effort_level: FivePoint = 3
    scheduled_start: LocalDateTime | None = None


class TaskPatch(RequestInput):
    title: TaskTitle | None = None
    done: StrictBool | None = None
    category: TaskCategory | None = None
    urgency_score: UrgencyScore | None = None
    due_date: ISODate | None = None
    importance: FivePoint | None = None
    estimated_minutes: Minutes | None = None
    effort_level: FivePoint | None = None
    scheduled_start: LocalDateTime | None = None


class TimeWindow(RequestInput):
    start: str
    end: str

    @model_validator(mode='after')
    def valid_window(self):
        for value in [self.start, self.end]:
            if not re.fullmatch(r'\d{2}:\d{2}', value):
                raise ValueError('Availability times must use HH:MM')
            time.fromisoformat(value)
        if self.end <= self.start:
            raise ValueError('Availability end must be later than start on the same day')
        return self


class AvailabilityInput(RequestInput):
    date: ISODate
    windows: list[TimeWindow] = Field(min_length=1, max_length=12)
    max_tasks: int = Field(ge=1, le=50, strict=True)

    @model_validator(mode='after')
    def disjoint_windows(self):
        self.windows.sort(key=lambda window: window.start)
        if any(left.end > right.start for left, right in zip(self.windows, self.windows[1:])):
            raise ValueError('Availability windows must not overlap')
        return self


class PlanningContext(RequestInput):
    energy_level: Literal['low', 'medium', 'high']
    source: Literal['user'] = 'user'
    valid_for_date: ISODate


class PlanInput(RequestInput):
    date: ISODate
    context: PlanningContext | None = None
    plan_from_now: StrictBool = False


class PlanConfirmation(RequestInput):
    plan: dict
