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
import java.util.Map;

import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.condition.EnabledIfEnvironmentVariable;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.SpringBootConfiguration;
import org.springframework.boot.autoconfigure.EnableAutoConfiguration;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.jdbc.core.JdbcTemplate;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.fasterxml.jackson.databind.node.ObjectNode;

@EnabledIfEnvironmentVariable(named = "RUN_EMPLOYEE_EGRESS_INPUT_QUALIFY_DIAG_V2", matches = "1")
@SpringBootTest(
        classes = EmployeeEgressInputQualificationDiagnosticV2LiveIntegrationTest.DiagnosticApplication.class,
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
class EmployeeEgressInputQualificationDiagnosticV2LiveIntegrationTest {
    private static final String RUN_ID =
            "employee-egress-input-qualification-diagnostic-v2-20260814-run-01";
    private static final String CANDIDATE_RUN_ID =
            "employee-egress-input-qualification-v2-20260814-candidate-02";
    private static final String CANDIDATE_LIFECYCLE_SHA256 =
            "570295951f8bf1a109156c017c30609ca548bfba3f021bff4cd2825f978ac231";
    private static final String CANDIDATE_RESULT_SHA256 =
            "7534b1d04a1512720dcbee1fe630114fb1f08bf9c3615dec1d2cb18bec4d5054";
    private static final String CANDIDATE_LIFECYCLE_PATH =
            "agent-runtime/tests/integration/adapters/employee/evidence/"
                    + "employee-egress-input-qualification-v2-20260814-candidate-02.lifecycle.jsonl";
    private static final String CANDIDATE_RESULT_PATH =
            "agent-runtime/tests/integration/adapters/employee/evidence/"
                    + "employee-egress-input-qualification-v2-20260814-candidate-02.result.json";

    private static final String ID_CARD_NO_CONDITION = """
            ID_CARD_NO IS NOT NULL
            AND CHAR_LENGTH(ID_CARD_NO) BETWEEN 5 AND 64
            AND OCTET_LENGTH(ID_CARD_NO) <= 192
            AND ID_CARD_NO NOT REGEXP '[[:space:]/\\\\%?#]'
            AND ID_CARD_NO NOT REGEXP '[[:cntrl:]]'
            AND HEX(ID_CARD_NO) NOT REGEXP '(E280AA|E280AB|E280AC|E280AD|E280AE|E281A6|E281A7|E281A8|E281A9)'
            """;
    private static final String CHINESE_NAME_CONDITION = """
            CHINESE_NAME IS NOT NULL
            AND CHAR_LENGTH(CHINESE_NAME) BETWEEN 1 AND 128
            AND CHINESE_NAME NOT REGEXP '[[:cntrl:]]'
            AND HEX(CHINESE_NAME) NOT REGEXP '(E280AA|E280AB|E280AC|E280AD|E280AE|E281A6|E281A7|E281A8|E281A9)'
            """;
    private static final String POSITION_CONDITION = """
            POSITION IS NOT NULL
            AND CHAR_LENGTH(POSITION) BETWEEN 1 AND 256
            AND POSITION NOT REGEXP '[[:cntrl:]]'
            AND HEX(POSITION) NOT REGEXP '(E280AA|E280AB|E280AC|E280AD|E280AE|E281A6|E281A7|E281A8|E281A9)'
            """;
    private static final String WORK_BASE_SI_CONDITION = """
            WORK_BASE_SI IS NOT NULL
            AND CHAR_LENGTH(WORK_BASE_SI) BETWEEN 1 AND 256
            AND WORK_BASE_SI NOT REGEXP '[[:cntrl:]]'
            AND HEX(WORK_BASE_SI) NOT REGEXP '(E280AA|E280AB|E280AC|E280AD|E280AE|E281A6|E281A7|E281A8|E281A9)'
            """;

    private static final String AGGREGATE_SQL = """
            SELECT
              COUNT(*) AS totalRows,
              COALESCE(SUM(CASE WHEN %s THEN 1 ELSE 0 END), 0) AS idCardNoCondition,
              COALESCE(SUM(CASE WHEN %s THEN 1 ELSE 0 END), 0) AS chineseNameCondition,
              COALESCE(SUM(CASE WHEN %s THEN 1 ELSE 0 END), 0) AS positionCondition,
              COALESCE(SUM(CASE WHEN %s THEN 1 ELSE 0 END), 0) AS workBaseSiCondition,
              COALESCE(SUM(CASE WHEN %s THEN 1 ELSE 0 END), 0) AS cumulativeIdCardNo,
              COALESCE(SUM(CASE WHEN (%s) AND (%s) THEN 1 ELSE 0 END), 0) AS cumulativeChineseName,
              COALESCE(SUM(CASE WHEN (%s) AND (%s) AND (%s) THEN 1 ELSE 0 END), 0) AS cumulativePosition,
              COALESCE(SUM(CASE WHEN (%s) AND (%s) AND (%s) AND (%s) THEN 1 ELSE 0 END), 0) AS cumulativeWorkBaseSi
            FROM employee
            """.formatted(
            ID_CARD_NO_CONDITION,
            CHINESE_NAME_CONDITION,
            POSITION_CONDITION,
            WORK_BASE_SI_CONDITION,
            ID_CARD_NO_CONDITION,
            ID_CARD_NO_CONDITION, CHINESE_NAME_CONDITION,
            ID_CARD_NO_CONDITION, CHINESE_NAME_CONDITION, POSITION_CONDITION,
            ID_CARD_NO_CONDITION, CHINESE_NAME_CONDITION, POSITION_CONDITION, WORK_BASE_SI_CONDITION);

    @Autowired
    private JdbcTemplate jdbcTemplate;
    @Autowired
    private ObjectMapper objectMapper;

    @Test
    void minimalDataContextLoadsWithoutExecutingTheAggregate() {
        assertThat(jdbcTemplate).isNotNull();
        assertThat(objectMapper).isNotNull();
    }

    @Test
    @EnabledIfEnvironmentVariable(
            named = "EXECUTE_EMPLOYEE_EGRESS_INPUT_QUALIFY_DIAG_V2_QUERY",
            matches = "1")
    void writesOneStrictAggregateCountRowWithoutReadingEmployeeValues() throws Exception {
        Path evidencePath = Path.of(required("EMPLOYEE_EGRESS_INPUT_QUALIFY_DIAG_V2_EVIDENCE"));
        assertThat(evidencePath).doesNotExist();
        Path repositoryRoot = Path.of(required("EMPLOYEE_EGRESS_INPUT_QUALIFY_DIAG_V2_REPOSITORY"));
        verifyHistory(repositoryRoot.resolve(CANDIDATE_LIFECYCLE_PATH), CANDIDATE_LIFECYCLE_SHA256);
        verifyHistory(repositoryRoot.resolve(CANDIDATE_RESULT_PATH), CANDIDATE_RESULT_SHA256);

        Map<String, Object> row = jdbcTemplate.queryForMap(AGGREGATE_SQL);
        long totalRows = count(row, "totalRows");
        long idCardNoCondition = count(row, "idCardNoCondition");
        long chineseNameCondition = count(row, "chineseNameCondition");
        long positionCondition = count(row, "positionCondition");
        long workBaseSiCondition = count(row, "workBaseSiCondition");
        long cumulativeIdCardNo = count(row, "cumulativeIdCardNo");
        long cumulativeChineseName = count(row, "cumulativeChineseName");
        long cumulativePosition = count(row, "cumulativePosition");
        long cumulativeWorkBaseSi = count(row, "cumulativeWorkBaseSi");

        assertThat(idCardNoCondition).isBetween(0L, totalRows);
        assertThat(chineseNameCondition).isBetween(0L, totalRows);
        assertThat(positionCondition).isBetween(0L, totalRows);
        assertThat(workBaseSiCondition).isBetween(0L, totalRows);
        assertThat(cumulativeIdCardNo).isEqualTo(idCardNoCondition);
        assertThat(cumulativeChineseName).isBetween(0L, cumulativeIdCardNo);
        assertThat(cumulativeChineseName).isLessThanOrEqualTo(chineseNameCondition);
        assertThat(cumulativePosition).isBetween(0L, cumulativeChineseName);
        assertThat(cumulativePosition).isLessThanOrEqualTo(positionCondition);
        assertThat(cumulativeWorkBaseSi).isBetween(0L, cumulativePosition);
        assertThat(cumulativeWorkBaseSi).isLessThanOrEqualTo(workBaseSiCondition);

        ObjectNode counts = objectMapper.createObjectNode()
                .put("totalRows", totalRows)
                .put("idCardNoCondition", idCardNoCondition)
                .put("chineseNameCondition", chineseNameCondition)
                .put("positionCondition", positionCondition)
                .put("workBaseSiCondition", workBaseSiCondition)
                .put("cumulativeIdCardNo", cumulativeIdCardNo)
                .put("cumulativeChineseName", cumulativeChineseName)
                .put("cumulativePosition", cumulativePosition)
                .put("cumulativeWorkBaseSi", cumulativeWorkBaseSi)
                .put("aggregateQueries", 1)
                .put("resultRows", 1)
                .put("employeeDetailCalls", 0)
                .put("otherEmployeeEndpointCalls", 0)
                .put("modelCalls", 0)
                .put("retryCount", 0)
                .put("resumeCount", 0);
        boolean available = cumulativeWorkBaseSi > 0;
        ObjectNode evidence = objectMapper.createObjectNode()
                .put("schemaVersion", 1)
                .put("workPackageId", "WP-EMP-EGRESS-INPUT-QUALIFY-DIAG-02")
                .put("runId", RUN_ID)
                .put("recordedAt", Instant.now().toString())
                .put("status", "completed");
        evidence.set("sourceEvidence", objectMapper.createObjectNode()
                .put("candidateRunId", CANDIDATE_RUN_ID)
                .put("candidateLifecycleSha256", CANDIDATE_LIFECYCLE_SHA256)
                .put("candidateResultSha256", CANDIDATE_RESULT_SHA256));
        evidence.set("counts", counts);
        evidence.set("diagnosis", objectMapper.createObjectNode()
                .put("reason", available ? "qualified_input_available" : "no_qualified_input")
                .put("qualifiedInputAvailable", available)
                .put("firstZeroStage", firstZeroStage(
                        totalRows,
                        cumulativeIdCardNo,
                        cumulativeChineseName,
                        cumulativePosition,
                        cumulativeWorkBaseSi)));
        evidence.set("safety", objectMapper.createObjectNode()
                .put("identifierPersisted", false)
                .put("fieldValuesPersisted", false)
                .put("rawRowsPersisted", false)
                .put("jwtRead", false)
                .put("llmApiKeyRead", false)
                .put("modelOutbound", false)
                .put("logLeakCount", 0)
                .put("rawLogsDeleted", false));

        writeAndForce(evidencePath, evidence);
    }

    private static long count(Map<String, Object> row, String key) {
        Object value = row.get(key);
        if (!(value instanceof Number number)) {
            throw new IllegalStateException("employee.egress_input_qualification_diagnostic_count_invalid");
        }
        long count = number.longValue();
        if (count < 0) {
            throw new IllegalStateException("employee.egress_input_qualification_diagnostic_count_invalid");
        }
        return count;
    }

    private static void verifyHistory(Path path, String expectedSha256) throws Exception {
        assertThat(path).isRegularFile();
        String actual = HexFormat.of().formatHex(
                MessageDigest.getInstance("SHA-256").digest(Files.readAllBytes(path)));
        assertThat(actual).isEqualTo(expectedSha256);
    }

    private static String firstZeroStage(
            long totalRows,
            long cumulativeIdCardNo,
            long cumulativeChineseName,
            long cumulativePosition,
            long cumulativeWorkBaseSi) {
        if (totalRows == 0) {
            return "total_records";
        }
        if (cumulativeIdCardNo == 0) {
            return "id_card_no";
        }
        if (cumulativeChineseName == 0) {
            return "chinese_name";
        }
        if (cumulativePosition == 0) {
            return "position";
        }
        if (cumulativeWorkBaseSi == 0) {
            return "work_base_si";
        }
        return "none";
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
            throw new IllegalStateException(
                    "employee.egress_input_qualification_diagnostic_env_missing:" + name);
        }
        return value.trim();
    }

    @SpringBootConfiguration
    @EnableAutoConfiguration
    static class DiagnosticApplication {
    }
}
