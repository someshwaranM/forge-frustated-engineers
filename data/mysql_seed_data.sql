-- =====================================================================
-- VIGIL — MySQL Seed Data
-- All names/numbers are synthetic — no real people, no real customers.
--
-- IMPORTANT: RM001-RM005 and CUST001-CUST005 are a reserved ID range.
-- Before Phase 5 (ingestion), check the actual filenames of your prepared
-- call recordings (RM<id>_CUST<id>_<datetime>.wav) and confirm every
-- RM_ID/Customer_ID referenced there exists here. If a real filename uses
-- an ID outside this range, ADD that row rather than renumbering existing
-- rows — Detection/Case data will key off whatever IDs actually ingest.
-- =====================================================================

-- ---------------------------------------------------------------------
-- rm — 5 RMs across a couple of branches
-- ---------------------------------------------------------------------
INSERT INTO rm (rm_id, full_name, branch, joined_date, active) VALUES
('RM001', 'Arjun Mehta',      'Mumbai - Andheri',   '2021-03-15', TRUE),
('RM002', 'Priya Nair',       'Bengaluru - Whitefield', '2019-07-01', TRUE),
('RM003', 'Vikram Sinha',     'Delhi - Connaught Place', '2022-01-10', TRUE),
('RM004', 'Sneha Kulkarni',   'Pune - Kothrud',     '2020-11-20', TRUE),
('RM005', 'Rahul Desai',      'Mumbai - Andheri',   '2023-06-05', TRUE);

-- ---------------------------------------------------------------------
-- customer — 5 customers, deliberately spanning all risk_profile and
-- investment_experience combinations so suitability-mismatch scenarios
-- are actually possible to trigger
-- ---------------------------------------------------------------------
INSERT INTO customer (customer_id, full_name, mobile_number, risk_profile, investment_experience, kyc_status) VALUES
('CUST001', 'Meena Iyer',      '9800010001', 'Conservative', 'Low',    'VERIFIED'),
('CUST002', 'Rohan Kapoor',    '9800010002', 'Moderate',     'Medium', 'VERIFIED'),
('CUST003', 'Anjali Rao',      '9800010003', 'Aggressive',   'High',   'VERIFIED'),
('CUST004', 'Suresh Pillai',   '9800010004', 'Conservative', 'Medium', 'VERIFIED'),
('CUST005', 'Kavita Bhatt',    '9800010005', 'Moderate',     'Low',    'PENDING');

-- ---------------------------------------------------------------------
-- product — 7 products, spanning Low/Medium/High risk_class. At least
-- 2 High-risk products deliberately exclude "Conservative" from
-- suitable_risk_profiles, so a mismatch actually exists to detect.
-- ---------------------------------------------------------------------
INSERT INTO product (product_id, product_name, risk_class, suitable_risk_profiles, disclosure_requirements) VALUES
('PROD001', 'Vigil Liquid Fund',                 'Low',    'Conservative,Moderate,Aggressive', 'Standard scheme document + risk-o-meter disclosure required.'),
('PROD002', 'Vigil Short Duration Debt Fund',    'Low',    'Conservative,Moderate,Aggressive', 'Standard scheme document + risk-o-meter disclosure required.'),
('PROD003', 'Vigil Balanced Hybrid Fund',        'Medium', 'Moderate,Aggressive',              'Risk-o-meter + hybrid-allocation disclosure required.'),
('PROD004', 'Vigil Large Cap Equity Fund',       'Medium', 'Moderate,Aggressive',              'Risk-o-meter + market-risk disclosure required.'),
('PROD005', 'Vigil Small Cap Equity Fund',       'High',   'Aggressive',                       'Risk-o-meter + high-volatility disclosure + no-guaranteed-return disclosure mandatory.'),
('PROD006', 'Vigil Sectoral Thematic Fund',      'High',   'Aggressive',                       'Risk-o-meter + concentration-risk disclosure + no-guaranteed-return disclosure mandatory.'),
('PROD007', 'Vigil Multi Asset Allocation Fund', 'Medium', 'Moderate,Aggressive',              'Risk-o-meter + multi-asset-allocation disclosure required.');

-- ---------------------------------------------------------------------
-- transaction — spread across the last several months, linking
-- customers to products via RMs. Includes at least one deliberately
-- mismatched transaction (CUST001, Conservative, into PROD005, High-risk)
-- for the suitability-mismatch demo scenario.
-- ---------------------------------------------------------------------
INSERT INTO transaction (transaction_id, customer_id, rm_id, product_id, amount, transaction_type, transaction_time) VALUES
('TXN0001', 'CUST001', 'RM001', 'PROD001', 50000.00,  'PURCHASE',  '2026-02-10 10:15:00'),
('TXN0002', 'CUST001', 'RM001', 'PROD005', 150000.00, 'PURCHASE',  '2026-05-22 11:40:00'),  -- mismatch: Conservative -> High risk
('TXN0003', 'CUST002', 'RM002', 'PROD003', 75000.00,  'PURCHASE',  '2026-03-05 14:20:00'),
('TXN0004', 'CUST002', 'RM002', 'PROD004', 60000.00,  'SIP',       '2026-04-01 09:00:00'),
('TXN0005', 'CUST003', 'RM003', 'PROD006', 200000.00, 'PURCHASE',  '2026-01-18 16:05:00'),
('TXN0006', 'CUST003', 'RM003', 'PROD005', 100000.00, 'PURCHASE',  '2026-06-30 13:30:00'),
('TXN0007', 'CUST004', 'RM004', 'PROD002', 40000.00,  'PURCHASE',  '2026-02-28 10:50:00'),
('TXN0008', 'CUST004', 'RM001', 'PROD007', 90000.00,  'SIP',       '2026-07-12 09:15:00'),
('TXN0009', 'CUST005', 'RM005', 'PROD001', 30000.00,  'PURCHASE',  '2026-03-19 12:00:00'),
('TXN0010', 'CUST005', 'RM002', 'PROD003', 55000.00,  'REDEMPTION','2026-08-02 15:45:00');

-- ---------------------------------------------------------------------
-- reviewer — compliance staff who review/action cases (distinct from RMs)
-- ---------------------------------------------------------------------
INSERT INTO reviewer (reviewer_id, full_name, role, active) VALUES
('REV001', 'Kiran Shetty',    'Compliance Officer', TRUE),
('REV002', 'Neha Agarwal',    'Compliance Officer', TRUE),
('REV003', 'Manoj Varma',     'Compliance Head',    TRUE);

-- ---------------------------------------------------------------------
-- app_settings — one seeded default: the confidence threshold shown/
-- editable on the Settings page
-- ---------------------------------------------------------------------
INSERT INTO app_settings (setting_key, setting_value) VALUES
('confidence_threshold', '0.75'),
('active_ai_provider',   'bedrock');

-- ---------------------------------------------------------------------
-- compliance_case and case_activity_log are intentionally left EMPTY.
-- They get populated once the detection pipeline (Phase 6/7) and case
-- workflow (Phase 8) actually run against real or demo call data.
-- ---------------------------------------------------------------------
