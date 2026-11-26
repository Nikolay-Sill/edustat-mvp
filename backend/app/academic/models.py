"""ORM-модели справочника контингента (схема academic, миграция V1). FR-05, FR-24."""

import uuid
from datetime import date

from sqlalchemy import ForeignKey, SmallInteger, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.db import Base


class StudyGroup(Base):
    __tablename__ = "study_group"
    __table_args__ = {"schema": "academic"}

    group_id: Mapped[int] = mapped_column(primary_key=True)
    group_name: Mapped[str] = mapped_column(String(20))
    course: Mapped[int] = mapped_column(SmallInteger)
    specialization: Mapped[str] = mapped_column(String(150))


class Student(Base):
    __tablename__ = "student"
    __table_args__ = {"schema": "academic"}

    student_id: Mapped[int] = mapped_column(primary_key=True)
    group_id: Mapped[int] = mapped_column(ForeignKey("academic.study_group.group_id"))
    full_name: Mapped[str] = mapped_column(String(150))
    email: Mapped[str] = mapped_column(String(100))
    birth_date: Mapped[date | None]
    lms_external_id: Mapped[str] = mapped_column(String(50))

    # lazy="joined": group_name нужен в каждом ответе, поэтому группа подгружается тем же запросом
    group: Mapped[StudyGroup] = relationship(lazy="joined")


class Subject(Base):
    __tablename__ = "subject"
    __table_args__ = {"schema": "academic"}

    subject_id: Mapped[int] = mapped_column(primary_key=True)
    subject_name: Mapped[str] = mapped_column(String(150))
    total_hours: Mapped[int] = mapped_column(SmallInteger)
    control_form: Mapped[str] = mapped_column(String(20))
    lms_course_id: Mapped[str | None] = mapped_column(String(50))


class Staff(Base):
    __tablename__ = "staff"
    __table_args__ = {"schema": "academic"}

    staff_id: Mapped[int] = mapped_column(primary_key=True)
    full_name: Mapped[str] = mapped_column(String(150))
    email: Mapped[str] = mapped_column(String(100))
    department: Mapped[str] = mapped_column(String(150))
    role: Mapped[str] = mapped_column(String(20))
    keycloak_user_id: Mapped[uuid.UUID]


class StaffSubject(Base):
    """Закрепление: преподаватель ведёт дисциплину в группе (по нему проверяется доступ, FR-24)."""

    __tablename__ = "staff_subject"
    __table_args__ = {"schema": "academic"}

    staff_id: Mapped[int] = mapped_column(ForeignKey("academic.staff.staff_id"), primary_key=True)
    subject_id: Mapped[int] = mapped_column(ForeignKey("academic.subject.subject_id"), primary_key=True)
    group_id: Mapped[int] = mapped_column(ForeignKey("academic.study_group.group_id"), primary_key=True)
