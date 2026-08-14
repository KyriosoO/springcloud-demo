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
import java.util.concurrent.TimeUnit;

import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.condition.EnabledIfEnvironmentVariable;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.boot.test.web.server.LocalServerPort;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.test.context.bean.override.mockito.MockitoBean;

import com.dylan.employee.event.WorkflowInboxProcessor;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.fasterxml.jackson.databind.node.ObjectNode;

@EnabledIfEnvironmentVariable(named = "RUN_EMPLOYEE_EGRESS_INPUT_QUALIFY_V2", matches = "1")
@SpringBootTest(webEnvironment = SpringBootTest.WebEnvironment.RANDOM_PORT, properties = {
        "spring.cloud.config.enabled=false",
        "spring.config.import=",
        "spring.config.additional-location=optional:file:D:/codex/config-service/src/main/resources/config/",
        "spring.profiles.active=datasource,emp,ai-provider",
        "eureka.client.enabled=false",
        "spring.kafka.listener.auto-startup=false",
        "employee.workflow.inbox-retry-delay-ms=3600000",
        "common.security.secrets.source-order[0]=environment",
        "common.security.secrets.allow-config-values=false",
        "common.security.secrets.fail-fast=true",
        "common.security.secrets.jwt.active-key-id=ACTIVE",
        "common.security.secrets.jwt.keys.ACTIVE.env=COMMON_SECURITY_JWT_HMAC_KEY_ACTIVE",
        "common.security.secrets.jwt.keys.ACTIVE.value="
})
class EmployeeEgressInputQualificationV2LiveIntegrationTest {
    private static final String RUN_ID =
            "employee-egress-input-qualification-v2-20260814-candidate-02";
    private static final String AUTHORIZATION_REFERENCE = "P3_00:GATE-049";
    private static final String QUALIFIED_IDENTIFIER_SQL = """
            SELECT ID_CARD_NO
            FROM employee
            WHERE ID_CARD_NO IS NOT NULL
              AND CHAR_LENGTH(ID_CARD_NO) BETWEEN 5 AND 64
              AND OCTET_LENGTH(ID_CARD_NO) <= 192
              AND ID_CARD_NO NOT REGEXP '[[:space:]/\\\\%?#]'
              AND ID_CARD_NO NOT REGEXP '[[:cntrl:]]'
              AND HEX(ID_CARD_NO) NOT REGEXP '(E280AA|E280AB|E280AC|E280AD|E280AE|E281A6|E281A7|E281A8|E281A9)'
              AND CHINESE_NAME IS NOT NULL
              AND CHAR_LENGTH(CHINESE_NAME) BETWEEN 1 AND 128
              AND CHINESE_NAME NOT REGEXP '[[:cntrl:]]'
              AND HEX(CHINESE_NAME) NOT REGEXP '(E280AA|E280AB|E280AC|E280AD|E280AE|E281A6|E281A7|E281A8|E281A9)'
              AND POSITION IS NOT NULL
              AND CHAR_LENGTH(POSITION) BETWEEN 1 AND 256
              AND POSITION NOT REGEXP '[[:cntrl:]]'
              AND HEX(POSITION) NOT REGEXP '(E280AA|E280AB|E280AC|E280AD|E280AE|E281A6|E281A7|E281A8|E281A9)'
              AND WORK_BASE_SI IS NOT NULL
              AND CHAR_LENGTH(WORK_BASE_SI) BETWEEN 1 AND 256
              AND WORK_BASE_SI NOT REGEXP '[[:cntrl:]]'
              AND HEX(WORK_BASE_SI) NOT REGEXP '(E280AA|E280AB|E280AC|E280AD|E280AE|E281A6|E281A7|E281A8|E281A9)'
            ORDER BY ID_CARD_NO
            LIMIT 1
            """;

    @LocalServerPort
    private int port;
    @Autowired
    private JdbcTemplate jdbcTemplate;
    @Autowired
    private ObjectMapper objectMapper;
    @MockitoBean
    private WorkflowInboxProcessor workflowInboxProcessor;

    @Test
    void selectsAtMostOneCodecCompleteInputAndDelegatesOneDetail() throws Exception {
        Path lifecycle = Path.of(required("EMPLOYEE_EGRESS_INPUT_QUALIFY_V2_LIFECYCLE"));
        Path result = Path.of(required("EMPLOYEE_EGRESS_INPUT_QUALIFY_V2_RESULT"));
        String manifestSha256 = required("EMPLOYEE_EGRESS_INPUT_QUALIFY_V2_MANIFEST_SHA256");
        createLifecycleJournal(lifecycle, manifestSha256);
        appendEvent(lifecycle, common(manifestSha256).put("event", "database_selection_started")
                .put("queryOrdinal", 1));

        List<String> candidates;
        try {
            candidates = jdbcTemplate.query(
                    QUALIFIED_IDENTIFIER_SQL,
                    (resultSet, rowNumber) -> resultSet.getString(1));
        }
        catch (RuntimeException exception) {
            appendEvent(lifecycle, common(manifestSha256)
                    .put("event", "database_selection_terminal")
                    .put("queryOrdinal", 1)
                    .put("status", "failed")
                    .put("selectedRows", 0));
            appendFailureTerminal(
                    lifecycle,
                    manifestSha256,
                    "failed",
                    "database_selection",
                    "employee.database_selection_failed");
            writeLimitedFailureResult(
                    lifecycle,
                    result,
                    manifestSha256,
                    "failed",
                    "database_selection",
                    "employee.database_selection_failed",
                    0);
            throw exception;
        }
        assertThat(candidates).hasSizeLessThanOrEqualTo(1);
        appendEvent(lifecycle, common(manifestSha256)
                .put("event", "database_selection_terminal")
                .put("queryOrdinal", 1)
                .put("status", "completed")
                .put("selectedRows", candidates.size()));
        if (candidates.isEmpty()) {
            appendFailureTerminal(
                    lifecycle,
                    manifestSha256,
                    "not_qualified",
                    "database_selection",
                    "employee.no_qualified_input");
            writeLimitedFailureResult(
                    lifecycle,
                    result,
                    manifestSha256,
                    "not_qualified",
                    "database_selection",
                    "employee.no_qualified_input",
                    0);
            return;
        }

        String identifier = candidates.getFirst();
        ProcessBuilder processBuilder = new ProcessBuilder(
                required("EMPLOYEE_EGRESS_INPUT_QUALIFY_V2_PYTHON"),
                "-m", "pytest",
                "tests/integration/adapters/employee/"
                        + "test_real_employee_egress_input_qualification_v2.py",
                "-q", "--tb=no");
        processBuilder.directory(
                Path.of(required("EMPLOYEE_EGRESS_INPUT_QUALIFY_V2_REPOSITORY"))
                        .resolve("agent-runtime")
                        .toFile());
        processBuilder.redirectErrorStream(true);
        processBuilder.redirectOutput(
                Path.of(required("EMPLOYEE_EGRESS_INPUT_QUALIFY_V2_PYTHON_LOG")).toFile());
        Map<String, String> environment = processBuilder.environment();
        environment.put("PYTHONPATH", "src;.");
        environment.put("RUN_EMPLOYEE_EGRESS_INPUT_QUALIFY_V2", "1");
        environment.put("EMPLOYEE_EGRESS_INPUT_QUALIFY_V2_IDENTIFIER", identifier);
        environment.put(
                "EMPLOYEE_EGRESS_INPUT_QUALIFY_V2_ADMIN_JWT",
                required("EMPLOYEE_EGRESS_INPUT_QUALIFY_V2_ADMIN_JWT"));
        environment.put(
                "EMPLOYEE_EGRESS_INPUT_QUALIFY_V2_BASE_URL",
                "http://127.0.0.1:" + port);

        Process process = processBuilder.start();
        boolean finished = process.waitFor(60, TimeUnit.SECONDS);
        if (!finished) {
            process.destroyForcibly();
            process.waitFor(10, TimeUnit.SECONDS);
        }
        boolean failed = !finished || !process.isAlive() && process.exitValue() != 0;
        if (failed) {
            String lifecycleText = Files.readString(lifecycle, StandardCharsets.UTF_8);
            if (lifecycleText.contains("\"event\":\"employee_detail_started\"")
                    && !lifecycleText.contains("\"event\":\"employee_detail_terminal\"")) {
                appendEvent(lifecycle, common(manifestSha256)
                        .put("event", "employee_detail_terminal")
                        .put("requestOrdinal", 1)
                        .put("status", "failed"));
            }
            if (!lifecycleText.contains("\"event\":\"run_terminal\"")) {
                appendFailureTerminal(
                        lifecycle,
                        manifestSha256,
                        "failed",
                        "employee_detail",
                        "employee.request_failed");
            }
            if (!java.nio.file.Files.exists(result)) {
                writeLimitedFailureResult(
                        lifecycle,
                        result,
                        manifestSha256,
                        "failed",
                        "employee_detail",
                        "employee.request_failed",
                        1);
            }
        }
        assertThat(finished).isTrue();
        assertThat(process.exitValue()).isZero();
    }

    private void createLifecycleJournal(Path path, String manifestSha256) throws Exception {
        ObjectNode first = common(manifestSha256)
                .put("event", "run_started")
                .put("selectionMode", "read_only_database")
                .put("databaseSelectionMaximumRows", 1)
                .put("employeeDetailMaximumRequests", 1)
                .put("modelMaximumCalls", 0)
                .put("retryAllowed", false)
                .put("resumeAllowed", false);
        writeAndForce(path, first, StandardOpenOption.CREATE_NEW, StandardOpenOption.WRITE);
    }

    private void appendFailureTerminal(
            Path path,
            String manifestSha256,
            String status,
            String phase,
            String reason) throws Exception {
        appendEvent(path, common(manifestSha256)
                .put("event", "run_terminal")
                .put("status", status)
                .put("failurePhase", phase)
                .put("failureReason", reason));
    }

    private void appendEvent(Path path, ObjectNode event) throws Exception {
        writeAndForce(path, event, StandardOpenOption.WRITE, StandardOpenOption.APPEND);
    }

    private void writeLimitedFailureResult(
            Path lifecycle,
            Path result,
            String manifestSha256,
            String status,
            String phase,
            String reason,
            int selectedRows) throws Exception {
        String lifecycleText = Files.readString(lifecycle, StandardCharsets.UTF_8);
        ObjectNode value = common(manifestSha256)
                .put("recordedAt", Instant.now().toString())
                .put("status", status)
                .put("selectionMode", "read_only_database")
                .put("egressReason", reason);
        value.set("codecMinimumFieldPresence", objectMapper.createObjectNode()
                .put("idCardNo", false)
                .put("chineseName", false)
                .put("position", false)
                .put("workBaseSi", false));
        value.set("requiredUserResultFieldPresence", objectMapper.createObjectNode()
                .put("employeeIdMasked", false)
                .put("chineseName", false));
        value.set("counts", objectMapper.createObjectNode()
                .put("databaseSelectionStarted", countEvent(lifecycleText, "database_selection_started"))
                .put("databaseSelectionTerminal", countEvent(lifecycleText, "database_selection_terminal"))
                .put("databaseSelectionRows", selectedRows)
                .put("employeeDetailStarted", countEvent(lifecycleText, "employee_detail_started"))
                .put("employeeDetailTerminal", countEvent(lifecycleText, "employee_detail_terminal"))
                .put("otherEmployeeEndpoints", 0)
                .put("modelCalls", 0)
                .put("retryCount", 0)
                .put("resumeCount", 0));
        value.set("failure", objectMapper.createObjectNode()
                .put("phase", phase)
                .put("reason", reason));
        value.set("lifecycle", objectMapper.createObjectNode()
                .put("recordCount", Files.readAllLines(lifecycle, StandardCharsets.UTF_8).size())
                .put("sha256", HexFormat.of().formatHex(
                        MessageDigest.getInstance("SHA-256").digest(Files.readAllBytes(lifecycle)))));
        value.set("safety", objectMapper.createObjectNode()
                .put("identifierPersisted", false)
                .put("jwtPersisted", false)
                .put("fieldValuesPersisted", false)
                .put("rawResponsePersisted", false)
                .put("llmApiKeyRead", false)
                .put("modelOutbound", false)
                .put("logLeakCount", 0)
                .put("logScanCompleted", false)
                .put("rawLogsDeleted", false));
        writeAndForce(result, value, StandardOpenOption.CREATE_NEW, StandardOpenOption.WRITE);
    }

    private static int countEvent(String lifecycleText, String event) {
        int count = 0;
        int offset = 0;
        String marker = "\"event\":\"" + event + "\"";
        while ((offset = lifecycleText.indexOf(marker, offset)) >= 0) {
            count++;
            offset += marker.length();
        }
        return count;
    }

    private void writeAndForce(Path path, ObjectNode event, StandardOpenOption... options)
            throws Exception {
        byte[] bytes = (objectMapper.writeValueAsString(event) + "\n")
                .getBytes(StandardCharsets.UTF_8);
        try (FileChannel channel = FileChannel.open(path, options)) {
            channel.write(ByteBuffer.wrap(bytes));
            channel.force(true);
        }
    }

    private ObjectNode common(String manifestSha256) {
        return objectMapper.createObjectNode()
                .put("schemaVersion", 2)
                .put("workPackageId", "WP-EMP-EGRESS-INPUT-QUALIFY-02")
                .put("gateId", "GATE-049")
                .put("runId", RUN_ID)
                .put("manifestSha256", manifestSha256)
                .put("authorizationReference", AUTHORIZATION_REFERENCE);
    }

    private static String required(String name) {
        String value = System.getenv(name);
        if (value == null || value.isBlank()) {
            throw new IllegalStateException("employee.egress_input_qualification_v2_env_missing:" + name);
        }
        return value.trim();
    }
}
