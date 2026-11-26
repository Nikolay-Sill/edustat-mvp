-- =====================================================================
-- EduStat MVP — дополнения к модели данных
-- Эти таблицы нужны для реализации FR, но отсутствуют на Рисунке 6.1:
-- в целевой архитектуре они принадлежат Notification / Reporting Service
-- и Keycloak. В MVP (модульный монолит) они живут в той же базе.
-- Каждое дополнение — кандидат в «журнал отклонений от спецификации».
-- =====================================================================

-- FR-09: три главных фактора прогноза.
-- В API (схема Prediction.top_factors) факторы есть, в ER-модели — нет.
CREATE TABLE analytics.prediction_factor (
    prediction_id  BIGINT      NOT NULL REFERENCES analytics.prediction (prediction_id),
    rank           SMALLINT    NOT NULL,
    factor         VARCHAR(50) NOT NULL,          -- например, activity_drop_14d
    value          NUMERIC(8,3) NOT NULL,
    unit           VARCHAR(10) NULL,
    PRIMARY KEY (prediction_id, rank),
    CONSTRAINT ck_prediction_factor_rank CHECK (rank BETWEEN 1 AND 3),
    CONSTRAINT ck_prediction_factor_unit CHECK (unit IS NULL OR unit IN ('ratio', 'count', 'percent', 'hours'))
);

-- FR-13: уведомления в личном кабинете (в MVP без e-mail).
CREATE SCHEMA IF NOT EXISTS notification;
CREATE TABLE notification.notification (
    notification_id  BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    staff_id         INTEGER      NOT NULL REFERENCES academic.staff (staff_id),
    type             VARCHAR(30)  NOT NULL,
    title            VARCHAR(200) NOT NULL,
    body             TEXT         NULL,
    link             VARCHAR(255) NULL,
    is_read          BOOLEAN      NOT NULL DEFAULT false,
    created_at       TIMESTAMPTZ  NOT NULL DEFAULT now(),
    CONSTRAINT ck_notification_type CHECK (type IN
        ('RISK_DETECTED', 'RISK_CASE_OVERDUE', 'RISK_ESCALATED', 'REPORT_READY', 'SYNC_FAILED'))
);
CREATE INDEX ix_notification_staff_unread ON notification.notification (staff_id, is_read, created_at DESC);

-- FR-21: фоновые отчёты (в MVP только XLSX, файл хранится на диске).
CREATE SCHEMA IF NOT EXISTS reporting;
CREATE TABLE reporting.report (
    report_id    UUID         PRIMARY KEY DEFAULT gen_random_uuid(),
    staff_id     INTEGER      NOT NULL REFERENCES academic.staff (staff_id),
    report_type  VARCHAR(30)  NOT NULL,
    format       VARCHAR(10)  NOT NULL DEFAULT 'XLSX',
    filters      JSONB        NULL,
    status       VARCHAR(20)  NOT NULL DEFAULT 'QUEUED',
    file_path    VARCHAR(255) NULL,
    created_at   TIMESTAMPTZ  NOT NULL DEFAULT now(),
    ready_at     TIMESTAMPTZ  NULL,
    expires_at   TIMESTAMPTZ  NOT NULL DEFAULT now() + INTERVAL '7 days',   -- US-03: файл доступен 7 дней
    CONSTRAINT ck_report_type   CHECK (report_type IN ('RISK_SUMMARY', 'GROUP_PERFORMANCE', 'FACULTY_OVERVIEW')),
    CONSTRAINT ck_report_format CHECK (format IN ('PDF', 'XLSX')),
    CONSTRAINT ck_report_status CHECK (status IN ('QUEUED', 'IN_PROGRESS', 'READY', 'FAILED'))
);

-- FR-23/FR-24 (упрощение): вход по логину и паролю вместо SSO/Keycloak.
-- Роль берётся из academic.staff.role; keycloak_user_id в MVP заполняется gen_random_uuid().
CREATE SCHEMA IF NOT EXISTS auth;
CREATE TABLE auth.app_user (
    user_id        INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    staff_id       INTEGER      NOT NULL UNIQUE REFERENCES academic.staff (staff_id),
    login          VARCHAR(50)  NOT NULL UNIQUE,
    password_hash  VARCHAR(255) NOT NULL,
    is_active      BOOLEAN      NOT NULL DEFAULT true
);
