DROP TABLE IF EXISTS node_recalls;
CREATE TABLE node_recalls AS
SELECT
    r.k_number,
    MIN(CASE e.classification
        WHEN 'Class I'   THEN 1
        WHEN 'Class II'  THEN 2
        WHEN 'Class III' THEN 3
        ELSE 9 END) AS severity_rank,
    MIN(r.event_date_initiated) AS recall_date,
    COUNT(*) AS recall_count
FROM recalls r
LEFT JOIN enforcement e ON e.recall_number = r.product_res_number
GROUP BY r.k_number;

DROP TABLE IF EXISTS node_marketing;
CREATE TABLE node_marketing AS
SELECT
    k_number,
    MAX(CASE WHEN status_code = '1' THEN 1 ELSE 0 END) AS actively_marketed,
    COUNT(*) AS registration_count
FROM registrations
GROUP BY k_number;

DROP TABLE IF EXISTS nodes;
CREATE TABLE nodes AS
SELECT
    n.*,
    CASE WHEN nr.k_number IS NOT NULL THEN 1 ELSE 0 END AS recalled,
    CASE nr.severity_rank
        WHEN 1 THEN 'Class I'
        WHEN 2 THEN 'Class II'
        WHEN 3 THEN 'Class III'
        END AS recall_class,
    nr.recall_date,
    COALESCE(nr.recall_count, 0) AS recall_count,
    nm.actively_marketed
FROM nodes_raw n
LEFT JOIN node_recalls   nr ON nr.k_number = n.k_number
LEFT JOIN node_marketing nm ON nm.k_number = n.k_number;

CREATE UNIQUE INDEX idx_nodes_k ON nodes(k_number);
CREATE INDEX idx_nodes_product ON nodes(product_code);
CREATE INDEX idx_nodes_decision ON nodes(decision_date);