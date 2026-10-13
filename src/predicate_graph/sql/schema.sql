CREATE TABLE IF NOT EXISTS nodes_raw (
    k_number TEXT PRIMARY KEY,
    device_name TEXT,
    applicant TEXT,
    decision_date TEXT,
    date_received TEXT,
    decision_code TEXT,
    decision_description TEXT,
    product_code TEXT,
    statement_or_summary TEXT,
    clearance_type TEXT,
    third_party_flag TEXT,
    expedited_review_flag TEXT,
    advisory_committee TEXT,
    advisory_committee_description TEXT,
    regulation_number TEXT,
    device_class TEXT,
    medical_specialty TEXT,
    state TEXT,
    country_code TEXT
);

CREATE TABLE IF NOT EXISTS recalls (
    cfres_id TEXT,
    k_number TEXT,
    product_res_number TEXT,
    res_event_number TEXT,
    event_date_initiated TEXT,
    event_date_posted TEXT,
    recall_status TEXT,
    recalling_firm TEXT,
    product_code TEXT,
    reason_for_recall TEXT,
    root_cause_description TEXT,
    PRIMARY KEY (cfres_id, k_number)
);

CREATE TABLE IF NOT EXISTS enforcement (
    recall_number TEXT PRIMARY KEY,
    event_id TEXT,
    classification TEXT,
    status TEXT,
    recall_initiation_date TEXT,
    center_classification_date TEXT,
    report_date TEXT,
    recalling_firm TEXT
);

CREATE TABLE IF NOT EXISTS registrations (
    k_number TEXT,
    registration_number TEXT,
    status_code TEXT,
    reg_expiry_date_year TEXT,
    establishment_name TEXT,
    iso_country_code TEXT,
    PRIMARY KEY (k_number, registration_number)
);

CREATE TABLE IF NOT EXISTS meta (
    key TEXT PRIMARY KEY,
    value TEXT
);

CREATE TABLE IF NOT EXISTS edges (
    citing TEXT,
    predicate TEXT,
    valid INTEGER,
    citing_date TEXT,
    predicate_date TEXT,
    page INTEGER,
    quote TEXT,
    PRIMARY KEY (citing, predicate)
);

CREATE TABLE IF NOT EXISTS edges_name_only (
    citing TEXT,
    predicate TEXT,
    score REAL,
    citing_date TEXT,
    predicate_date TEXT,
    page INTEGER,
    quote TEXT,
    PRIMARY KEY (citing, predicate)
);

CREATE INDEX IF NOT EXISTS idx_recalls_k ON recalls(k_number);
CREATE INDEX IF NOT EXISTS idx_recalls_res ON recalls(product_res_number);
CREATE INDEX IF NOT EXISTS idx_reg_k ON registrations(k_number);

CREATE INDEX IF NOT EXISTS idx_edges_predicate ON edges(predicate);
CREATE INDEX IF NOT EXISTS idx_edges_name_only_predicate ON edges_name_only(predicate);