CREATE TABLE IF NOT EXISTS relations (
    id SERIAL PRIMARY KEY,
    name TEXT,
    age INTEGER,
    sex TEXT,
    occupation TEXT
);

CREATE TABLE IF NOT EXISTS patients (
    id SERIAL PRIMARY KEY,
    name TEXT,
    age INTEGER,
    sex TEXT,
    occupation TEXT,
    date_of_admission DATE,
    next_of_kin_id INTEGER
);

CREATE TABLE  IF NOT EXISTS examinations (
    id SERIAL PRIMARY KEY,
    date DATE,
    patient_id INTEGER,
    summary TEXT,
    details TEXT
);
CREATE TABLE IF NOT EXISTS api_tokens (
    app_id SERIAL PRIMARY KEY,
    user_id BIGINT NOT NULL,
    app_name TEXT,
    secret BYTEA
);
