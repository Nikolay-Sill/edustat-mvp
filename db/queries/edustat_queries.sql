-- =====================================================================
-- EduStat — проверочные SQL-запросы (раздел 6.3 проектной документации)
-- Тестовая среда: одна база, схемы academic / integration / analytics.
-- Запуск в psql, параметры задаются переменными:
--   psql -d edustat -v staff_id=1 -v group_id=1 -f edustat_queries.sql
-- =====================================================================

-- Запрос 1. Студенты группы риска по дисциплинам преподавателя
-- (берётся только последний прогноз). FR-12, FR-24, US-01.
WITH last_prediction AS (
    SELECT DISTINCT ON (p.student_id, p.subject_id)
           p.student_id, p.subject_id, p.risk_probability, p.risk_level, p.created_at
    FROM analytics.prediction p
    ORDER BY p.student_id, p.subject_id, p.created_at DESC
)
SELECT s.full_name, g.group_name, sb.subject_name,
       lp.risk_probability, lp.created_at::date AS calculated_on
FROM last_prediction lp
JOIN academic.student       s  ON s.student_id  = lp.student_id
JOIN academic.study_group   g  ON g.group_id    = s.group_id
JOIN academic.subject       sb ON sb.subject_id = lp.subject_id
JOIN academic.staff_subject ss ON ss.subject_id = lp.subject_id
                              AND ss.group_id   = s.group_id
WHERE ss.staff_id = :staff_id
  AND lp.risk_level = 'HIGH'
ORDER BY lp.risk_probability DESC;

-- Запрос 2. Активность в LMS за 30 дней в разрезе уровней риска по группе.
-- FR-06, FR-18.
SELECT lp.risk_level,
       COUNT(DISTINCT lp.student_id) AS students,
       ROUND(AVG(a.actions), 1)      AS avg_actions,
       ROUND(AVG(a.hours), 1)        AS avg_hours_in_lms
FROM (
    SELECT DISTINCT ON (student_id, subject_id) student_id, subject_id, risk_level
    FROM analytics.prediction
    ORDER BY student_id, subject_id, created_at DESC
) lp
JOIN academic.student s ON s.student_id = lp.student_id
JOIN (
    SELECT student_id, subject_id,
           COUNT(*) AS actions, SUM(duration_sec) / 3600.0 AS hours
    FROM integration.activity
    WHERE occurred_at >= now() - INTERVAL '30 days'
    GROUP BY student_id, subject_id
) a ON a.student_id = lp.student_id AND a.subject_id = lp.subject_id
WHERE s.group_id = :group_id
GROUP BY lp.risk_level
ORDER BY CASE lp.risk_level WHEN 'HIGH' THEN 1 WHEN 'MEDIUM' THEN 2 ELSE 3 END;
