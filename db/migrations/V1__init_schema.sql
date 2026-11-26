-- =====================================================================
-- EduStat — DDL физической модели данных (PostgreSQL 16)
-- Источник: раздел 6 проектной документации, Рисунок 6.1 (IDEF1X)
-- с учётом изменений из edustat_schema_changes.sql.
--
-- Тестовая среда: все таблицы в одной базе, в схемах academic,
-- integration и analytics (раздел 6.3). В продуктивной среде таблицы
-- разнесены по базам сервисов (Таблица 6.1), а межсервисные связи
-- хранятся без внешних ключей (раздел 6.1).
-- 11 таблиц: 5 academic + 3 integration + 3 analytics.
-- =====================================================================

CREATE SCHEMA IF NOT EXISTS academic;
CREATE SCHEMA IF NOT EXISTS integration;
CREATE SCHEMA IF NOT EXISTS analytics;

-- ---------------------------------------------------------------------
-- Справочник контингента (Academic Service): FR-05, FR-24
-- ---------------------------------------------------------------------

CREATE TABLE academic.study_group (
    group_id        INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    group_name      VARCHAR(20)  NOT NULL,
    course          SMALLINT     NOT NULL,
    specialization  VARCHAR(150) NOT NULL,
    CONSTRAINT uq_study_group_name UNIQUE (group_name),
    CONSTRAINT ck_study_group_course CHECK (course BETWEEN 1 AND 6)
);

CREATE TABLE academic.student (
    student_id        INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    group_id          INTEGER      NOT NULL REFERENCES academic.study_group (group_id),
    full_name         VARCHAR(150) NOT NULL,
    email             VARCHAR(100) NOT NULL,
    birth_date        DATE         NULL,
    lms_external_id   VARCHAR(50)  NOT NULL,
    CONSTRAINT uq_student_email           UNIQUE (email),
    CONSTRAINT uq_student_lms_external_id UNIQUE (lms_external_id)  -- сопоставление при загрузке (FR-03)
);
CREATE INDEX ix_student_group     ON academic.student (group_id);
CREATE INDEX ix_student_full_name ON academic.student (lower(full_name));  -- поиск по ФИО (FR-22)

CREATE TABLE academic.subject (
    subject_id     INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    subject_name   VARCHAR(150) NOT NULL,
    total_hours    SMALLINT     NOT NULL,
    control_form   VARCHAR(20)  NOT NULL,
    lms_course_id  VARCHAR(50)  NULL,
    CONSTRAINT ck_subject_hours        CHECK (total_hours > 0),
    CONSTRAINT ck_subject_control_form CHECK (control_form IN ('EXAM', 'CREDIT', 'GRADED_CREDIT')),
    CONSTRAINT uq_subject_lms_course   UNIQUE (lms_course_id)
);

CREATE TABLE academic.staff (
    staff_id          INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    full_name         VARCHAR(150) NOT NULL,
    email             VARCHAR(100) NOT NULL,
    department        VARCHAR(150) NOT NULL,
    role              VARCHAR(20)  NOT NULL,
    keycloak_user_id  UUID         NOT NULL,
    CONSTRAINT uq_staff_email    UNIQUE (email),
    CONSTRAINT uq_staff_keycloak UNIQUE (keycloak_user_id),
    CONSTRAINT ck_staff_role     CHECK (role IN ('TEACHER', 'DEAN_OFFICE', 'ADMIN'))
);

-- Таблица-связка: кто ведёт какую дисциплину в какой группе.
-- Единственная идентифицирующая связь на Рисунке 6.1; по ней проверяется доступ (FR-24).
CREATE TABLE academic.staff_subject (
    staff_id    INTEGER NOT NULL REFERENCES academic.staff (staff_id),
    subject_id  INTEGER NOT NULL REFERENCES academic.subject (subject_id),
    group_id    INTEGER NOT NULL REFERENCES academic.study_group (group_id),
    PRIMARY KEY (staff_id, subject_id, group_id)
);
CREATE INDEX ix_staff_subject_group ON academic.staff_subject (group_id, subject_id);

-- ---------------------------------------------------------------------
-- Цифровой след (LMS Integration Service): FR-01 – FR-03
-- ---------------------------------------------------------------------

CREATE TABLE integration.sync_job (
    sync_job_id     BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    lms_source      VARCHAR(50) NOT NULL,
    status          VARCHAR(20) NOT NULL,
    records_loaded  INTEGER     NULL,
    started_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    finished_at     TIMESTAMPTZ NULL,
    CONSTRAINT ck_sync_job_status  CHECK (status IN ('RUNNING', 'SUCCESS', 'FAILED')),
    CONSTRAINT ck_sync_job_records CHECK (records_loaded IS NULL OR records_loaded >= 0),
    CONSTRAINT ck_sync_job_period  CHECK (finished_at IS NULL OR finished_at >= started_at)
);
-- Поиск последней успешной синхронизации для инкрементальной загрузки (FR-01)
CREATE INDEX ix_sync_job_source_status ON integration.sync_job (lms_source, status, started_at DESC);

CREATE TABLE integration.activity (
    activity_id    BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    student_id     INTEGER     NOT NULL REFERENCES academic.student (student_id),
    subject_id     INTEGER     NOT NULL REFERENCES academic.subject (subject_id),
    sync_job_id    BIGINT      NOT NULL REFERENCES integration.sync_job (sync_job_id),
    lms_record_id  VARCHAR(50) NOT NULL,
    activity_type  VARCHAR(30) NOT NULL,
    duration_sec   INTEGER     NULL,
    occurred_at    TIMESTAMPTZ NOT NULL,
    CONSTRAINT uq_activity_lms_record UNIQUE (lms_record_id),       -- защита от дублей (FR-03)
    CONSTRAINT ck_activity_type CHECK (activity_type IN
        ('LOGIN', 'VIEW_MATERIAL', 'TEST_ATTEMPT', 'ASSIGNMENT_SUBMIT', 'FORUM_POST')),
    CONSTRAINT ck_activity_duration CHECK (duration_sec IS NULL OR duration_sec >= 0)
);
CREATE INDEX ix_activity_student_subject_time
    ON integration.activity (student_id, subject_id, occurred_at DESC);  -- активность за 7/14/30 дней (FR-06)

CREATE TABLE integration.exam_result (
    exam_result_id  BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    student_id      INTEGER      NOT NULL REFERENCES academic.student (student_id),
    subject_id      INTEGER      NOT NULL REFERENCES academic.subject (subject_id),
    sync_job_id     BIGINT       NOT NULL REFERENCES integration.sync_job (sync_job_id),
    lms_record_id   VARCHAR(50)  NOT NULL,
    exam_type       VARCHAR(30)  NOT NULL,
    score           NUMERIC(5,2) NOT NULL,
    max_score       NUMERIC(5,2) NOT NULL,
    exam_date       TIMESTAMPTZ  NOT NULL,
    CONSTRAINT uq_exam_result_lms_record UNIQUE (lms_record_id),
    CONSTRAINT ck_exam_result_type  CHECK (exam_type IN ('TEST', 'CONTROL_WORK', 'MIDTERM', 'EXAM')),
    CONSTRAINT ck_exam_result_score CHECK (max_score > 0 AND score >= 0 AND score <= max_score)
);
CREATE INDEX ix_exam_result_student_subject
    ON integration.exam_result (student_id, subject_id, exam_date DESC);

-- ---------------------------------------------------------------------
-- Аналитика (Analytics Service): FR-07 – FR-17
-- ---------------------------------------------------------------------

CREATE TABLE analytics.model_version (
    model_version_id  INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    algorithm         VARCHAR(50)  NOT NULL,
    version           VARCHAR(20)  NOT NULL,
    roc_auc           NUMERIC(4,3) NOT NULL,
    is_active         BOOLEAN      NOT NULL DEFAULT false,
    CONSTRAINT uq_model_version  UNIQUE (algorithm, version),
    CONSTRAINT ck_model_roc_auc  CHECK (roc_auc BETWEEN 0 AND 1),
    -- NFR-17: версию с ROC-AUC ниже 0,80 нельзя активировать
    CONSTRAINT ck_model_active_quality CHECK (NOT is_active OR roc_auc >= 0.80)
);
-- Активной может быть только одна версия модели (FR-11)
CREATE UNIQUE INDEX uq_model_version_single_active
    ON analytics.model_version (is_active) WHERE is_active;

CREATE TABLE analytics.prediction (
    prediction_id     BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    student_id        INTEGER      NOT NULL REFERENCES academic.student (student_id),
    subject_id        INTEGER      NOT NULL REFERENCES academic.subject (subject_id),
    model_version_id  INTEGER      NOT NULL REFERENCES analytics.model_version (model_version_id),
    risk_probability  NUMERIC(4,3) NOT NULL,
    risk_level        VARCHAR(10)  NOT NULL,
    predicted_grade   NUMERIC(3,1) NULL,
    created_at        TIMESTAMPTZ  NOT NULL DEFAULT now(),
    CONSTRAINT ck_prediction_probability CHECK (risk_probability BETWEEN 0 AND 1),
    CONSTRAINT ck_prediction_level       CHECK (risk_level IN ('LOW', 'MEDIUM', 'HIGH')),
    CONSTRAINT ck_prediction_grade       CHECK (predicted_grade IS NULL OR predicted_grade BETWEEN 2 AND 5)
);
-- Таблица 6.3: быстрый поиск последнего прогноза по паре «студент — дисциплина»
CREATE INDEX ix_prediction_last
    ON analytics.prediction (student_id, subject_id, created_at DESC);
CREATE INDEX ix_prediction_model ON analytics.prediction (model_version_id);

CREATE TABLE analytics.risk_case (
    risk_case_id   BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    prediction_id  BIGINT       NOT NULL REFERENCES analytics.prediction (prediction_id),
    staff_id       INTEGER      NOT NULL REFERENCES academic.staff (staff_id),
    status         VARCHAR(20)  NOT NULL DEFAULT 'NEW',
    measure        VARCHAR(255) NULL,
    comment        TEXT         NULL,
    created_at     TIMESTAMPTZ  NOT NULL DEFAULT now(),
    closed_at      TIMESTAMPTZ  NULL,
    CONSTRAINT uq_risk_case_prediction UNIQUE (prediction_id),   -- связь PREDICTION → RISK_CASE 1:0..1
    CONSTRAINT ck_risk_case_status CHECK (status IN
        ('NEW', 'IN_PROGRESS', 'RESOLVED', 'FALSE_POSITIVE', 'ESCALATED')),
    -- FR-15, FR-17: передача в деканат и ложное срабатывание — только с комментарием
    CONSTRAINT ck_risk_case_comment_required CHECK (
        status NOT IN ('ESCALATED', 'FALSE_POSITIVE') OR length(btrim(coalesce(comment, ''))) > 0),
    CONSTRAINT ck_risk_case_closed CHECK (closed_at IS NULL OR closed_at >= created_at)
);
CREATE INDEX ix_risk_case_staff_status ON analytics.risk_case (staff_id, status);
