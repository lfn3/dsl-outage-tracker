CREATE VIRTUAL TABLE outage_texts USING fts4 (
    provider_ref_id,
    equipment_list,
    full_text
);

CREATE TABLE IF NOT EXISTS outages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    provider TEXT NOT NULL,

    num_affected INTEGER,
    num_iconz_affected INTEGER,

    start_time TIMESTAMP NOT NULL,
    end_time TIMESTAMP,

    checked BOOLEAN NOT NULL DEFAULT 0,
    flagged BOOLEAN NOT NULL DEFAULT 0,
    handmade BOOLEAN NOT NULL DEFAULT 0,
    issues BOOLEAN NOT NULL DEFAULT 0,
    hidden BOOLEAN NOT NULL DEFAULT 0,
    
    text_id INTEGER NOT NULL,
    FOREIGN KEY(text_id) REFERENCES outage_texts(rowid)
);

CREATE TABLE IF NOT EXISTS dslams (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS dslusers (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    asid INTEGER UNIQUE NOT NULL,
    account_name TEXT,
    phone_number TEXT,
    user_name TEXT,

    dslam_id INTEGER NOT NULL,
    FOREIGN KEY(dslam_id) REFERENCES dslams(id)
);

CREATE TABLE IF NOT EXISTS outages_dslusers_rel (
    outages_id INTEGER NOT NULL,
    dslusers_id INTEGER NOT NULL,

    FOREIGN KEY(outages_id) references outages(id),
    FOREIGN KEY(dslusers_id) references dslusers(id)
);
