package com.dylan.baseline.agent.security.migration.control;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;
import static org.mockito.ArgumentMatchers.anyString;
import static org.mockito.ArgumentMatchers.eq;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.when;

import java.util.Map;
import org.junit.jupiter.api.Test;
import org.springframework.jdbc.core.JdbcTemplate;

class Open04001ControlledMigrationCliTest {

    private static final String PRIMARY = "a".repeat(64);
    private static final String DRILL = "b".repeat(64);

    @Test
    void acceptsOnlyEmptyAndThreeExactRecoverableCheckpoints() {
        assertThat(Open04001ControlledMigrationCli.determineStartStep(jdbc(0, 0, 0, null), PRIMARY, DRILL))
                .isZero();
        assertThat(Open04001ControlledMigrationCli.determineStartStep(
                jdbc(1, 1, 1, state(PRIMARY, 1, 1)), PRIMARY, DRILL)).isEqualTo(1);
        assertThat(Open04001ControlledMigrationCli.determineStartStep(
                jdbc(1, 2, 2, state(DRILL, 2, 2)), PRIMARY, DRILL)).isEqualTo(2);
        assertThat(Open04001ControlledMigrationCli.determineStartStep(
                jdbc(1, 2, 3, state(PRIMARY, 3, 3)), PRIMARY, DRILL)).isEqualTo(3);
    }

    @Test
    void rejectsUnknownOrTamperedDatabaseState() {
        assertThatThrownBy(() -> Open04001ControlledMigrationCli.determineStartStep(
                jdbc(1, 2, 2, state(PRIMARY, 2, 2)), PRIMARY, DRILL))
                .isInstanceOf(IllegalStateException.class)
                .hasMessageContaining("exact recoverable");
        assertThatThrownBy(() -> Open04001ControlledMigrationCli.determineStartStep(
                jdbc(2, 2, 2, null), PRIMARY, DRILL))
                .isInstanceOf(IllegalStateException.class)
                .hasMessageContaining("not a recoverable");
    }

    private static JdbcTemplate jdbc(int active, int versions, int audits, Map<String, Object> state) {
        JdbcTemplate jdbc = mock(JdbcTemplate.class);
        when(jdbc.queryForObject(anyString(), eq(Integer.class))).thenAnswer(invocation -> {
            String sql = invocation.getArgument(0);
            if (sql.contains("agent_security_policy_active")) {
                return active;
            }
            if (sql.contains("agent_security_policy_version")) {
                return versions;
            }
            if (sql.contains("agent_security_policy_activation_audit")) {
                return audits;
            }
            throw new AssertionError("unexpected count SQL: " + sql);
        });
        if (state != null) {
            when(jdbc.queryForMap(anyString())).thenReturn(state);
        }
        return jdbc;
    }

    private static Map<String, Object> state(String digest, long epoch, long stateVersion) {
        return Map.of("policyDigest", digest, "policyEpoch", epoch, "stateVersion", stateVersion);
    }
}
