package com.dylan.employee.live;

import static org.assertj.core.api.Assertions.assertThat;

import java.nio.ByteBuffer;
import java.nio.channels.FileChannel;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.StandardOpenOption;
import java.security.MessageDigest;
import java.util.HexFormat;
import java.util.Map;
import java.util.concurrent.TimeUnit;
import java.util.function.Supplier;

import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.condition.EnabledIfEnvironmentVariable;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.boot.test.web.server.LocalServerPort;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.test.context.bean.override.mockito.MockitoBean;
import org.springframework.transaction.PlatformTransactionManager;
import org.springframework.transaction.support.TransactionTemplate;

import com.dylan.employee.event.WorkflowInboxProcessor;
import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.fasterxml.jackson.databind.node.ObjectNode;

@EnabledIfEnvironmentVariable(named = "RUN_EMPLOYEE_EGRESS_INPUT_QUALIFY_V3", matches = "1")
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
class EmployeeEgressInputQualificationV3LiveIntegrationTest {
    private static final String RUN_ID =
            "employee-egress-input-qualification-v3-20260814-candidate-03";
    private static final String WORK_PACKAGE_ID = "WP-EMP-EGRESS-INPUT-QUALIFY-03";
    private static final String AUTHORIZATION_REFERENCE = "P3_00:GATE-049";
    private static final String SEED = "employee-qualification-candidate-03";
    private static final String PRECHECK_SQL = """
            SELECT COUNT(*) FROM employee WHERE BINARY ID_CARD_NO = BINARY ?
            """;
    private static final String INSERT_SQL = """
            INSERT INTO employee (ID_CARD_NO, CHINESE_NAME, POSITION, WORK_BASE_SI)
            VALUES (?, ?, ?, ?)
            """;
    private static final String VERIFY_SQL = """
            SELECT COUNT(*) FROM employee
            WHERE BINARY ID_CARD_NO = BINARY ?
              AND BINARY CHINESE_NAME = BINARY ?
              AND BINARY POSITION = BINARY ?
              AND BINARY WORK_BASE_SI = BINARY ?
            """;
    private static final String DELETE_SQL = """
            DELETE FROM employee
            WHERE BINARY ID_CARD_NO = BINARY ?
              AND BINARY CHINESE_NAME = BINARY ?
              AND BINARY POSITION = BINARY ?
              AND BINARY WORK_BASE_SI = BINARY ?
            """;

    @LocalServerPort
    private int port;
    @Autowired
    private JdbcTemplate jdbcTemplate;
    @Autowired
    private ObjectMapper objectMapper;
    @Autowired
    private PlatformTransactionManager transactionManager;
    @MockitoBean
    private WorkflowInboxProcessor workflowInboxProcessor;

    @Test
    void createsQualifiesAndExactlyCleansOneSyntheticEmployee() throws Exception {
        String manifestSha = required("EMPLOYEE_EGRESS_INPUT_QUALIFY_V3_MANIFEST_SHA256");
        Path lifecycle = Path.of(required("EMPLOYEE_EGRESS_INPUT_QUALIFY_V3_LIFECYCLE"));
        Path pending = Path.of(required("EMPLOYEE_EGRESS_INPUT_QUALIFY_V3_PENDING"));
        Path staging = Path.of(required("EMPLOYEE_EGRESS_INPUT_QUALIFY_V3_STAGING"));
        Fixture fixture = fixture();
        Counts counts = new Counts();
        Presence presence = new Presence();
        LifecycleWriter journal = new LifecycleWriter(lifecycle, manifestSha, objectMapper);
        String status = "failed";
        String reason = "none";
        boolean insertStarted = false;
        try {
            stage(journal, "fixture_precheck", () -> {
                counts.databaseSelectStarted++;
                try {
                    counts.preexisting = bounded(inTransaction(() -> jdbcTemplate.queryForObject(
                            PRECHECK_SQL, Integer.class, fixture.identifier())));
                }
                finally {
                    counts.databaseSelectTerminal++;
                }
                if (counts.preexisting != 0) {
                    throw new CandidateFailure("identifier_conflict");
                }
            });
            insertStarted = true;
            stage(journal, "fixture_insert", () -> {
                counts.databaseInsertStarted++;
                try {
                    counts.inserted = bounded(inTransaction(() -> jdbcTemplate.update(
                            INSERT_SQL,
                            fixture.identifier(), fixture.chineseName(),
                            fixture.position(), fixture.workBaseSi())));
                }
                finally {
                    counts.databaseInsertTerminal++;
                }
                if (counts.inserted != 1) {
                    throw new CandidateFailure("insert_count_invalid");
                }
            });
            stage(journal, "fixture_verify", () -> {
                counts.databaseSelectStarted++;
                try {
                    counts.verified = bounded(inTransaction(() -> jdbcTemplate.queryForObject(
                            VERIFY_SQL, Integer.class,
                            fixture.identifier(), fixture.chineseName(),
                            fixture.position(), fixture.workBaseSi())));
                }
                finally {
                    counts.databaseSelectTerminal++;
                }
                if (counts.verified != 1) {
                    throw new CandidateFailure("fingerprint_mismatch");
                }
            });

            Process process = startPythonProbe(fixture.identifier(), manifestSha, lifecycle, staging);
            boolean finished = process.waitFor(60, TimeUnit.SECONDS);
            if (!finished) {
                process.destroyForcibly();
                process.waitFor(10, TimeUnit.SECONDS);
            }
            counts.employeeDetailStarted = countEvent(lifecycle, "employee_detail", "started");
            counts.employeeDetailTerminal = countTerminalEvent(lifecycle, "employee_detail");
            if (counts.employeeDetailStarted == 1 && counts.employeeDetailTerminal == 0) {
                journal.record("employee_detail", "failed", "employee_request_failed");
                counts.employeeDetailTerminal = 1;
            }
            if (!finished || process.exitValue() != 0 || !Files.isRegularFile(staging)) {
                throw new CandidateFailure("employee_request_failed");
            }
            JsonNode value = objectMapper.readTree(Files.readAllBytes(staging));
            presence.load(value);
            if (!presence.requestSucceeded) {
                status = "failed";
                reason = "employee_request_failed";
            }
            else if (!presence.allCodec() || !presence.allRequiredUser()) {
                status = "not_qualified";
                reason = "employee_result_invalid";
            }
            else if (!presence.egressAllowed) {
                status = "not_qualified";
                reason = "egress_projection_invalid";
            }
            else {
                status = "qualified";
            }
        }
        catch (CandidateFailure failure) {
            reason = failure.getMessage();
        }
        catch (RuntimeException failure) {
            reason = "database_operation_failed";
        }
        finally {
            if (insertStarted) {
                String cleanupReason = cleanup(journal, fixture, counts);
                if (!"none".equals(cleanupReason)) {
                    status = "failed_cleanup_required";
                    reason = cleanupReason;
                }
            }
            counts.employeeDetailStarted = countEvent(lifecycle, "employee_detail", "started");
            counts.employeeDetailTerminal = countTerminalEvent(lifecycle, "employee_detail");
            writePending(pending, status, reason, presence, counts);
        }
        assertThat(counts.databaseSelectStarted).isLessThanOrEqualTo(3);
        assertThat(counts.databaseInsertStarted).isLessThanOrEqualTo(1);
        assertThat(counts.databaseDeleteStarted).isLessThanOrEqualTo(1);
    }

    private Process startPythonProbe(
            String identifier,
            String manifestSha,
            Path lifecycle,
            Path staging) throws Exception {
        ProcessBuilder builder = new ProcessBuilder(
                required("EMPLOYEE_EGRESS_INPUT_QUALIFY_V3_PYTHON"),
                "-m", "pytest",
                "tests/integration/adapters/employee/"
                        + "test_real_employee_egress_input_qualification_v3.py",
                "-q", "--tb=no");
        builder.directory(Path.of(required("EMPLOYEE_EGRESS_INPUT_QUALIFY_V3_REPOSITORY"))
                .resolve("agent-runtime").toFile());
        builder.redirectErrorStream(true);
        builder.redirectOutput(Path.of(required("EMPLOYEE_EGRESS_INPUT_QUALIFY_V3_PYTHON_LOG")).toFile());
        Map<String, String> environment = builder.environment();
        environment.remove("LLM_API_KEY");
        environment.put("PYTHONPATH", "src;.");
        environment.put("RUN_EMPLOYEE_EGRESS_INPUT_QUALIFY_V3", "1");
        environment.put("EMPLOYEE_EGRESS_INPUT_QUALIFY_V3_IDENTIFIER", identifier);
        environment.put("EMPLOYEE_EGRESS_INPUT_QUALIFY_V3_ADMIN_JWT",
                required("EMPLOYEE_EGRESS_INPUT_QUALIFY_V3_ADMIN_JWT"));
        environment.put("EMPLOYEE_EGRESS_INPUT_QUALIFY_V3_BASE_URL", "http://127.0.0.1:" + port);
        environment.put("EMPLOYEE_EGRESS_INPUT_QUALIFY_V3_MANIFEST_SHA256", manifestSha);
        environment.put("EMPLOYEE_EGRESS_INPUT_QUALIFY_V3_LIFECYCLE", lifecycle.toString());
        environment.put("EMPLOYEE_EGRESS_INPUT_QUALIFY_V3_STAGING", staging.toString());
        return builder.start();
    }

    private String cleanup(LifecycleWriter journal, Fixture fixture, Counts counts) {
        try {
            stage(journal, "cleanup_delete", () -> {
                counts.databaseDeleteStarted++;
                try {
                    counts.deleted = bounded(inTransaction(() -> jdbcTemplate.update(
                            DELETE_SQL,
                            fixture.identifier(), fixture.chineseName(),
                            fixture.position(), fixture.workBaseSi())));
                }
                finally {
                    counts.databaseDeleteTerminal++;
                }
                if (counts.deleted != 1) {
                    throw new CandidateFailure("cleanup_count_invalid");
                }
            });
            stage(journal, "cleanup_verify", () -> {
                counts.databaseSelectStarted++;
                try {
                    counts.remaining = bounded(inTransaction(() -> jdbcTemplate.queryForObject(
                            PRECHECK_SQL, Integer.class, fixture.identifier())));
                }
                finally {
                    counts.databaseSelectTerminal++;
                }
                if (counts.remaining != 0) {
                    throw new CandidateFailure("cleanup_verification_failed");
                }
            });
            return "none";
        }
        catch (CandidateFailure failure) {
            return failure.getMessage();
        }
        catch (RuntimeException failure) {
            return "database_operation_failed";
        }
    }

    private void stage(LifecycleWriter journal, String phase, StageOperation operation) {
        journal.record(phase, "started", "none");
        try {
            operation.run();
        }
        catch (CandidateFailure failure) {
            journal.record(phase, "failed", failure.getMessage());
            throw failure;
        }
        catch (RuntimeException failure) {
            journal.record(phase, "failed", "database_operation_failed");
            throw failure;
        }
        journal.record(phase, "succeeded", "none");
    }

    private void writePending(
            Path path, String status, String reason, Presence presence, Counts counts) throws Exception {
        ObjectNode value = objectMapper.createObjectNode()
                .put("schemaVersion", 3)
                .put("status", status)
                .put("reason", reason);
        value.set("fieldPresence", presence.toJson(objectMapper));
        value.set("counts", counts.toJson(objectMapper));
        writeAndForce(path, value, StandardOpenOption.CREATE_NEW, StandardOpenOption.WRITE);
    }

    private <T> T inTransaction(Supplier<T> operation) {
        return new TransactionTemplate(transactionManager).execute(status -> operation.get());
    }

    private static Fixture fixture() throws Exception {
        byte[] digest = MessageDigest.getInstance("SHA-256")
                .digest(("employee-synthetic-fixture-v1:" + SEED).getBytes(StandardCharsets.UTF_8));
        return new Fixture(
                "synthetic-employee-" + HexFormat.of().formatHex(digest).substring(0, 24),
                "Synthetic Employee", "Synthetic Position", "Synthetic Work Base");
    }

    private static int bounded(Number value) {
        if (value == null || value.intValue() < 0 || value.intValue() > 1) {
            throw new CandidateFailure("database_operation_failed");
        }
        return value.intValue();
    }

    private static int countEvent(Path path, String phase, String state) throws Exception {
        int count = 0;
        for (String line : Files.readAllLines(path, StandardCharsets.UTF_8)) {
            if (line.contains("\"phase\":\"" + phase + "\"")
                    && line.contains("\"state\":\"" + state + "\"")) {
                count++;
            }
        }
        return count;
    }

    private static int countTerminalEvent(Path path, String phase) throws Exception {
        return countEvent(path, phase, "succeeded") + countEvent(path, phase, "failed");
    }

    private static String required(String name) {
        String value = System.getenv(name);
        if (value == null || value.isBlank()) {
            throw new IllegalStateException("employee.qualification_v3_env_missing:" + name);
        }
        return value.trim();
    }

    private static void writeAndForce(Path path, JsonNode value, StandardOpenOption... options)
            throws Exception {
        byte[] bytes = (new ObjectMapper().writeValueAsString(value) + "\n")
                .getBytes(StandardCharsets.UTF_8);
        try (FileChannel channel = FileChannel.open(path, options)) {
            channel.write(ByteBuffer.wrap(bytes));
            channel.force(true);
        }
    }

    private record Fixture(String identifier, String chineseName, String position, String workBaseSi) {
    }

    @FunctionalInterface
    private interface StageOperation {
        void run();
    }

    private static final class CandidateFailure extends RuntimeException {
        private CandidateFailure(String reason) {
            super(reason);
        }
    }

    private static final class Presence {
        private boolean idCardNo;
        private boolean chineseName;
        private boolean position;
        private boolean workBaseSi;
        private boolean employeeIdMasked;
        private boolean requiredChineseName;
        private boolean egressAllowed;
        private boolean requestSucceeded;

        private void load(JsonNode value) {
            if (!value.isObject() || value.size() != 5
                    || !value.path("schemaVersion").canConvertToInt()
                    || value.path("schemaVersion").intValue() != 3
                    || !value.path("codec").isObject() || value.path("codec").size() != 4
                    || !value.path("requiredUser").isObject() || value.path("requiredUser").size() != 2
                    || !value.path("egressAllowed").isBoolean()
                    || !value.path("requestSucceeded").isBoolean()) {
                throw new CandidateFailure("employee_result_invalid");
            }
            JsonNode codec = value.path("codec");
            JsonNode required = value.path("requiredUser");
            if (!codec.path("idCardNo").isBoolean()
                    || !codec.path("chineseName").isBoolean()
                    || !codec.path("position").isBoolean()
                    || !codec.path("workBaseSi").isBoolean()
                    || !required.path("employeeIdMasked").isBoolean()
                    || !required.path("chineseName").isBoolean()) {
                throw new CandidateFailure("employee_result_invalid");
            }
            idCardNo = codec.path("idCardNo").asBoolean(false);
            chineseName = codec.path("chineseName").asBoolean(false);
            position = codec.path("position").asBoolean(false);
            workBaseSi = codec.path("workBaseSi").asBoolean(false);
            employeeIdMasked = required.path("employeeIdMasked").asBoolean(false);
            requiredChineseName = required.path("chineseName").asBoolean(false);
            egressAllowed = value.path("egressAllowed").asBoolean(false);
            requestSucceeded = value.path("requestSucceeded").asBoolean(false);
        }

        private boolean allCodec() {
            return idCardNo && chineseName && position && workBaseSi;
        }

        private boolean allRequiredUser() {
            return employeeIdMasked && requiredChineseName;
        }

        private ObjectNode toJson(ObjectMapper mapper) {
            ObjectNode root = mapper.createObjectNode();
            root.set("codec", mapper.createObjectNode()
                    .put("idCardNo", idCardNo)
                    .put("chineseName", chineseName)
                    .put("position", position)
                    .put("workBaseSi", workBaseSi));
            root.set("requiredUser", mapper.createObjectNode()
                    .put("employeeIdMasked", employeeIdMasked)
                    .put("chineseName", requiredChineseName));
            root.put("egressAllowed", egressAllowed);
            return root;
        }
    }

    private static final class Counts {
        private int databaseSelectStarted;
        private int databaseSelectTerminal;
        private int databaseInsertStarted;
        private int databaseInsertTerminal;
        private int databaseDeleteStarted;
        private int databaseDeleteTerminal;
        private int preexisting;
        private int inserted;
        private int verified;
        private int deleted;
        private int remaining;
        private int employeeDetailStarted;
        private int employeeDetailTerminal;

        private ObjectNode toJson(ObjectMapper mapper) {
            return mapper.createObjectNode()
                    .put("databaseSelectStarted", databaseSelectStarted)
                    .put("databaseSelectTerminal", databaseSelectTerminal)
                    .put("databaseInsertStarted", databaseInsertStarted)
                    .put("databaseInsertTerminal", databaseInsertTerminal)
                    .put("databaseDeleteStarted", databaseDeleteStarted)
                    .put("databaseDeleteTerminal", databaseDeleteTerminal)
                    .put("preexisting", preexisting)
                    .put("inserted", inserted)
                    .put("verified", verified)
                    .put("deleted", deleted)
                    .put("remaining", remaining)
                    .put("employeeDetailStarted", employeeDetailStarted)
                    .put("employeeDetailTerminal", employeeDetailTerminal)
                    .put("otherEmployeeEndpoints", 0)
                    .put("modelCalls", 0)
                    .put("retryCount", 0)
                    .put("resumeCount", 0);
        }
    }

    private static final class LifecycleWriter {
        private final Path path;
        private final String manifestSha;
        private final ObjectMapper mapper;

        private LifecycleWriter(Path path, String manifestSha, ObjectMapper mapper) throws Exception {
            this.path = path;
            this.manifestSha = manifestSha;
            this.mapper = mapper;
            record("run", "started", "none");
        }

        private void record(String phase, String state, String reason) {
            try {
                int sequence = Files.exists(path)
                        ? Files.readAllLines(path, StandardCharsets.UTF_8).size() + 1
                        : 1;
                ObjectNode value = mapper.createObjectNode()
                        .put("schemaVersion", 3)
                        .put("workPackageId", WORK_PACKAGE_ID)
                        .put("gateId", "GATE-049")
                        .put("runId", RUN_ID)
                        .put("manifestSha256", manifestSha)
                        .put("authorizationReference", AUTHORIZATION_REFERENCE)
                        .put("sequence", sequence)
                        .put("phase", phase)
                        .put("state", state)
                        .put("reason", reason);
                writeAndForce(
                        path,
                        value,
                        sequence == 1 ? StandardOpenOption.CREATE_NEW : StandardOpenOption.APPEND,
                        StandardOpenOption.WRITE);
            }
            catch (Exception failure) {
                throw new IllegalStateException("employee.qualification_v3_journal_failed", failure);
            }
        }
    }
}
