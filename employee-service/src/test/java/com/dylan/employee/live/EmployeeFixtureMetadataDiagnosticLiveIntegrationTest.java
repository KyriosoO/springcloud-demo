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
import java.util.Locale;
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
import com.fasterxml.jackson.databind.node.ArrayNode;
import com.fasterxml.jackson.databind.node.ObjectNode;

@EnabledIfEnvironmentVariable(named = "RUN_EMPLOYEE_FIXTURE_METADATA_DIAG", matches = "1")
@SpringBootTest(
        classes = EmployeeFixtureMetadataDiagnosticLiveIntegrationTest.DiagnosticApplication.class,
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
class EmployeeFixtureMetadataDiagnosticLiveIntegrationTest {
    private static final String RUN_ID =
            "employee-fixture-metadata-diagnostic-v1-20260814-run-01";
    private static final String SOURCE_EVIDENCE_PATH =
            "agent-runtime/tests/integration/adapters/employee/evidence/"
                    + "employee-work-base-data-diagnostic-v1-20260814-run-01.json";
    private static final String SOURCE_EVIDENCE_SHA256 =
            "b79f3601c3ead955e5cf747fa91cc000aad9773a1294c17277deeef05f92efe6";

    private static final String COLUMN_AND_ENGINE_SQL = """
            SELECT
              c.COLUMN_NAME AS columnName,
              c.ORDINAL_POSITION AS ordinalPosition,
              c.DATA_TYPE AS dataType,
              c.COLUMN_TYPE AS columnType,
              c.IS_NULLABLE AS isNullable,
              c.COLUMN_DEFAULT AS columnDefault,
              c.EXTRA AS extra,
              c.GENERATION_EXPRESSION AS generationExpression,
              c.CHARACTER_MAXIMUM_LENGTH AS characterMaximumLength,
              c.CHARACTER_SET_NAME AS characterSetName,
              c.COLLATION_NAME AS collationName,
              t.ENGINE AS tableEngine
            FROM information_schema.columns c
            JOIN information_schema.tables t
              ON t.TABLE_SCHEMA = c.TABLE_SCHEMA
             AND t.TABLE_NAME = c.TABLE_NAME
            WHERE c.TABLE_SCHEMA = DATABASE()
              AND LOWER(c.TABLE_NAME) = LOWER('employee')
            ORDER BY c.ORDINAL_POSITION
            """;

    private static final String KEY_AND_FOREIGN_KEY_SQL = """
            SELECT
              'owned' AS direction,
              tc.CONSTRAINT_NAME AS constraintName,
              tc.CONSTRAINT_TYPE AS constraintType,
              kcu.TABLE_NAME AS tableName,
              kcu.COLUMN_NAME AS columnName,
              kcu.ORDINAL_POSITION AS ordinalPosition,
              kcu.REFERENCED_TABLE_NAME AS referencedTableName,
              kcu.REFERENCED_COLUMN_NAME AS referencedColumnName
            FROM information_schema.table_constraints tc
            JOIN information_schema.key_column_usage kcu
              ON kcu.CONSTRAINT_SCHEMA = tc.CONSTRAINT_SCHEMA
             AND kcu.CONSTRAINT_NAME = tc.CONSTRAINT_NAME
             AND kcu.TABLE_SCHEMA = tc.TABLE_SCHEMA
             AND kcu.TABLE_NAME = tc.TABLE_NAME
            WHERE tc.TABLE_SCHEMA = DATABASE()
              AND LOWER(tc.TABLE_NAME) = LOWER('employee')
              AND tc.CONSTRAINT_TYPE IN ('PRIMARY KEY', 'UNIQUE', 'FOREIGN KEY')
            UNION ALL
            SELECT
              'inbound' AS direction,
              tc.CONSTRAINT_NAME AS constraintName,
              tc.CONSTRAINT_TYPE AS constraintType,
              kcu.TABLE_NAME AS tableName,
              kcu.COLUMN_NAME AS columnName,
              kcu.ORDINAL_POSITION AS ordinalPosition,
              kcu.REFERENCED_TABLE_NAME AS referencedTableName,
              kcu.REFERENCED_COLUMN_NAME AS referencedColumnName
            FROM information_schema.table_constraints tc
            JOIN information_schema.key_column_usage kcu
              ON kcu.CONSTRAINT_SCHEMA = tc.CONSTRAINT_SCHEMA
             AND kcu.CONSTRAINT_NAME = tc.CONSTRAINT_NAME
             AND kcu.TABLE_SCHEMA = tc.TABLE_SCHEMA
             AND kcu.TABLE_NAME = tc.TABLE_NAME
            WHERE tc.CONSTRAINT_TYPE = 'FOREIGN KEY'
              AND kcu.REFERENCED_TABLE_SCHEMA = DATABASE()
              AND LOWER(kcu.REFERENCED_TABLE_NAME) = LOWER('employee')
              AND NOT (kcu.TABLE_SCHEMA = DATABASE()
                       AND LOWER(kcu.TABLE_NAME) = LOWER('employee'))
            ORDER BY direction, constraintName, ordinalPosition
            """;

    private static final String CHECK_SQL = """
            SELECT
              tc.CONSTRAINT_NAME AS constraintName,
              cc.CHECK_CLAUSE AS checkClause
            FROM information_schema.table_constraints tc
            JOIN information_schema.check_constraints cc
              ON cc.CONSTRAINT_SCHEMA = tc.CONSTRAINT_SCHEMA
             AND cc.CONSTRAINT_NAME = tc.CONSTRAINT_NAME
            WHERE tc.TABLE_SCHEMA = DATABASE()
              AND LOWER(tc.TABLE_NAME) = LOWER('employee')
              AND tc.CONSTRAINT_TYPE = 'CHECK'
            ORDER BY tc.CONSTRAINT_NAME
            """;

    private static final String TRIGGER_SQL = """
            SELECT
              TRIGGER_NAME AS triggerName,
              ACTION_TIMING AS timing,
              EVENT_MANIPULATION AS event,
              ACTION_ORIENTATION AS orientation,
              ACTION_STATEMENT AS actionStatement
            FROM information_schema.triggers
            WHERE EVENT_OBJECT_SCHEMA = DATABASE()
              AND LOWER(EVENT_OBJECT_TABLE) = LOWER('employee')
            ORDER BY TRIGGER_NAME
            """;

    @Autowired
    private JdbcTemplate jdbcTemplate;
    @Autowired
    private ObjectMapper objectMapper;

    @Test
    void minimalMetadataContextLoadsWithoutExecutingQueries() {
        assertThat(jdbcTemplate).isNotNull();
        assertThat(objectMapper).isNotNull();
    }

    @Test
    @Transactional(readOnly = true)
    @EnabledIfEnvironmentVariable(
            named = "EXECUTE_EMPLOYEE_FIXTURE_METADATA_DIAG_QUERIES",
            matches = "1")
    void writesFourQueryInformationSchemaEvidence() throws Exception {
        Path evidencePath = Path.of(required("EMPLOYEE_FIXTURE_METADATA_DIAG_STAGING"));
        Path repositoryRoot = Path.of(required("EMPLOYEE_FIXTURE_METADATA_DIAG_REPOSITORY"));
        assertThat(evidencePath).doesNotExist();
        verifyHistory(repositoryRoot.resolve(SOURCE_EVIDENCE_PATH), SOURCE_EVIDENCE_SHA256);

        List<Map<String, Object>> columnRows = jdbcTemplate.queryForList(COLUMN_AND_ENGINE_SQL);
        List<Map<String, Object>> constraintRows = jdbcTemplate.queryForList(
                KEY_AND_FOREIGN_KEY_SQL);
        List<Map<String, Object>> checkRows = jdbcTemplate.queryForList(CHECK_SQL);
        List<Map<String, Object>> triggerRows = jdbcTemplate.queryForList(TRIGGER_SQL);

        assertThat(columnRows.size()).isBetween(1, 128);
        assertThat(constraintRows.size()).isBetween(0, 128);
        assertThat(checkRows.size()).isBetween(0, 128);
        assertThat(triggerRows.size()).isBetween(0, 128);
        String engine = requiredText(columnRows.getFirst(), "tableEngine");
        assertThat(columnRows)
                .allSatisfy(row -> assertThat(requiredText(row, "tableEngine")).isEqualTo(engine));

        ObjectNode evidence = objectMapper.createObjectNode()
                .put("schemaVersion", 1)
                .put("workPackageId", "WP-EMP-EGRESS-TEST-DATA-PREP-01")
                .put("runId", RUN_ID)
                .put("authorizationReference", "P3_00:GATE-050")
                .put("recordedAt", Instant.now().toString())
                .put("status", "collected");
        evidence.set("sourceEvidence", objectMapper.createObjectNode()
                .put("path", SOURCE_EVIDENCE_PATH)
                .put("sha256", SOURCE_EVIDENCE_SHA256));

        ObjectNode table = objectMapper.createObjectNode()
                .put("tableName", "employee")
                .put("engine", engine);
        ArrayNode columns = table.putArray("columns");
        for (Map<String, Object> row : columnRows) {
            ObjectNode column = columns.addObject()
                    .put("columnName", requiredText(row, "columnName").toUpperCase(Locale.ROOT))
                    .put("ordinalPosition", requiredLong(row, "ordinalPosition"))
                    .put("dataType", requiredText(row, "dataType").toLowerCase(Locale.ROOT))
                    .put("columnType", requiredText(row, "columnType"))
                    .put("isNullable", requiredText(row, "isNullable"))
                    .put("extra", textOrEmpty(row.get("extra")))
                    .put("generationExpression", textOrEmpty(row.get("generationExpression")));
            putNullableText(column, "columnDefault", row.get("columnDefault"));
            putNullableLong(column, "characterMaximumLength", row.get("characterMaximumLength"));
            putNullableText(column, "characterSetName", row.get("characterSetName"));
            putNullableText(column, "collationName", row.get("collationName"));
        }
        evidence.set("tableMetadata", table);

        ObjectNode constraintMetadata = objectMapper.createObjectNode();
        ArrayNode constraints = constraintMetadata.putArray("entries");
        for (Map<String, Object> row : constraintRows) {
            ObjectNode constraint = constraints.addObject()
                    .put("direction", requiredText(row, "direction"))
                    .put("constraintName", requiredText(row, "constraintName"))
                    .put("constraintType", requiredText(row, "constraintType"))
                    .put("tableName", requiredText(row, "tableName"))
                    .put("columnName", requiredText(row, "columnName").toUpperCase(Locale.ROOT))
                    .put("ordinalPosition", requiredLong(row, "ordinalPosition"));
            putNullableText(constraint, "referencedTableName", row.get("referencedTableName"));
            putNullableUpperText(
                    constraint, "referencedColumnName", row.get("referencedColumnName"));
        }
        ArrayNode checks = constraintMetadata.putArray("checks");
        for (Map<String, Object> row : checkRows) {
            checks.addObject()
                    .put("constraintName", requiredText(row, "constraintName"))
                    .put("checkClause", requiredText(row, "checkClause"));
        }
        evidence.set("constraintMetadata", constraintMetadata);

        ObjectNode triggerMetadata = objectMapper.createObjectNode();
        ArrayNode triggers = triggerMetadata.putArray("entries");
        for (Map<String, Object> row : triggerRows) {
            String statement = requiredText(row, "actionStatement");
            triggers.addObject()
                    .put("triggerName", requiredText(row, "triggerName"))
                    .put("timing", requiredText(row, "timing").toUpperCase(Locale.ROOT))
                    .put("event", requiredText(row, "event").toUpperCase(Locale.ROOT))
                    .put("orientation", requiredText(row, "orientation").toUpperCase(Locale.ROOT))
                    .put("actionStatementSha256", sha256(statement))
                    .put("sideEffectClassification", "present_requires_manual_review");
        }
        evidence.set("triggerMetadata", triggerMetadata);

        evidence.set("counts", objectMapper.createObjectNode()
                .put("maxQueries", 4)
                .put("executedQueries", 4)
                .put("columnQueries", 1)
                .put("columnResultRows", columnRows.size())
                .put("constraintQueries", 1)
                .put("constraintResultRows", constraintRows.size())
                .put("checkQueries", 1)
                .put("checkResultRows", checkRows.size())
                .put("triggerQueries", 1)
                .put("triggerResultRows", triggerRows.size())
                .put("employeeBusinessRowQueries", 0)
                .put("employeeEndpointCalls", 0)
                .put("authCalls", 0)
                .put("modelCalls", 0)
                .put("retryCount", 0)
                .put("resumeCount", 0));
        evidence.set("safety", objectMapper.createObjectNode()
                .put("businessRowsRead", false)
                .put("identifiersPersisted", false)
                .put("fieldValuesPersisted", false)
                .put("rawTriggerStatementsPersisted", false)
                .put("jwtRead", false)
                .put("llmApiKeyRead", false)
                .put("modelOutbound", false)
                .put("databaseWrites", 0)
                .put("schemaChanges", 0)
                .put("logLeakCount", 0)
                .put("rawLogsDeleted", false));
        writeAndForce(evidencePath, evidence);
    }

    private static long requiredLong(Map<String, Object> row, String key) {
        Object value = row.get(key);
        if (!(value instanceof Number number) || number.longValue() < 0) {
            throw new IllegalStateException("employee.fixture_metadata_diagnostic_metadata_invalid");
        }
        return number.longValue();
    }

    private static String requiredText(Map<String, Object> row, String key) {
        Object value = row.get(key);
        if (!(value instanceof String text) || text.isBlank()) {
            throw new IllegalStateException("employee.fixture_metadata_diagnostic_metadata_invalid");
        }
        return text;
    }

    private static String textOrEmpty(Object value) {
        return value == null ? "" : String.valueOf(value);
    }

    private static void putNullableLong(ObjectNode node, String key, Object value) {
        if (value == null) {
            node.putNull(key);
        } else if (value instanceof Number number && number.longValue() >= 0) {
            node.put(key, number.longValue());
        } else {
            throw new IllegalStateException("employee.fixture_metadata_diagnostic_metadata_invalid");
        }
    }

    private static void putNullableText(ObjectNode node, String key, Object value) {
        if (value == null) {
            node.putNull(key);
        } else {
            node.put(key, String.valueOf(value));
        }
    }

    private static void putNullableUpperText(ObjectNode node, String key, Object value) {
        if (value == null) {
            node.putNull(key);
        } else {
            node.put(key, String.valueOf(value).toUpperCase(Locale.ROOT));
        }
    }

    private static String sha256(String value) throws Exception {
        return HexFormat.of().formatHex(MessageDigest.getInstance("SHA-256")
                .digest(value.getBytes(StandardCharsets.UTF_8)));
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
            throw new IllegalStateException("employee.fixture_metadata_diagnostic_env_missing:" + name);
        }
        return value.trim();
    }

    @SpringBootConfiguration
    @EnableAutoConfiguration
    static class DiagnosticApplication {
    }
}
