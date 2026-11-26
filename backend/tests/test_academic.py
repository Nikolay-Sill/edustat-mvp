"""Справочник контингента: группы, студенты, дисциплины, закрепления."""

from sqlalchemy import func, select

from app.academic.models import StaffSubject, Student, StudyGroup

API = "/api/v1"


def test_groups_list_all_sorted_by_course_and_name(client, seeded):
    """FR-05: список групп отдаёт все группы справочника по курсу и названию."""
    body = client.get(f"{API}/groups").json()

    assert body["total_elements"] == 4
    names = [g["group_name"] for g in body["items"]]
    assert names == ["ИКБО-01-25", "ИКБО-02-25", "ИНБО-01-24", "ИНБО-02-24"]
    assert set(body["items"][0]) == {"group_id", "group_name", "course", "specialization"}


def test_groups_filter_by_course(client, seeded):
    """FR-05: фильтр групп по курсу."""
    body = client.get(f"{API}/groups", params={"course": 3}).json()

    assert body["total_elements"] == 2
    assert all(g["course"] == 3 for g in body["items"])


def test_groups_pagination_meta(client, seeded):
    """FR-05: пагинация page/size и поля PageMeta."""
    body = client.get(f"{API}/groups", params={"page": 2, "size": 3}).json()

    assert (body["page"], body["size"], body["total_elements"], body["total_pages"]) == (2, 3, 4, 2)
    assert len(body["items"]) == 1


def test_page_beyond_last_returns_empty_items(client, seeded):
    """FR-05: страница за пределами списка — пустой items, а не ошибка."""
    body = client.get(f"{API}/groups", params={"page": 10}).json()

    assert body["items"] == []
    assert body["total_elements"] == 4


def test_students_list_has_group_name(client, seeded):
    """FR-05: список студентов с названием группы и пагинацией по умолчанию (20)."""
    body = client.get(f"{API}/students").json()

    assert body["total_elements"] == 30
    assert body["size"] == 20 and len(body["items"]) == 20 and body["total_pages"] == 2
    assert all(s["group_name"] for s in body["items"])


def test_students_filter_by_group(client, db, seeded):
    """FR-05: фильтр студентов по группе."""
    group = db.scalars(select(StudyGroup).filter_by(group_name="ИНБО-01-24")).one()

    body = client.get(f"{API}/students", params={"group_id": group.group_id}).json()

    assert body["total_elements"] == 8
    assert {s["group_name"] for s in body["items"]} == {"ИНБО-01-24"}


def test_student_card(client, db, seeded):
    """FR-05: карточка студента по id."""
    student = db.scalars(select(Student).filter_by(lms_external_id="DEMO-001")).one()

    body = client.get(f"{API}/students/{student.student_id}").json()

    assert body["student_id"] == student.student_id
    assert body["email"] == "student001@edu.example.ru"
    assert body["group_id"] == student.group_id


def test_student_card_omits_empty_birth_date(client, db, seeded):
    """FR-05: необязательная дата рождения не отдаётся как null (в спецификации поле не nullable)."""
    student = db.scalars(select(Student).where(Student.birth_date.is_(None))).first()

    body = client.get(f"{API}/students/{student.student_id}").json()

    assert "birth_date" not in body


def test_student_not_found(client, seeded):
    """FR-05: несуществующий студент — 404 в формате RFC 7807."""
    response = client.get(f"{API}/students/999999")

    assert response.status_code == 404
    assert response.headers["content-type"] == "application/problem+json"
    assert response.json()["status"] == 404


def test_subjects_list_all(client, seeded):
    """FR-05: список дисциплин без пагинации (так в спецификации)."""
    body = client.get(f"{API}/subjects").json()

    assert set(body) == {"items"}
    assert len(body["items"]) == 5


def test_subjects_filter_by_group_uses_staff_subject(client, db, seeded):
    """FR-05: дисциплины группы — те, что закреплены за преподавателями в этой группе."""
    group = db.scalars(select(StudyGroup).filter_by(group_name="ИКБО-01-25")).one()

    body = client.get(f"{API}/subjects", params={"group_id": group.group_id}).json()

    names = {s["subject_name"] for s in body["items"]}
    assert names == {"Программирование на Python", "Математический анализ", "Иностранный язык"}


def test_seed_is_idempotent(db, seeded):
    """FR-05: повторное заполнение справочников не создаёт дублей."""
    from scripts.seed import seed

    assert seeded["staff_subject"] == 12 and seeded["student"] == 30
    assert all(n == 0 for n in seed(db).values())
    assert db.scalar(select(func.count()).select_from(StaffSubject)) == 12
