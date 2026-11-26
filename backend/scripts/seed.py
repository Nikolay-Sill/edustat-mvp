"""Заполнение справочников: группы, дисциплины, сотрудники, закрепления staff_subject (FR-05).

Запуск из папки backend:
    python -m scripts.seed                    # справочники + демо-студенты
    python -m scripts.seed --no-demo-students # только справочники

Скрипт идемпотентный: запись ищется по естественному ключу (название группы, e-mail и т. п.)
и создаётся, только если её ещё нет, поэтому повторный запуск не плодит дубли.

Демо-студенты нужны, чтобы GET /students не был пустым до этапа 2. Их lms_external_id
начинается с DEMO-, поэтому они не пересекутся со студентами из OULAD, и их легко удалить.
"""

import argparse
import random
import uuid
from datetime import date, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.academic.models import Staff, StaffSubject, Student, StudyGroup, Subject
from app.core.db import get_sessionmaker

DEMO_PREFIX = "DEMO-"

GROUPS = [
    # (название, курс, направление подготовки)
    ("ИНБО-01-24", 3, "09.03.04 Программная инженерия"),
    ("ИНБО-02-24", 3, "09.03.04 Программная инженерия"),
    ("ИКБО-01-25", 2, "09.03.01 Информатика и вычислительная техника"),
    ("ИКБО-02-25", 2, "09.03.01 Информатика и вычислительная техника"),
]

SUBJECTS = [
    # (название, часы, форма контроля); lms_course_id заполнится на этапе 2 при сопоставлении с OULAD
    ("Базы данных", 144, "EXAM"),
    ("Математический анализ", 180, "EXAM"),
    ("Программирование на Python", 108, "GRADED_CREDIT"),
    ("Иностранный язык", 72, "CREDIT"),
    ("Проектирование информационных систем", 144, "EXAM"),
]

STAFF = [
    # (ФИО, e-mail, кафедра, роль)
    ("Петрова Анна Викторовна", "petrova@edu.example.ru", "Кафедра информационных систем", "TEACHER"),
    ("Смирнов Олег Игоревич", "smirnov@edu.example.ru", "Кафедра высшей математики", "TEACHER"),
    ("Кузнецова Мария Андреевна", "kuznetsova@edu.example.ru", "Кафедра иностранных языков", "TEACHER"),
    ("Волков Дмитрий Павлович", "volkov@edu.example.ru", "Деканат института ИТ", "DEAN_OFFICE"),
    ("Орлов Сергей Николаевич", "orlov@edu.example.ru", "Отдел информационных технологий", "ADMIN"),
]

# Кто что ведёт: e-mail преподавателя → дисциплины; группы — по курсу
ASSIGNMENTS = {
    "petrova@edu.example.ru": {
        3: ["Базы данных", "Проектирование информационных систем"],
        2: ["Программирование на Python"],
    },
    "smirnov@edu.example.ru": {2: ["Математический анализ"]},
    "kuznetsova@edu.example.ru": {3: ["Иностранный язык"], 2: ["Иностранный язык"]},
}

DEMO_STUDENTS_PER_GROUP = [8, 8, 7, 7]

_SURNAMES = [("Иванов", "Иванова"), ("Соколов", "Соколова"), ("Попов", "Попова"), ("Лебедев", "Лебедева"),
             ("Козлов", "Козлова"), ("Новиков", "Новикова"), ("Морозов", "Морозова"), ("Егоров", "Егорова"),
             ("Павлов", "Павлова"), ("Семёнов", "Семёнова"), ("Голубев", "Голубева"), ("Виноградов",
             "Виноградова"), ("Богданов", "Богданова"), ("Фёдоров", "Фёдорова"), ("Михайлов", "Михайлова")]
_MALE = ["Александр", "Максим", "Артём", "Иван", "Никита", "Егор", "Кирилл", "Илья"]
_FEMALE = ["Анастасия", "Дарья", "Полина", "Екатерина", "Софья", "Алиса", "Виктория", "Ксения"]
_PATRONYMICS = [("Сергеевич", "Сергеевна"), ("Андреевич", "Андреевна"), ("Алексеевич", "Алексеевна"),
                ("Дмитриевич", "Дмитриевна"), ("Олегович", "Олеговна")]


def get_or_create(session: Session, model, key: dict, values: dict | None = None):
    """Ищет запись по ключу; если нет — создаёт. Возвращает (объект, создан_ли)."""
    obj = session.scalars(select(model).filter_by(**key)).first()
    if obj is not None:
        return obj, False
    obj = model(**key, **(values or {}))
    session.add(obj)
    session.flush()  # чтобы получить сгенерированный id до коммита
    return obj, True


def _demo_students(groups: list[StudyGroup]):
    """Синтетические студенты; random с фиксированным зерном — набор одинаковый при каждом запуске."""
    rnd = random.Random(42)
    number = 0
    for group, count in zip(groups, DEMO_STUDENTS_PER_GROUP, strict=True):
        for _ in range(count):
            number += 1
            female = rnd.random() < 0.5
            surname = rnd.choice(_SURNAMES)[int(female)]
            name = rnd.choice(_FEMALE if female else _MALE)
            patronymic = rnd.choice(_PATRONYMICS)[int(female)]
            # Год рождения ≈ год поступления − 18; у части студентов дата не указана (поле необязательное)
            birth_date = None if number % 10 == 0 else (
                date(2026 - group.course - 18, 1, 1) + timedelta(days=rnd.randrange(365)))
            yield group, {
                "lms_external_id": f"{DEMO_PREFIX}{number:03d}",
                "full_name": f"{surname} {name} {patronymic}",
                "email": f"student{number:03d}@edu.example.ru",
                "birth_date": birth_date,
            }


def seed(session: Session, demo_students: bool = True) -> dict[str, int]:
    """Заполняет справочники и возвращает число созданных записей по таблицам."""
    created = {"study_group": 0, "subject": 0, "staff": 0, "staff_subject": 0, "student": 0}

    groups = []
    for name, course, specialization in GROUPS:
        group, new = get_or_create(session, StudyGroup, {"group_name": name},
                                   {"course": course, "specialization": specialization})
        groups.append(group)
        created["study_group"] += new

    subjects = {}
    for name, hours, control_form in SUBJECTS:
        subject, new = get_or_create(session, Subject, {"subject_name": name},
                                     {"total_hours": hours, "control_form": control_form})
        subjects[name] = subject
        created["subject"] += new

    staff_by_email = {}
    for full_name, email, department, role in STAFF:
        # В MVP нет Keycloak: идентификатор генерируется случайно (см. комментарий в миграции V2)
        staff, new = get_or_create(session, Staff, {"email": email},
                                   {"full_name": full_name, "department": department, "role": role,
                                    "keycloak_user_id": uuid.uuid4()})
        staff_by_email[email] = staff
        created["staff"] += new

    for email, by_course in ASSIGNMENTS.items():
        for course, subject_names in by_course.items():
            for group in (g for g in groups if g.course == course):
                for subject_name in subject_names:
                    _, new = get_or_create(session, StaffSubject, {
                        "staff_id": staff_by_email[email].staff_id,
                        "subject_id": subjects[subject_name].subject_id,
                        "group_id": group.group_id,
                    })
                    created["staff_subject"] += new

    if demo_students:
        for group, values in _demo_students(groups):
            lms_id = values.pop("lms_external_id")
            _, new = get_or_create(session, Student, {"lms_external_id": lms_id},
                                   {"group_id": group.group_id, **values})
            created["student"] += new

    session.commit()
    return created


def main() -> None:
    parser = argparse.ArgumentParser(description="Заполнение справочников EduStat (FR-05)")
    parser.add_argument("--no-demo-students", action="store_true", help="не создавать демо-студентов")
    args = parser.parse_args()

    with get_sessionmaker()() as session:
        created = seed(session, demo_students=not args.no_demo_students)
    print("Создано записей:", ", ".join(f"{table}={n}" for table, n in created.items()))


if __name__ == "__main__":
    main()
