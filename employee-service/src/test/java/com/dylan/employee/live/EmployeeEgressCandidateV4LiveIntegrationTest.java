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

import com.dylan.employee.EmployeeServiceApplication;
import com.dylan.employee.event.WorkflowInboxProcessor;
import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.fasterxml.jackson.databind.node.ObjectNode;

@EnabledIfEnvironmentVariable(named = "RUN_EMPLOYEE_EGRESS_CANDIDATE_V4", matches = "1")
@SpringBootTest(classes = EmployeeServiceApplication.class,
        webEnvironment = SpringBootTest.WebEnvironment.RANDOM_PORT,
        properties = {
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
class EmployeeEgressCandidateV4LiveIntegrationTest {
    private static final int SCHEMA_VERSION = 3;
    private static final String RUN_ID = "employee-egress-v4-20260817-candidate-04";
    private static final String AUTHORIZATION_REFERENCE = "P3_00:GATE-024";
    private static final String SEED = "employee-egress-candidate-04";
    private static final String PRECHECK_SQL =
            "SELECT COUNT(*) FROM employee WHERE BINARY ID_CARD_NO = BINARY ?";
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
    void createsCallsModelAndExactlyCleansOneSyntheticEmployee() throws Exception {
        String manifestSha = required("EMPLOYEE_EGRESS_V4_MANIFEST_SHA256");
        Path lifecycle = Path.of(required("EMPLOYEE_EGRESS_V4_LIFECYCLE"));
        Path consumed = Path.of(required("EMPLOYEE_EGRESS_V4_CONSUMED"));
        Path staging = Path.of(required("EMPLOYEE_EGRESS_V4_STAGING"));
        Path pending = Path.of(required("EMPLOYEE_EGRESS_V4_PENDING"));
        Fixture fixture = fixture();
        Counts counts = new Counts();
        LifecycleWriter journal = new LifecycleWriter(lifecycle, manifestSha, objectMapper);
        String failurePhase = "none";
        String failureReason = "none";
        boolean insertStarted = false;
        JsonNode modelStaging = null;
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
                            INSERT_SQL, fixture.identifier(), fixture.chineseName(),
                            fixture.position(), fixture.workBaseSi())));
                }
                finally {
                    counts.databaseInsertTerminal++;
                }
                if (counts.inserted != 1) {
                    throw new CandidateFailure("database_operation_failed");
                }
            });
            stage(journal, "fixture_verify", () -> {
                counts.databaseSelectStarted++;
                try {
                    counts.verified = bounded(inTransaction(() -> jdbcTemplate.queryForObject(
                            VERIFY_SQL, Integer.class, fixture.identifier(), fixture.chineseName(),
                            fixture.position(), fixture.workBaseSi())));
                }
                finally {
                    counts.databaseSelectTerminal++;
                }
                if (counts.verified != 1) {
                    throw new CandidateFailure("database_operation_failed");
                }
            });

            Process process = startPython(fixture.identifier(), manifestSha, lifecycle, consumed, staging);
            boolean finished = process.waitFor(600, TimeUnit.SECONDS);
            if (!finished) {
                process.destroyForcibly();
                process.waitFor(10, TimeUnit.SECONDS);
            }
            counts.loadLifecycle(lifecycle, objectMapper);
            if (Files.isRegularFile(staging)) {
                modelStaging = objectMapper.readTree(Files.readAllBytes(staging));
                validateStaging(modelStaging, manifestSha);
                counts.assertStaging(modelStaging.path("counts"));
                if (!"none".equals(modelStaging.path("failure").path("reason").asText())) {
                    failurePhase = modelStaging.path("failure").path("phase").asText();
                    failureReason = modelStaging.path("failure").path("reason").asText();
                }
            }
            else {
                failurePhase = "host_validation";
                failureReason = "evidence_write_failed";
            }
            if (!finished || process.exitValue() != 0) {
                if ("none".equals(failureReason)) {
                    failurePhase = Files.exists(consumed) ? "model_answer" : "employee_detail";
                    failureReason = Files.exists(consumed) ? "model_call_failed" : "employee_request_failed";
                }
            }
        }
        catch (CandidateFailure failure) {
            failurePhase = currentFailurePhase(lifecycle);
            failureReason = failure.getMessage();
        }
        catch (RuntimeException failure) {
            failurePhase = currentFailurePhase(lifecycle);
            failureReason = "database_operation_failed";
        }
        finally {
            if (insertStarted) {
                try {
                    stage(journal, "cleanup_delete", () -> {
                        counts.databaseDeleteStarted++;
                        try {
                            counts.deleted = bounded(inTransaction(() -> jdbcTemplate.update(
                                    DELETE_SQL, fixture.identifier(), fixture.chineseName(),
                                    fixture.position(), fixture.workBaseSi())));
                        }
                        finally {
                            counts.databaseDeleteTerminal++;
                        }
                        if (counts.deleted != 1) {
                            throw new CandidateFailure("cleanup_failed");
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
                            throw new CandidateFailure("cleanup_failed");
                        }
                    });
                }
                catch (RuntimeException cleanupFailure) {
                    failurePhase = currentFailurePhase(lifecycle);
                    failureReason = "cleanup_failed";
                }
            }
            writePending(pending, manifestSha, failurePhase, failureReason, counts, modelStaging);
        }
        assertThat(counts.databaseSelectStarted).isLessThanOrEqualTo(3);
        assertThat(counts.databaseInsertStarted).isLessThanOrEqualTo(1);
        assertThat(counts.databaseDeleteStarted).isLessThanOrEqualTo(1);
        assertThat(counts.employeeDetailStarted).isLessThanOrEqualTo(1);
        assertThat(counts.modelAnswerStarted).isLessThanOrEqualTo(30);
    }

    private Process startPython(
            String identifier, String manifestSha, Path lifecycle, Path consumed, Path staging)
            throws Exception {
        ProcessBuilder builder = new ProcessBuilder(
                required("EMPLOYEE_EGRESS_V4_PYTHON"), "-m", "pytest",
                "tests/integration/adapters/employee/test_real_employee_egress_candidate_v4.py",
                "-q", "--tb=no");
        builder.directory(Path.of(required("EMPLOYEE_EGRESS_V4_REPOSITORY"))
                .resolve("agent-runtime").toFile());
        builder.redirectErrorStream(true);
        builder.redirectOutput(Path.of(required("EMPLOYEE_EGRESS_V4_PYTHON_LOG")).toFile());
        Map<String, String> environment = builder.environment();
        environment.put("PYTHONPATH", "src;.");
        environment.put("RUN_EMPLOYEE_EGRESS_CANDIDATE_V4", "1");
        environment.put("EMPLOYEE_EGRESS_V4_IDENTIFIER", identifier);
        environment.put("EMPLOYEE_EGRESS_V4_ADMIN_JWT", required("EMPLOYEE_EGRESS_V4_ADMIN_JWT"));
        environment.put("EMPLOYEE_EGRESS_V4_BASE_URL", "http://127.0.0.1:" + port);
        environment.put("EMPLOYEE_EGRESS_V4_MANIFEST_SHA256", manifestSha);
        environment.put("EMPLOYEE_EGRESS_V4_LIFECYCLE", lifecycle.toString());
        environment.put("EMPLOYEE_EGRESS_V4_CONSUMED", consumed.toString());
        environment.put("EMPLOYEE_EGRESS_V4_STAGING", staging.toString());
        environment.put("EMPLOYEE_EGRESS_V4_REPOSITORY", required("EMPLOYEE_EGRESS_V4_REPOSITORY"));
        return builder.start();
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

    private void validateStaging(JsonNode value, String manifestSha) {
        if (!value.isObject() || value.size() != 7
                || value.path("schemaVersion").asInt(-1) != SCHEMA_VERSION
                || !RUN_ID.equals(value.path("runId").asText())
                || !manifestSha.equals(value.path("manifestSha256").asText())
                || !AUTHORIZATION_REFERENCE.equals(value.path("authorizationReference").asText())
                || !value.path("failure").isObject() || value.path("failure").size() != 2
                || !value.path("counts").isObject() || value.path("counts").size() != 5
                || !value.path("safety").isObject() || value.path("safety").size() != 6) {
            throw new CandidateFailure("employee_result_invalid");
        }
    }

    private void writePending(
            Path path, String manifestSha, String failurePhase, String failureReason,
            Counts counts, JsonNode modelStaging) throws Exception {
        ObjectNode safety = objectMapper.createObjectNode()
                .put("retryCount", 0).put("resumeCount", 0).put("otherEndpointCalls", 0)
                .put("forbiddenPayloadFieldCount", modelValue(modelStaging, "forbiddenPayloadFieldCount"))
                .put("forbiddenLiteralCount", modelValue(modelStaging, "forbiddenLiteralCount"))
                .put("runtimeLogLeakCount", modelValue(modelStaging, "logLeakCount"));
        ObjectNode value = objectMapper.createObjectNode()
                .put("schemaVersion", SCHEMA_VERSION)
                .put("runId", RUN_ID)
                .put("manifestSha256", manifestSha)
                .put("authorizationReference", AUTHORIZATION_REFERENCE);
        value.set("failure", objectMapper.createObjectNode()
                .put("phase", failurePhase).put("reason", failureReason));
        value.set("counts", counts.toJson(objectMapper));
        value.set("safety", safety);
        writeAndForce(path, value, StandardOpenOption.CREATE_NEW, StandardOpenOption.WRITE);
    }

    private int modelValue(JsonNode staging, String key) {
        return staging == null ? 0 : staging.path("safety").path(key).asInt(0);
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

    private static String currentFailurePhase(Path lifecycle) {
        try {
            String last = Files.readAllLines(lifecycle, StandardCharsets.UTF_8).getLast();
            JsonNode value = new ObjectMapper().readTree(last);
            return value.path("phase").asText("host_validation");
        }
        catch (Exception failure) {
            return "host_validation";
        }
    }

    private static String required(String name) {
        String value = System.getenv(name);
        if (value == null || value.isBlank()) {
            throw new IllegalStateException("employee.egress_candidate_v4_env_missing:" + name);
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
        private int remaining = 1;
        private int employeeDetailStarted;
        private int employeeDetailTerminal;
        private int modelAnswerStarted;
        private int modelAnswerTerminal;
        private int validAnswers;

        private void loadLifecycle(Path lifecycle, ObjectMapper mapper) throws Exception {
            employeeDetailStarted = 0;
            employeeDetailTerminal = 0;
            modelAnswerStarted = 0;
            modelAnswerTerminal = 0;
            validAnswers = 0;
            for (String line : Files.readAllLines(lifecycle, StandardCharsets.UTF_8)) {
                JsonNode record = mapper.readTree(line);
                String phase = record.path("phase").asText();
                String state = record.path("state").asText();
                if ("employee_detail".equals(phase)) {
                    if ("started".equals(state)) {
                        employeeDetailStarted++;
                    }
                    else {
                        employeeDetailTerminal++;
                    }
                }
                else if ("model_answer".equals(phase)) {
                    if ("started".equals(state)) {
                        modelAnswerStarted++;
                    }
                    else {
                        modelAnswerTerminal++;
                        if ("answer".equals(state)) {
                            validAnswers++;
                        }
                    }
                }
            }
        }

        private void assertStaging(JsonNode value) {
            if (employeeDetailStarted != value.path("employeeDetailStarted").asInt(-1)
                    || employeeDetailTerminal != value.path("employeeDetailTerminal").asInt(-1)
                    || modelAnswerStarted != value.path("modelAnswerStarted").asInt(-1)
                    || modelAnswerTerminal != value.path("modelAnswerTerminal").asInt(-1)
                    || validAnswers != value.path("validAnswers").asInt(-1)) {
                throw new CandidateFailure("employee_result_invalid");
            }
        }

        private ObjectNode toJson(ObjectMapper mapper) {
            return mapper.createObjectNode()
                    .put("databaseSelectStarted", databaseSelectStarted)
                    .put("databaseSelectTerminal", databaseSelectTerminal)
                    .put("databaseInsertStarted", databaseInsertStarted)
                    .put("databaseInsertTerminal", databaseInsertTerminal)
                    .put("databaseDeleteStarted", databaseDeleteStarted)
                    .put("databaseDeleteTerminal", databaseDeleteTerminal)
                    .put("preexisting", preexisting).put("inserted", inserted)
                    .put("verified", verified).put("deleted", deleted).put("remaining", remaining)
                    .put("employeeDetailStarted", employeeDetailStarted)
                    .put("employeeDetailTerminal", employeeDetailTerminal)
                    .put("modelAnswerStarted", modelAnswerStarted)
                    .put("modelAnswerTerminal", modelAnswerTerminal)
                    .put("validAnswers", validAnswers);
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
            if (!Files.isRegularFile(path) || Files.readAllLines(path, StandardCharsets.UTF_8).size() != 1) {
                throw new IllegalStateException("employee.egress_candidate_v4_lifecycle_not_initialized");
            }
        }

        private void record(String phase, String state, String reason) {
            try {
                int sequence = Files.readAllLines(path, StandardCharsets.UTF_8).size();
                ObjectNode value = mapper.createObjectNode()
                        .put("schemaVersion", SCHEMA_VERSION).put("runId", RUN_ID)
                        .put("manifestSha256", manifestSha)
                        .put("authorizationReference", AUTHORIZATION_REFERENCE)
                        .put("sequence", sequence).put("phase", phase).put("state", state)
                        .put("reason", reason).put("failurePhase", "none");
                value.putNull("ordinal");
                writeAndForce(path, value, StandardOpenOption.APPEND, StandardOpenOption.WRITE);
            }
            catch (Exception failure) {
                throw new IllegalStateException("employee.egress_candidate_v4_journal_failed", failure);
            }
        }
    }
}
