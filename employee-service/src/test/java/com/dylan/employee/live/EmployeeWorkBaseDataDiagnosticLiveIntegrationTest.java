package com.dylan.employee.live;

import static org.assertj.core.api.Assertions.assertThat;

import java.nio.ByteBuffer;
import java.nio.channels.FileChannel;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.StandardOpenOption;
import java.security.MessageDigest;
import java.time.Instant;
import java.util.HexFormat;
import java.util.List;
import java.util.Map;

import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.condition.EnabledIfEnvironmentVariable;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.SpringBootConfiguration;
import org.springframework.boot.autoconfigure.EnableAutoConfiguration;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.transaction.annotation.Transactional;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.fasterxml.jackson.databind.node.ObjectNode;

@EnabledIfEnvironmentVariable(named = "RUN_EMPLOYEE_WORK_BASE_DATA_DIAG", matches = "1")
@SpringBootTest(
        classes = EmployeeWorkBaseDataDiagnosticLiveIntegrationTest.DiagnosticApplication.class,
        webEnvironment = SpringBootTest.WebEnvironment.NONE,
        properties = {
        "spring.cloud.config.enabled=false",
        "spring.config.import=",
        "spring.config.additional-location=optional:file:D:/codex/config-service/src/main/resources/config/",
        "spring.profiles.active=datasource,emp,ai-provider",
        "eureka.client.enabled=false",
        "spring.kafka.listener.auto-startup=false",
        "spring.main.web-application-type=none",
        "spring.autoconfigure.exclude=com.dylan.common.security.JwtConfig,"
                + "com.dylan.common.security.FeignTokenRelayAutoConfiguration,"
                + "com.dylan.common.security.ResourceServerSecurityAutoConfiguration,"
                + "com.dylan.common.security.ReactiveResourceServerSecurityAutoConfiguration,"
                + "com.dylan.common.security.UserRoleAuthorityAutoConfiguration"
        })
class EmployeeWorkBaseDataDiagnosticLiveIntegrationTest {
    private static final String RUN_ID =
            "employee-work-base-data-diagnostic-v1-20260814-run-01";
    private static final String SOURCE_EVIDENCE_PATH =
            "agent-runtime/tests/integration/adapters/employee/evidence/"
                    + "employee-work-base-static-diagnostic-v1-20260814-run-01.json";
    private static final String SOURCE_EVIDENCE_SHA256 =
            "7edad245f9041535a6cb579401102fc8a754980b4f6951c1192836c2d4271ed8";
    private static final String BIDI_HEX_PATTERN =
            "(E280AA|E280AB|E280AC|E280AD|E280AE|E281A6|E281A7|E281A8|E281A9)";

    private static final String METADATA_SQL = """
            SELECT
              DATA_TYPE AS dataType,
              COLUMN_TYPE AS columnType,
              IS_NULLABLE AS isNullable,
              CHARACTER_MAXIMUM_LENGTH AS characterMaximumLength,
              COLUMN_DEFAULT AS columnDefault,
              COLLATION_NAME AS collationName
            FROM information_schema.columns
            WHERE TABLE_SCHEMA = DATABASE()
              AND LOWER(TABLE_NAME) = LOWER('employee')
              AND UPPER(COLUMN_NAME) = 'WORK_BASE_SI'
            LIMIT 2
            """;

    private static final String AGGREGATE_SQL = """
            SELECT
              COUNT(*) AS totalRows,
              COALESCE(SUM(CASE
                WHEN WORK_BASE_SI IS NULL THEN 1 ELSE 0 END), 0) AS nullRows,
              COALESCE(SUM(CASE
                WHEN WORK_BASE_SI IS NOT NULL
                  AND CHAR_LENGTH(WORK_BASE_SI) NOT BETWEEN 1 AND 256
                THEN 1 ELSE 0 END), 0) AS lengthInvalidRows,
              COALESCE(SUM(CASE
                WHEN WORK_BASE_SI IS NOT NULL
                  AND CHAR_LENGTH(WORK_BASE_SI) BETWEEN 1 AND 256
                  AND WORK_BASE_SI REGEXP '[[:cntrl:]]'
                THEN 1 ELSE 0 END), 0) AS controlCharacterRows,
              COALESCE(SUM(CASE
                WHEN WORK_BASE_SI IS NOT NULL
                  AND CHAR_LENGTH(WORK_BASE_SI) BETWEEN 1 AND 256
                  AND WORK_BASE_SI NOT REGEXP '[[:cntrl:]]'
                  AND HEX(WORK_BASE_SI) REGEXP '%s'
                THEN 1 ELSE 0 END), 0) AS bidiControlRows,
              COALESCE(SUM(CASE
                WHEN WORK_BASE_SI IS NOT NULL
                  AND CHAR_LENGTH(WORK_BASE_SI) BETWEEN 1 AND 256
                  AND WORK_BASE_SI NOT REGEXP '[[:cntrl:]]'
                  AND HEX(WORK_BASE_SI) NOT REGEXP '%s'
                THEN 1 ELSE 0 END), 0) AS validRows
            FROM employee
            """.formatted(BIDI_HEX_PATTERN, BIDI_HEX_PATTERN);

    @Autowired
    private JdbcTemplate jdbcTemplate;
    @Autowired
    private ObjectMapper objectMapper;

    @Test
    void minimalDataContextLoadsWithoutExecutingQueries() {
        assertThat(jdbcTemplate).isNotNull();
        assertThat(objectMapper).isNotNull();
    }

    @Test
    @Transactional(readOnly = true)
    @EnabledIfEnvironmentVariable(
            named = "EXECUTE_EMPLOYEE_WORK_BASE_DATA_DIAG_QUERIES",
            matches = "1")
    void writesStrictMetadataAndMutuallyExclusiveAggregateEvidence() throws Exception {
        Path evidencePath = Path.of(required("EMPLOYEE_WORK_BASE_DATA_DIAG_EVIDENCE"));
        Path repositoryRoot = Path.of(required("EMPLOYEE_WORK_BASE_DATA_DIAG_REPOSITORY"));
        assertThat(evidencePath).doesNotExist();
        verifyHistory(repositoryRoot.resolve(SOURCE_EVIDENCE_PATH), SOURCE_EVIDENCE_SHA256);

        List<Map<String, Object>> metadataRows = jdbcTemplate.queryForList(METADATA_SQL);
        assertThat(metadataRows).hasSize(1);
        Map<String, Object> metadata = metadataRows.getFirst();
        Map<String, Object> aggregate = jdbcTemplate.queryForMap(AGGREGATE_SQL);

        long totalRows = count(aggregate, "totalRows");
        long nullRows = count(aggregate, "nullRows");
        long lengthInvalidRows = count(aggregate, "lengthInvalidRows");
        long controlCharacterRows = count(aggregate, "controlCharacterRows");
        long bidiControlRows = count(aggregate, "bidiControlRows");
        long validRows = count(aggregate, "validRows");
        assertThat(nullRows + lengthInvalidRows + controlCharacterRows
                + bidiControlRows + validRows).isEqualTo(totalRows);

        boolean sourceMatches = totalRows == 990L && validRows == 0L;
        String reason = reason(
                totalRows,
                nullRows,
                lengthInvalidRows,
                controlCharacterRows,
                bidiControlRows,
                sourceMatches);
        String nextStep = sourceMatches
                ? "separate_test_data_remediation_authorization_required"
                : "reconcile_source_snapshot_required";

        ObjectNode evidence = objectMapper.createObjectNode()
                .put("schemaVersion", 1)
                .put("workPackageId", "WP-EMP-EGRESS-WORK-BASE-DATA-DIAG-01")
                .put("runId", RUN_ID)
                .put("recordedAt", Instant.now().toString())
                .put("status", "completed");
        evidence.set("sourceEvidence", objectMapper.createObjectNode()
                .put("path", SOURCE_EVIDENCE_PATH)
                .put("sha256", SOURCE_EVIDENCE_SHA256)
                .put("expectedTotalRows", 990)
                .put("expectedValidRows", 0));
        ObjectNode column = objectMapper.createObjectNode()
                .put("dataType", requiredText(metadata, "dataType"))
                .put("columnType", requiredText(metadata, "columnType"))
                .put("isNullable", requiredText(metadata, "isNullable"));
        putNullableLong(column, "characterMaximumLength", metadata.get("characterMaximumLength"));
        putNullableText(column, "columnDefault", metadata.get("columnDefault"));
        putNullableText(column, "collationName", metadata.get("collationName"));
        evidence.set("columnDefinition", column);
        evidence.set("counts", objectMapper.createObjectNode()
                .put("totalRows", totalRows)
                .put("nullRows", nullRows)
                .put("lengthInvalidRows", lengthInvalidRows)
                .put("controlCharacterRows", controlCharacterRows)
                .put("bidiControlRows", bidiControlRows)
                .put("validRows", validRows)
                .put("metadataQueries", 1)
                .put("metadataResultRows", 1)
                .put("aggregateQueries", 1)
                .put("aggregateResultRows", 1)
                .put("employeeEndpointCalls", 0)
                .put("modelCalls", 0)
                .put("retryCount", 0)
                .put("resumeCount", 0));
        evidence.set("diagnosis", objectMapper.createObjectNode()
                .put("reason", reason)
                .put("distributionProven", sourceMatches)
                .put("sourceSnapshotMatches", sourceMatches)
                .put("nextStep", nextStep));
        evidence.set("safety", objectMapper.createObjectNode()
                .put("identifiersPersisted", false)
                .put("fieldValuesPersisted", false)
                .put("rawRowsPersisted", false)
                .put("jwtRead", false)
                .put("llmApiKeyRead", false)
                .put("modelOutbound", false)
                .put("logLeakCount", 0)
                .put("rawLogsDeleted", false));
        writeAndForce(evidencePath, evidence);
    }

    private static String reason(
            long totalRows,
            long nullRows,
            long lengthInvalidRows,
            long controlCharacterRows,
            long bidiControlRows,
            boolean sourceMatches) {
        if (!sourceMatches) {
            return "source_snapshot_mismatch";
        }
        if (nullRows == totalRows) {
            return "all_rows_null";
        }
        if (lengthInvalidRows == totalRows) {
            return "all_rows_length_invalid";
        }
        if (controlCharacterRows == totalRows) {
            return "all_rows_control_character_invalid";
        }
        if (bidiControlRows == totalRows) {
            return "all_rows_bidi_control_invalid";
        }
        return "mixed_invalid_values";
    }

    private static long count(Map<String, Object> row, String key) {
        Object value = row.get(key);
        if (!(value instanceof Number number) || number.longValue() < 0) {
            throw new IllegalStateException("employee.work_base_data_diagnostic_count_invalid");
        }
        return number.longValue();
    }

    private static String requiredText(Map<String, Object> row, String key) {
        Object value = row.get(key);
        if (!(value instanceof String text) || text.isBlank()) {
            throw new IllegalStateException("employee.work_base_data_diagnostic_metadata_invalid");
        }
        return text;
    }

    private static void putNullableLong(ObjectNode node, String key, Object value) {
        if (value == null) {
            node.putNull(key);
        } else if (value instanceof Number number && number.longValue() >= 0) {
            node.put(key, number.longValue());
        } else {
            throw new IllegalStateException("employee.work_base_data_diagnostic_metadata_invalid");
        }
    }

    private static void putNullableText(ObjectNode node, String key, Object value) {
        if (value == null) {
            node.putNull(key);
        } else if (value instanceof String text) {
            node.put(key, text);
        } else {
            throw new IllegalStateException("employee.work_base_data_diagnostic_metadata_invalid");
        }
    }

    private static void verifyHistory(Path path, String expectedSha256) throws Exception {
        assertThat(path).isRegularFile();
        String actual = HexFormat.of().formatHex(
                MessageDigest.getInstance("SHA-256").digest(Files.readAllBytes(path)));
        assertThat(actual).isEqualTo(expectedSha256);
    }

    private void writeAndForce(Path path, ObjectNode evidence) throws Exception {
        Path parent = path.getParent();
        if (parent != null) {
            Files.createDirectories(parent);
        }
        byte[] bytes = (objectMapper.writeValueAsString(evidence) + "\n")
                .getBytes(StandardCharsets.UTF_8);
        try (FileChannel channel = FileChannel.open(
                path,
                StandardOpenOption.CREATE_NEW,
                StandardOpenOption.WRITE)) {
            channel.write(ByteBuffer.wrap(bytes));
            channel.force(true);
        }
    }

    private static String required(String name) {
        String value = System.getenv(name);
        if (value == null || value.isBlank()) {
            throw new IllegalStateException("employee.work_base_data_diagnostic_env_missing:" + name);
        }
        return value.trim();
    }

    @SpringBootConfiguration
    @EnableAutoConfiguration
    static class DiagnosticApplication {
    }
}
