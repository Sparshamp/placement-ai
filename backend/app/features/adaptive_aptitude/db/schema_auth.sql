-- Phase 3: authentication. Depends on `students` (db/schema.sql).

ALTER TABLE students ADD COLUMN IF NOT EXISTS email TEXT;
ALTER TABLE students ADD COLUMN IF NOT EXISTS password_hash TEXT;
CREATE UNIQUE INDEX IF NOT EXISTS idx_students_email
    ON students (email) WHERE email IS NOT NULL;

CREATE TABLE IF NOT EXISTS auth_refresh_tokens (
    token_id      UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    student_id    TEXT NOT NULL REFERENCES students(student_id) ON DELETE CASCADE,
    token_hash    TEXT NOT NULL,
    issued_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
    expires_at    TIMESTAMPTZ NOT NULL,
    revoked_at    TIMESTAMPTZ
);
CREATE INDEX IF NOT EXISTS idx_refresh_tokens_student ON auth_refresh_tokens (student_id);
CREATE INDEX IF NOT EXISTS idx_refresh_tokens_hash ON auth_refresh_tokens (token_hash);