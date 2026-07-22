-- 仅用于已部署的旧版表：把仅 policy_version 外键升级为 version+digest 复合外键。
-- 使用 INFORMATION_SCHEMA 生成幂等 DDL；新装环境直接执行 V0_1，无需执行本文件。

SET @schema_name = DATABASE();

SET @ddl = (
    SELECT IF(COUNT(*) = 0,
        'ALTER TABLE agent_security_policy_version ADD UNIQUE KEY uk_agent_security_policy_version_digest (policy_version, policy_digest)',
        'SELECT 1')
      FROM INFORMATION_SCHEMA.STATISTICS
     WHERE BINARY TABLE_SCHEMA = BINARY @schema_name
       AND BINARY TABLE_NAME = BINARY 'agent_security_policy_version'
       AND BINARY INDEX_NAME = BINARY 'uk_agent_security_policy_version_digest'
);
PREPARE statement FROM @ddl;
EXECUTE statement;
DEALLOCATE PREPARE statement;

SET @ddl = (
    SELECT IF(COUNT(*) > 0,
        'ALTER TABLE agent_security_policy_active DROP FOREIGN KEY fk_agent_security_policy_active_version',
        'SELECT 1')
      FROM INFORMATION_SCHEMA.REFERENTIAL_CONSTRAINTS
     WHERE BINARY CONSTRAINT_SCHEMA = BINARY @schema_name
       AND BINARY TABLE_NAME = BINARY 'agent_security_policy_active'
       AND BINARY CONSTRAINT_NAME = BINARY 'fk_agent_security_policy_active_version'
);
PREPARE statement FROM @ddl;
EXECUTE statement;
DEALLOCATE PREPARE statement;

SET @ddl = (
    SELECT IF(COUNT(*) = 0,
        'ALTER TABLE agent_security_policy_active ADD CONSTRAINT fk_agent_security_policy_active_version_digest FOREIGN KEY (policy_version, policy_digest) REFERENCES agent_security_policy_version (policy_version, policy_digest) ON DELETE RESTRICT',
        'SELECT 1')
      FROM INFORMATION_SCHEMA.REFERENTIAL_CONSTRAINTS
     WHERE BINARY CONSTRAINT_SCHEMA = BINARY @schema_name
       AND BINARY TABLE_NAME = BINARY 'agent_security_policy_active'
       AND BINARY CONSTRAINT_NAME = BINARY 'fk_agent_security_policy_active_version_digest'
);
PREPARE statement FROM @ddl;
EXECUTE statement;
DEALLOCATE PREPARE statement;

SET @ddl = (
    SELECT IF(COUNT(*) > 0,
        'ALTER TABLE agent_security_policy_activation_audit DROP FOREIGN KEY fk_agent_security_policy_activation_version',
        'SELECT 1')
      FROM INFORMATION_SCHEMA.REFERENTIAL_CONSTRAINTS
     WHERE BINARY CONSTRAINT_SCHEMA = BINARY @schema_name
       AND BINARY TABLE_NAME = BINARY 'agent_security_policy_activation_audit'
       AND BINARY CONSTRAINT_NAME = BINARY 'fk_agent_security_policy_activation_version'
);
PREPARE statement FROM @ddl;
EXECUTE statement;
DEALLOCATE PREPARE statement;

SET @ddl = (
    SELECT IF(COUNT(*) = 0,
        'ALTER TABLE agent_security_policy_activation_audit ADD CONSTRAINT fk_agent_security_policy_activation_version_digest FOREIGN KEY (to_policy_version, to_policy_digest) REFERENCES agent_security_policy_version (policy_version, policy_digest) ON DELETE RESTRICT',
        'SELECT 1')
      FROM INFORMATION_SCHEMA.REFERENTIAL_CONSTRAINTS
     WHERE BINARY CONSTRAINT_SCHEMA = BINARY @schema_name
       AND BINARY TABLE_NAME = BINARY 'agent_security_policy_activation_audit'
       AND BINARY CONSTRAINT_NAME = BINARY 'fk_agent_security_policy_activation_version_digest'
);
PREPARE statement FROM @ddl;
EXECUTE statement;
DEALLOCATE PREPARE statement;
