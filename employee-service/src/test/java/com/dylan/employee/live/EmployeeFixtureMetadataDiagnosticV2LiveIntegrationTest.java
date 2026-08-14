package com.dylan.employee.live;

import static org.assertj.core.api.Assertions.assertThat;

import java.io.IOException;
import java.nio.ByteBuffer;
import java.nio.channels.FileChannel;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.StandardOpenOption;
import java.security.MessageDigest;
import java.sql.SQLException;
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
import org.springframework.core.NestedExceptionUtils;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.transaction.annotation.Transactional;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.fasterxml.jackson.databind.node.ArrayNode;
import com.fasterxml.jackson.databind.node.ObjectNode;

@EnabledIfEnvironmentVariable(named = "RUN_EMPLOYEE_FIXTURE_METADATA_DIAG_V2", matches = "1")
@SpringBootTest(
        classes = EmployeeFixtureMetadataDiagnosticV2LiveIntegrationTest.DiagnosticApplication.class,
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
class EmployeeFixtureMetadataDiagnosticV2LiveIntegrationTest {
    private static final int MAX_QUERIES = 4;
    private static final String RUN_ID =
            "employee-fixture-metadata-diagnostic-v2-20260814-candidate-02";
    private static final String AUTHORIZATION_REFERENCE = "P3_00:GATE-050";
    private static final String PREPARATION_WORK_PACKAGE_ID =
            "WP-EMP-EGRESS-FIXTURE-METADATA-CANDIDATE-02-PREP";
    private static final String WORK_PACKAGE_ID = "WP-EMP-EGRESS-TEST-DATA-PREP-01";
    private static final Map<String, String> HISTORY = Map.of(
            "agent-runtime/tests/integration/adapters/employee/evidence/"
                    + "employee-work-base-data-diagnostic-v1-20260814-run-01.json",
            "b79f3601c3ead955e5cf747fa91cc000aad9773a1294c17277deeef05f92efe6",
            "agent-runtime/tests/integration/adapters/employee/evidence/"
                    + "employee-fixture-metadata-diagnostic-v1-20260814-run-01.failure.json",
            "dce5e7659ed9cc49b52aa9cca6b70c9701c22cc55867f26cfa6a50ead291e7a1",
            "agent-runtime/tests/integration/adapters/employee/evidence/"
                    + "employee-fixture-metadata-diagnostic-v1-failure.schema.json",
            "e9182239e7425a071c7daaf4c2a74fb3ef354fec9907ca0da5cef92f8ac85adc");

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
              ON BINARY t.TABLE_SCHEMA = BINARY c.TABLE_SCHEMA
             AND BINARY t.TABLE_NAME = BINARY c.TABLE_NAME
            WHERE BINARY c.TABLE_SCHEMA = BINARY DATABASE()
              AND BINARY c.TABLE_NAME = BINARY 'employee'
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
              ON BINARY kcu.CONSTRAINT_SCHEMA = BINARY tc.CONSTRAINT_SCHEMA
             AND BINARY kcu.CONSTRAINT_NAME = BINARY tc.CONSTRAINT_NAME
             AND BINARY kcu.TABLE_SCHEMA = BINARY tc.TABLE_SCHEMA
             AND BINARY kcu.TABLE_NAME = BINARY tc.TABLE_NAME
            WHERE BINARY tc.TABLE_SCHEMA = BINARY DATABASE()
              AND BINARY tc.TABLE_NAME = BINARY 'employee'
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
              ON BINARY kcu.CONSTRAINT_SCHEMA = BINARY tc.CONSTRAINT_SCHEMA
             AND BINARY kcu.CONSTRAINT_NAME = BINARY tc.CONSTRAINT_NAME
             AND BINARY kcu.TABLE_SCHEMA = BINARY tc.TABLE_SCHEMA
             AND BINARY kcu.TABLE_NAME = BINARY tc.TABLE_NAME
            WHERE tc.CONSTRAINT_TYPE = 'FOREIGN KEY'
              AND BINARY kcu.REFERENCED_TABLE_SCHEMA = BINARY DATABASE()
              AND BINARY kcu.REFERENCED_TABLE_NAME = BINARY 'employee'
              AND NOT (BINARY kcu.TABLE_SCHEMA = BINARY DATABASE()
                       AND BINARY kcu.TABLE_NAME = BINARY 'employee')
            ORDER BY direction, constraintName, ordinalPosition
            """;

    private static final String CHECK_SQL = """
            SELECT
              tc.CONSTRAINT_NAME AS constraintName,
              cc.CHECK_CLAUSE AS checkClause
            FROM information_schema.table_constraints tc
            JOIN information_schema.check_constraints cc
              ON BINARY cc.CONSTRAINT_SCHEMA = BINARY tc.CONSTRAINT_SCHEMA
             AND BINARY cc.CONSTRAINT_NAME = BINARY tc.CONSTRAINT_NAME
            WHERE BINARY tc.TABLE_SCHEMA = BINARY DATABASE()
              AND BINARY tc.TABLE_NAME = BINARY 'employee'
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
            WHERE BINARY EVENT_OBJECT_SCHEMA = BINARY DATABASE()
              AND BINARY EVENT_OBJECT_TABLE = BINARY 'employee'
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
            named = "EXECUTE_EMPLOYEE_FIXTURE_METADATA_DIAG_V2_QUERIES",
            matches = "1")
    void writesCollationNeutralFourQueryEvidenceWithDurableLifecycle() throws Exception {
        Path repositoryRoot = Path.of(required("EMPLOYEE_FIXTURE_METADATA_DIAG_V2_REPOSITORY"));
        Path lifecyclePath = Path.of(required("EMPLOYEE_FIXTURE_METADATA_DIAG_V2_LIFECYCLE"));
        Path stagingPath = Path.of(required("EMPLOYEE_FIXTURE_METADATA_DIAG_V2_STAGING"));
        assertThat(lifecyclePath).doesNotExist();
        assertThat(stagingPath).doesNotExist();
        verifyHistory(repositoryRoot);

        LifecycleWriter journal = new LifecycleWriter(lifecyclePath, objectMapper);
        int succeeded = 0;
        try {
            List<Map<String, Object>> columns = executeQuery(
                    journal, "column_and_engine", 1, COLUMN_AND_ENGINE_SQL);
            succeeded++;
            List<Map<String, Object>> constraints = executeQuery(
                    journal, "key_and_foreign_key", 2, KEY_AND_FOREIGN_KEY_SQL);
            succeeded++;
            List<Map<String, Object>> checks = executeQuery(
                    journal, "check_constraints", 3, CHECK_SQL);
            succeeded++;
            List<Map<String, Object>> triggers = executeQuery(
                    journal, "triggers", 4, TRIGGER_SQL);
            succeeded++;
            ObjectNode result = successResult(columns, constraints, checks, triggers);
            writeAndForce(stagingPath, result);
            journal.runTerminal(true, null);
        } catch (MetadataQueryFailure failure) {
            journal.runTerminal(false, "information_schema_query_failed");
            writeAndForce(stagingPath, failureResult(failure, succeeded));
            throw failure;
        } catch (RuntimeException failure) {
            journal.runTerminal(false, "metadata_invalid");
            writeAndForce(stagingPath, assemblyFailureResult(succeeded));
            throw failure;
        }
    }

    private List<Map<String, Object>> executeQuery(
            LifecycleWriter journal,
            String phase,
            int ordinal,
            String sql) {
        journal.queryStarted(phase, ordinal);
        try {
            List<Map<String, Object>> rows = jdbcTemplate.queryForList(sql);
            if (rows.size() > 128) {
                throw new IllegalStateException(
                        "employee.fixture_metadata_v2_metadata_invalid");
            }
            journal.queryTerminal(phase, ordinal, true, null);
            return rows;
        } catch (RuntimeException failure) {
            journal.queryTerminal(
                    phase, ordinal, false, "information_schema_query_failed");
            Throwable root = NestedExceptionUtils.getMostSpecificCause(failure);
            String sqlState = root instanceof SQLException sqlFailure
                    ? sqlFailure.getSQLState() : null;
            Integer vendorCode = root instanceof SQLException sqlFailure
                    ? sqlFailure.getErrorCode() : null;
            throw new MetadataQueryFailure(phase, ordinal, sqlState, vendorCode, failure);
        }
    }

    private ObjectNode successResult(
            List<Map<String, Object>> columnRows,
            List<Map<String, Object>> constraintRows,
            List<Map<String, Object>> checkRows,
            List<Map<String, Object>> triggerRows) {
        if (columnRows.isEmpty()) {
            throw new IllegalStateException("employee.fixture_metadata_v2_metadata_invalid");
        }
        String engine = requiredText(columnRows.getFirst(), "tableEngine");
        ObjectNode result = baseResult("passed", 4, 4, 4, 0);
        ObjectNode metadata = result.putObject("metadata");
        ObjectNode table = metadata.putObject("table")
                .put("name", "employee")
                .put("engine", engine);
        ArrayNode columns = table.putArray("columns");
        for (Map<String, Object> row : columnRows) {
            if (!requiredText(row, "tableEngine").equals(engine)) {
                throw new IllegalStateException("employee.fixture_metadata_v2_metadata_invalid");
            }
            ObjectNode column = columns.addObject()
                    .put("name", requiredText(row, "columnName").toUpperCase(Locale.ROOT))
                    .put("ordinal", requiredLong(row, "ordinalPosition"))
                    .put("dataType", requiredText(row, "dataType").toLowerCase(Locale.ROOT))
                    .put("columnType", requiredText(row, "columnType"))
                    .put("nullable", requiredText(row, "isNullable"))
                    .put("extra", textOrEmpty(row.get("extra")))
                    .put("generationExpression", textOrEmpty(row.get("generationExpression")));
            putNullableText(column, "default", row.get("columnDefault"));
            putNullableLong(column, "maximumLength", row.get("characterMaximumLength"));
            putNullableText(column, "characterSet", row.get("characterSetName"));
            putNullableText(column, "collation", row.get("collationName"));
        }
        ArrayNode constraints = metadata.putArray("constraints");
        for (Map<String, Object> row : constraintRows) {
            ObjectNode constraint = constraints.addObject()
                    .put("direction", requiredText(row, "direction"))
                    .put("name", requiredText(row, "constraintName"))
                    .put("type", requiredText(row, "constraintType"))
                    .put("table", requiredText(row, "tableName"))
                    .put("column", requiredText(row, "columnName").toUpperCase(Locale.ROOT))
                    .put("ordinal", requiredLong(row, "ordinalPosition"));
            putNullableText(constraint, "referencedTable", row.get("referencedTableName"));
            putNullableUpperText(constraint, "referencedColumn", row.get("referencedColumnName"));
        }
        ArrayNode checks = metadata.putArray("checks");
        for (Map<String, Object> row : checkRows) {
            checks.addObject()
                    .put("name", requiredText(row, "constraintName"))
                    .put("expressionSha256", sha256(requiredText(row, "checkClause")));
        }
        ArrayNode triggers = metadata.putArray("triggers");
        for (Map<String, Object> row : triggerRows) {
            triggers.addObject()
                    .put("name", requiredText(row, "triggerName"))
                    .put("timing", requiredText(row, "timing").toUpperCase(Locale.ROOT))
                    .put("event", requiredText(row, "event").toUpperCase(Locale.ROOT))
                    .put("orientation", requiredText(row, "orientation").toUpperCase(Locale.ROOT))
                    .put("actionSha256", sha256(requiredText(row, "actionStatement")))
                    .put("sideEffectClassification", "present_requires_manual_review");
        }
        return result;
    }

    private ObjectNode failureResult(MetadataQueryFailure failure, int succeeded) {
        ObjectNode result = baseResult(
                "failed", failure.ordinal(), failure.ordinal(), succeeded, 1);
        ObjectNode failureNode = result.putObject("failure")
                .put("phase", failure.phase())
                .put("reason", "information_schema_query_failed")
                .put("queryOrdinal", failure.ordinal());
        putNullableText(failureNode, "sqlState", failure.sqlState());
        if (failure.vendorCode() == null) {
            failureNode.putNull("vendorCode");
        } else {
            failureNode.put("vendorCode", failure.vendorCode());
        }
        return result;
    }

    private ObjectNode assemblyFailureResult(int succeeded) {
        ObjectNode result = baseResult("failed", MAX_QUERIES, MAX_QUERIES, succeeded, 0);
        result.putObject("failure")
                .put("phase", "result_assembly")
                .put("reason", "metadata_invalid")
                .put("queryOrdinal", MAX_QUERIES)
                .putNull("sqlState")
                .putNull("vendorCode");
        return result;
    }

    private ObjectNode baseResult(
            String status, int started, int terminal, int succeeded, int failed) {
        ObjectNode result = objectMapper.createObjectNode()
                .put("schemaVersion", 2)
                .put("preparationWorkPackageId", PREPARATION_WORK_PACKAGE_ID)
                .put("workPackageId", WORK_PACKAGE_ID)
                .put("gateId", "GATE-050")
                .put("runId", RUN_ID)
                .put("authorizationReference", AUTHORIZATION_REFERENCE)
                .put("status", status);
        ArrayNode history = result.putArray("history");
        HISTORY.entrySet().stream().sorted(Map.Entry.comparingByKey()).forEach(entry ->
                history.addObject().put("path", entry.getKey()).put("sha256", entry.getValue()));
        result.set("queryCounts", objectMapper.createObjectNode()
                .put("maximum", MAX_QUERIES)
                .put("started", started)
                .put("terminal", terminal)
                .put("succeeded", succeeded)
                .put("failed", failed)
                .put("retryCount", 0)
                .put("resumeCount", 0));
        result.set("safety", objectMapper.createObjectNode()
                .put("businessRowsRead", false)
                .put("employeeEndpointCalls", 0)
                .put("authCalls", 0)
                .put("jwtRead", false)
                .put("llmApiKeyRead", false)
                .put("modelCalls", 0)
                .put("modelOutbound", false)
                .put("databaseWrites", 0)
                .put("schemaChanges", 0)
                .put("identifiersPersisted", false)
                .put("fieldValuesPersisted", false)
                .put("rawTriggerStatementsPersisted", false)
                .put("logLeakCount", 0)
                .put("rawLogsDeleted", false));
        return result;
    }

    private static long requiredLong(Map<String, Object> row, String key) {
        Object value = row.get(key);
        if (!(value instanceof Number number) || number.longValue() <= 0) {
            throw new IllegalStateException("employee.fixture_metadata_v2_metadata_invalid");
        }
        return number.longValue();
    }

    private static String requiredText(Map<String, Object> row, String key) {
        Object value = row.get(key);
        if (!(value instanceof String text) || text.isBlank()) {
            throw new IllegalStateException("employee.fixture_metadata_v2_metadata_invalid");
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
            throw new IllegalStateException("employee.fixture_metadata_v2_metadata_invalid");
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

    private static String sha256(String value) {
        try {
            return HexFormat.of().formatHex(MessageDigest.getInstance("SHA-256")
                    .digest(value.getBytes(StandardCharsets.UTF_8)));
        } catch (java.security.NoSuchAlgorithmException failure) {
            throw new IllegalStateException(
                    "employee.fixture_metadata_v2_digest_unavailable", failure);
        }
    }

    private static void verifyHistory(Path repositoryRoot) throws Exception {
        for (Map.Entry<String, String> entry : HISTORY.entrySet()) {
            Path path = repositoryRoot.resolve(entry.getKey());
            assertThat(path).isRegularFile();
            assertThat(HexFormat.of().formatHex(
                    MessageDigest.getInstance("SHA-256").digest(Files.readAllBytes(path))))
                    .isEqualTo(entry.getValue());
        }
    }

    private void writeAndForce(Path path, ObjectNode value) {
        try {
            byte[] bytes = (objectMapper.writeValueAsString(value) + "\n")
                    .getBytes(StandardCharsets.UTF_8);
            Path parent = path.getParent();
            if (parent != null) {
                Files.createDirectories(parent);
            }
            try (FileChannel channel = FileChannel.open(
                    path, StandardOpenOption.CREATE_NEW, StandardOpenOption.WRITE)) {
                channel.write(ByteBuffer.wrap(bytes));
                channel.force(true);
            }
        } catch (IOException failure) {
            throw new IllegalStateException(
                    "employee.fixture_metadata_v2_result_write_failed", failure);
        }
    }

    private static String required(String name) {
        String value = System.getenv(name);
        if (value == null || value.isBlank()) {
            throw new IllegalStateException("employee.fixture_metadata_v2_env_missing:" + name);
        }
        return value.trim();
    }

    private static final class MetadataQueryFailure extends RuntimeException {
        private final String phase;
        private final int ordinal;
        private final String sqlState;
        private final Integer vendorCode;

        private MetadataQueryFailure(
                String phase,
                int ordinal,
                String sqlState,
                Integer vendorCode,
                RuntimeException cause) {
            super("employee.fixture_metadata_v2_query_failed", cause);
            this.phase = phase;
            this.ordinal = ordinal;
            this.sqlState = sqlState;
            this.vendorCode = vendorCode;
        }

        private String phase() {
            return phase;
        }

        private int ordinal() {
            return ordinal;
        }

        private String sqlState() {
            return sqlState;
        }

        private Integer vendorCode() {
            return vendorCode;
        }
    }

    private static final class LifecycleWriter {
        private final Path path;
        private final ObjectMapper objectMapper;
        private int sequence;
        private boolean closed;

        private LifecycleWriter(Path path, ObjectMapper objectMapper) throws IOException {
            this.path = path;
            this.objectMapper = objectMapper;
            Path parent = path.getParent();
            if (parent != null) {
                Files.createDirectories(parent);
            }
            try (FileChannel channel = FileChannel.open(
                    path, StandardOpenOption.CREATE_NEW, StandardOpenOption.WRITE)) {
                channel.force(true);
            }
            append("run_started", "run", "started", null, 0);
        }

        private void queryStarted(String phase, int ordinal) {
            append("query_started", phase, "started", null, ordinal);
        }

        private void queryTerminal(
                String phase, int ordinal, boolean succeeded, String reason) {
            append(
                    "query_terminal",
                    phase,
                    succeeded ? "succeeded" : "failed",
                    reason,
                    ordinal);
        }

        private void runTerminal(boolean succeeded, String reason) {
            append("run_terminal", "run", succeeded ? "passed" : "failed", reason, 0);
            closed = true;
        }

        private void append(
                String event, String phase, String status, String reason, int ordinal) {
            if (closed) {
                throw new IllegalStateException("employee.fixture_metadata_v2_lifecycle_closed");
            }
            sequence++;
            ObjectNode record = objectMapper.createObjectNode()
                    .put("schemaVersion", 2)
                    .put("runId", RUN_ID)
                    .put("authorizationReference", AUTHORIZATION_REFERENCE)
                    .put("sequence", sequence)
                    .put("event", event)
                    .put("phase", phase)
                    .put("status", status)
                    .put("queryOrdinal", ordinal)
                    .put("retryCount", 0)
                    .put("resumeCount", 0);
            if (reason == null) {
                record.putNull("reason");
            } else {
                record.put("reason", reason);
            }
            byte[] bytes;
            try {
                bytes = (objectMapper.writeValueAsString(record) + "\n")
                        .getBytes(StandardCharsets.UTF_8);
                try (FileChannel channel = FileChannel.open(
                        path, StandardOpenOption.APPEND, StandardOpenOption.WRITE)) {
                    channel.write(ByteBuffer.wrap(bytes));
                    channel.force(true);
                }
            } catch (IOException failure) {
                throw new IllegalStateException(
                        "employee.fixture_metadata_v2_lifecycle_write_failed", failure);
            }
        }
    }

    @SpringBootConfiguration
    @EnableAutoConfiguration
    static class DiagnosticApplication {
    }
}
