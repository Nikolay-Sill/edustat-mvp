"""Справочник контингента: группы, студенты, дисциплины (FR-05).

Пока без авторизации: проверка JWT и закреплений преподавателя (FR-24) появится на этапе 5.
ORM-модели и схемы ответов называются одинаково (Student, Subject), поэтому импортируются модулями.
"""

from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.academic import models, schemas
from app.core.db import get_db
from app.core.errors import ProblemException
from app.core.pagination import Page, PageParams, page_params, paginate
from app.core.schemas import PROBLEM_RESPONSES

router = APIRouter(tags=["Academic"])

DbSession = Annotated[Session, Depends(get_db)]
Paging = Annotated[PageParams, Depends(page_params)]


@router.get("/groups", response_model=Page[schemas.Group], operation_id="listGroups",
            summary="Список учебных групп", responses=PROBLEM_RESPONSES(400))
def list_groups(db: DbSession, paging: Paging,
                course: Annotated[int | None, Query(ge=1, le=6)] = None) -> Page[schemas.Group]:
    group = models.StudyGroup
    stmt = select(group).order_by(group.course, group.group_name)
    if course is not None:
        stmt = stmt.where(group.course == course)
    return paginate(db, stmt, paging, schemas.Group.model_validate)


@router.get("/students", response_model=Page[schemas.Student], response_model_exclude_none=True,
            operation_id="listStudents", summary="Список студентов с фильтрами",
            responses=PROBLEM_RESPONSES(400))
def list_students(db: DbSession, paging: Paging,
                  group_id: Annotated[int | None, Query()] = None) -> Page[schemas.Student]:
    student = models.Student
    stmt = select(student).order_by(student.full_name, student.student_id)
    if group_id is not None:
        stmt = stmt.where(student.group_id == group_id)
    return paginate(db, stmt, paging, schemas.Student.from_model)


@router.get("/students/{student_id}", response_model=schemas.Student, response_model_exclude_none=True,
            operation_id="getStudent", summary="Карточка студента", responses=PROBLEM_RESPONSES(400, 404))
def get_student(student_id: int, db: DbSession) -> schemas.Student:
    student = db.get(models.Student, student_id)
    if student is None:
        raise ProblemException(404, f"Студент с id={student_id} не найден", "Not Found")
    return schemas.Student.from_model(student)


@router.get("/subjects", response_model=schemas.SubjectList, operation_id="listSubjects",
            summary="Список дисциплин", responses=PROBLEM_RESPONSES(400))
def list_subjects(db: DbSession, group_id: Annotated[int | None, Query()] = None) -> schemas.SubjectList:
    subject = models.Subject
    stmt = select(subject).order_by(subject.subject_name, subject.subject_id)
    if group_id is not None:
        # Дисциплины группы — те, что закреплены за преподавателями в этой группе (staff_subject)
        in_group = select(models.StaffSubject.subject_id).where(models.StaffSubject.group_id == group_id)
        stmt = stmt.where(subject.subject_id.in_(in_group))
    return schemas.SubjectList(items=[schemas.Subject.model_validate(s) for s in db.scalars(stmt)])
