package com.dylan.baseline.agent.security.policy;

import static org.assertj.core.api.Assertions.assertThat;

import java.io.IOException;
import java.nio.charset.StandardCharsets;
import org.junit.jupiter.api.Test;

class AgentSecurityPolicyPersistenceContractTest {

    @Test
    void controlledSqlContainsRequiredPolicyInvariants() throws IOException {
        try (var input = getClass().getClassLoader().getResourceAsStream(
                "db/manual/agent-security/V0_1__agent_security_policy.sql")) {
            assertThat(input).isNotNull();
            String sql = new String(input.readAllBytes(), StandardCharsets.UTF_8);
            assertThat(sql)
                    .contains("CREATE TABLE agent_security_policy_version")
                    .contains("CREATE TABLE agent_security_policy_active")
                    .contains("CREATE TABLE agent_security_policy_activation_audit")
                    .contains("CHECK (scope = 'GLOBAL')")
                    .contains("FOREIGN KEY (policy_version, policy_digest)")
                    .contains("FOREIGN KEY (to_policy_version, to_policy_digest)")
                    .contains("UNIQUE KEY uk_agent_security_policy_activation_epoch")
                    .contains("ON DELETE RESTRICT")
                    .doesNotContain("DROP TABLE", "TRUNCATE TABLE");
        }
    }

    @Test
    void deployedSchemaAlignmentIsIdempotentAndKeepsDigestBoundForeignKeys() throws IOException {
        try (var input = getClass().getClassLoader().getResourceAsStream(
                "db/manual/agent-security/V0_2__align_policy_digest_foreign_keys.sql")) {
            assertThat(input).isNotNull();
            String sql = new String(input.readAllBytes(), StandardCharsets.UTF_8);
            assertThat(sql)
                    .contains("INFORMATION_SCHEMA.REFERENTIAL_CONSTRAINTS")
                    .contains("uk_agent_security_policy_version_digest")
                    .contains("fk_agent_security_policy_active_version_digest")
                    .contains("fk_agent_security_policy_activation_version_digest")
                    .contains("FOREIGN KEY (policy_version, policy_digest)")
                    .contains("FOREIGN KEY (to_policy_version, to_policy_digest)")
                    .contains("ON DELETE RESTRICT")
                    .doesNotContain("DROP TABLE", "TRUNCATE TABLE", "DELETE FROM");
        }
    }
}
