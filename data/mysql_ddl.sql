-- =====================================================================
-- VIGIL — MySQL DDL
-- 8 tables: rm, customer, product, transaction, compliance_case,
-- case_activity_log, reviewer, app_settings
-- =====================================================================

-- ---------------------------------------------------------------------
-- 1. rm — the RM roster
-- ---------------------------------------------------------------------
CREATE TABLE rm (
    rm_id       VARCHAR(20) PRIMARY KEY,
    full_name   VARCHAR(100) NOT NULL,
    branch      VARCHAR(100),
    joined_date DATE,
    active      BOOLEAN DEFAULT TRUE
);

-- ---------------------------------------------------------------------
-- 2. customer — risk_profile + investment_experience drive suitability
--    detection directly
-- ---------------------------------------------------------------------
CREATE TABLE customer (
    customer_id            VARCHAR(20) PRIMARY KEY,
    full_name              VARCHAR(100),
    mobile_number          VARCHAR(20),
    risk_profile           VARCHAR(30),   -- Conservative, Moderate, Aggressive
    investment_experience  VARCHAR(20),   -- Low, Medium, High
    kyc_status             VARCHAR(20)
);

-- ---------------------------------------------------------------------
-- 3. product — risk_class + suitable_risk_profiles is the other half
--    of suitability detection
-- ---------------------------------------------------------------------
CREATE TABLE product (
    product_id               VARCHAR(20) PRIMARY KEY,
    product_name             VARCHAR(150),
    risk_class                VARCHAR(30),   -- Low, Medium, High
    suitable_risk_profiles    VARCHAR(100),  -- comma-separated, e.g. "Conservative,Moderate"
    disclosure_requirements   TEXT
);

-- ---------------------------------------------------------------------
-- 4. transaction — links customer + rm + product; feeds get_transactions
--    and RM history context for the Investigator Agent
-- ---------------------------------------------------------------------
CREATE TABLE transaction (
    transaction_id    VARCHAR(20) PRIMARY KEY,
    customer_id       VARCHAR(20) REFERENCES customer(customer_id),
    rm_id             VARCHAR(20) REFERENCES rm(rm_id),
    product_id        VARCHAR(20) REFERENCES product(product_id),
    amount            DECIMAL(15,2),
    transaction_type  VARCHAR(30),   -- PURCHASE, REDEMPTION, SIP
    transaction_time  TIMESTAMP
);

-- ---------------------------------------------------------------------
-- 5. reviewer — compliance staff who review cases (NOT RMs — RMs are
--    monitored, reviewers do the reviewing)
-- ---------------------------------------------------------------------
CREATE TABLE reviewer (
    reviewer_id  VARCHAR(20) PRIMARY KEY,
    full_name    VARCHAR(100) NOT NULL,
    role         VARCHAR(50),    -- e.g. Compliance Officer, Compliance Head
    active       BOOLEAN DEFAULT TRUE
);

-- ---------------------------------------------------------------------
-- 6. compliance_case — the authoritative case workflow table.
--    status stays binary (OPEN/RESOLVED) on purpose — "escalated" is a
--    flag, not a third status value, so the workflow doesn't quietly grow
--    a three-state enum nothing else in the system expects.
-- ---------------------------------------------------------------------
CREATE TABLE compliance_case (
    case_id           VARCHAR(64) PRIMARY KEY,
    finding_id        VARCHAR(64) NOT NULL,   -- references the finding in the
                                               -- compliance_findings ES index
    call_id           VARCHAR(64) NOT NULL,   -- references the call in the
                                               -- calls ES index
    rm_id             VARCHAR(20) REFERENCES rm(rm_id),
    customer_id       VARCHAR(20) REFERENCES customer(customer_id),
    category          VARCHAR(50),
    severity          VARCHAR(10),            -- LOW, MEDIUM, HIGH
    status            VARCHAR(20) DEFAULT 'OPEN',  -- OPEN or RESOLVED only
    escalated         BOOLEAN DEFAULT FALSE,
    assigned_to       VARCHAR(20) REFERENCES reviewer(reviewer_id),
    created_at        TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at        TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    resolution_notes  TEXT,
    resolution_type   VARCHAR(30) NULL  -- CONFIRMED_ACTION_TAKEN | DISMISSED_FALSE_POSITIVE | ESCALATED_RESOLVED
);

-- ---------------------------------------------------------------------
-- 7. case_activity_log — full audit trail of case actions. Without this,
--    "auditable Evidence Chain" only covers the AI's detection, not the
--    human case-handling on top of it.
-- ---------------------------------------------------------------------
CREATE TABLE case_activity_log (
    log_id      INT AUTO_INCREMENT PRIMARY KEY,
    case_id     VARCHAR(64) REFERENCES compliance_case(case_id),
    action      VARCHAR(50),   -- STATUS_CHANGE, NOTE_ADDED, ASSIGNED, ESCALATED
    actor       VARCHAR(20) REFERENCES reviewer(reviewer_id),
    details     TEXT,
    timestamp   TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ---------------------------------------------------------------------
-- 8. app_settings — tiny key-value table so config like the confidence
--    threshold actually persists instead of resetting every restart
-- ---------------------------------------------------------------------
CREATE TABLE app_settings (
    setting_key    VARCHAR(50) PRIMARY KEY,
    setting_value  VARCHAR(255),
    updated_at     TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
);

-- ---------------------------------------------------------------------
-- 9. users — authentication, roles, and institutional access control
-- ---------------------------------------------------------------------
CREATE TABLE users (
    user_id        VARCHAR(64) PRIMARY KEY,
    username       VARCHAR(50) NOT NULL UNIQUE,
    email          VARCHAR(100) NOT NULL UNIQUE,
    password_hash  VARCHAR(255) NOT NULL,
    role           VARCHAR(50) NOT NULL DEFAULT 'Audit Officer',
    team           VARCHAR(50) NOT NULL DEFAULT 'Compliance',
    access_level   VARCHAR(50) NOT NULL DEFAULT 'All',
    full_name      VARCHAR(100) NOT NULL DEFAULT 'Audit Officer',
    is_active      BOOLEAN DEFAULT TRUE,
    last_login_at  TIMESTAMP NULL,
    created_at     TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at     TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
);

