-- 受控SQL版本源：不得由应用启动自动执行。
CREATE TABLE agent_security_policy_version (
    policy_version VARCHAR(128) NOT NULL,
    schema_version VARCHAR(32) NOT NULL,
    policy_payload JSON NOT NULL,
    policy_digest CHAR(64) NOT NULL,
    change_class VARCHAR(16) NOT NULL,
    approval_ref VARCHAR(128) NULL,
    created_by_ref_digest CHAR(64) NOT NULL,
    created_at DATETIME(6) NOT NULL,
    PRIMARY KEY (policy_version),
    UNIQUE KEY uk_agent_security_policy_digest (policy_digest),
    UNIQUE KEY uk_agent_security_policy_version_digest (policy_version, policy_digest),
    CONSTRAINT ck_agent_security_policy_change_class
        CHECK (change_class IN ('TIGHTENING', 'EXPANSION', 'MIXED', 'INITIAL'))
) ENGINE=InnoDB;

CREATE TABLE agent_security_policy_active (
    scope VARCHAR(16) NOT NULL,
    policy_version VARCHAR(128) NOT NULL,
    policy_digest CHAR(64) NOT NULL,
    policy_epoch BIGINT NOT NULL,
    state_version BIGINT NOT NULL,
    activated_at DATETIME(6) NOT NULL,
    activated_by_ref_digest CHAR(64) NOT NULL,
    PRIMARY KEY (scope),
    CONSTRAINT ck_agent_security_policy_active_scope CHECK (scope = 'GLOBAL'),
    CONSTRAINT ck_agent_security_policy_epoch CHECK (policy_epoch >= 1),
    CONSTRAINT ck_agent_security_policy_state_version CHECK (state_version >= 1),
    CONSTRAINT fk_agent_security_policy_active_version_digest
        FOREIGN KEY (policy_version, policy_digest)
        REFERENCES agent_security_policy_version (policy_version, policy_digest)
        ON DELETE RESTRICT
) ENGINE=InnoDB;

CREATE TABLE agent_security_policy_activation_audit (
    activation_id VARCHAR(128) NOT NULL,
    scope VARCHAR(16) NOT NULL,
    from_policy_version VARCHAR(128) NULL,
    to_policy_version VARCHAR(128) NOT NULL,
    to_policy_digest CHAR(64) NOT NULL,
    new_policy_epoch BIGINT NOT NULL,
    change_class VARCHAR(16) NOT NULL,
    approval_ref VARCHAR(128) NOT NULL,
    approval_evidence_digest CHAR(64) NOT NULL,
    actor_type VARCHAR(32) NOT NULL,
    actor_ref_digest CHAR(64) NOT NULL,
    correlation_id VARCHAR(128) NOT NULL,
    occurred_at DATETIME(6) NOT NULL,
    PRIMARY KEY (activation_id),
    UNIQUE KEY uk_agent_security_policy_activation_epoch (scope, new_policy_epoch),
    CONSTRAINT ck_agent_security_policy_activation_scope CHECK (scope = 'GLOBAL'),
    CONSTRAINT ck_agent_security_policy_activation_epoch CHECK (new_policy_epoch >= 1),
    CONSTRAINT ck_agent_security_policy_activation_change_class
        CHECK (change_class IN ('TIGHTENING', 'EXPANSION', 'MIXED', 'INITIAL')),
    CONSTRAINT fk_agent_security_policy_activation_version_digest
        FOREIGN KEY (to_policy_version, to_policy_digest)
        REFERENCES agent_security_policy_version (policy_version, policy_digest)
        ON DELETE RESTRICT
) ENGINE=InnoDB;
