"""Схемы ответов: повторяют Group, Student, Subject из edustat-openapi.yaml."""

from datetime import date
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class Group(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    group_id: int
    group_name: str = Field(examples=["ИНБО-11-23"])
    course: int = Field(ge=1, le=6)
    specialization: str


class Student(BaseModel):
    student_id: int
    full_name: str
    email: str
    # В БД поле может быть NULL; в спецификации оно не nullable, поэтому пустое значение
    # не отдаём вовсе (response_model_exclude_none в роутере)
    birth_date: date | None = None
    group_id: int
    group_name: str

    @classmethod
    def from_model(cls, student) -> "Student":
        return cls(
            student_id=student.student_id,
            full_name=student.full_name,
            email=student.email,
            birth_date=student.birth_date,
            group_id=student.group_id,
            group_name=student.group.group_name,
        )


class Subject(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    subject_id: int
    subject_name: str
    total_hours: int
    control_form: Literal["EXAM", "CREDIT", "GRADED_CREDIT"]


class SubjectList(BaseModel):
    """GET /subjects в спецификации возвращает только items, без пагинации."""

    items: list[Subject]
