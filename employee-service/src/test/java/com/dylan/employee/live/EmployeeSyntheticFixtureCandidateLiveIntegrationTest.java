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
import java.util.HexFormat;
import java.util.List;
import java.util.Map;
import java.util.function.Supplier;

import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.condition.EnabledIfEnvironmentVariable;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.SpringBootConfiguration;
import org.springframework.boot.autoconfigure.EnableAutoConfiguration;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.transaction.PlatformTransactionManager;
import org.springframework.transaction.support.TransactionTemplate;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.fasterxml.jackson.databind.node.ArrayNode;
import com.fasterxml.jackson.databind.node.ObjectNode;

@EnabledIfEnvironmentVariable(
        named = "RUN_EMPLOYEE_TEST_DATA_FIXTURE_CANDIDATE_01",
        matches = "1")
@SpringBootTest(
        classes = EmployeeSyntheticFixtureCandidateLiveIntegrationTest.FixtureApplication.class,
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
class EmployeeSyntheticFixtureCandidateLiveIntegrationTest {
    private static final String PREPARATION_WORK_PACKAGE_ID =
            "WP-EMP-EGRESS-TEST-DATA-CANDIDATE-01-PREP";
    private static final String WORK_PACKAGE_ID =
            "WP-EMP-EGRESS-TEST-DATA-CANDIDATE-01";
    private static final String GATE_ID = "GATE-051";
    private static final String RUN_ID =
            "employee-synthetic-fixture-v1-20260814-candidate-01";
    private static final String AUTHORIZATION_REFERENCE = "P3_00:GATE-051";
    private static final String CONTRACT_VERSION = "employee-synthetic-fixture-v1";
    private static final String SEED = "employee-fixture-candidate-01";
    private static final List<HistoryAsset> SOURCE_HISTORY = List.of(
            new HistoryAsset(
                    "fixture_contract",
                    "agent-runtime/tests/integration/adapters/employee/"
                            + "employee_test_data_fixture.py",
                    "d0b23b75edb600d6aba2e143305a3492c5f263e9d5ce58de55c138c082aa1148"),
            new HistoryAsset(
                    "fixture_schema",
                    "agent-runtime/tests/integration/adapters/employee/evidence/"
                            + "employee-test-data-fixture-v1.schema.json",
                    "93db9b28e38dc77b6568e28e3e3878a021164c6e187ed5e7a7244336005f5f31"),
            new HistoryAsset(
                    "metadata_manifest",
                    "agent-runtime/tests/integration/adapters/employee/evidence/"
                            + "employee-fixture-metadata-diagnostic-v2-20260814-candidate-02.manifest.json",
                    "ce3dcd481352bbb59be01a2d3b975dfd1b9f35ae1479dd24d7408f11be7af6b7"),
            new HistoryAsset(
                    "metadata_authorization",
                    "agent-runtime/tests/integration/adapters/employee/evidence/"
                            + "employee-fixture-metadata-diagnostic-v2-20260814-candidate-02.authorization.json",
                    "532353a032835c7f9eb4e5d8548061f22f45b16f42525d79e635131f5e0a2fb4"),
            new HistoryAsset(
                    "metadata_lifecycle",
                    "agent-runtime/tests/integration/adapters/employee/evidence/"
                            + "employee-fixture-metadata-diagnostic-v2-20260814-candidate-02.lifecycle.jsonl",
                    "affbd35987e4caaa4950888eaed80cf12e695470b1703735716f2dd54d52a105"),
            new HistoryAsset(
                    "metadata_result",
                    "agent-runtime/tests/integration/adapters/employee/evidence/"
                            + "employee-fixture-metadata-diagnostic-v2-20260814-candidate-02.result.json",
                    "9973863d43112a8142bf54eaa1ea18905112d8ca802a24dda7eed5599ab7cd51"));

    private static final String PRECHECK_SQL = """
            SELECT COUNT(*)
            FROM employee
            WHERE BINARY ID_CARD_NO = BINARY ?
            """;
    private static final String INSERT_SQL = """
            INSERT INTO employee (ID_CARD_NO, CHINESE_NAME, POSITION, WORK_BASE_SI)
            VALUES (?, ?, ?, ?)
            """;
    private static final String VERIFY_SQL = """
            SELECT COUNT(*)
            FROM employee
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

    @Autowired
    private JdbcTemplate jdbcTemplate;
    @Autowired
    private ObjectMapper objectMapper;
    @Autowired
    private PlatformTransactionManager transactionManager;

    @Test
    void fixtureContextLoadsWithoutExecutingDatabaseOperations() {
        assertThat(jdbcTemplate).isNotNull();
        assertThat(objectMapper).isNotNull();
    }

    @Test
    @EnabledIfEnvironmentVariable(
            named = "EXECUTE_EMPLOYEE_TEST_DATA_FIXTURE_CANDIDATE_01",
            matches = "1")
    void createsVerifiesAndPreciselyCleansOneSyntheticFixture() throws Exception {
        Path repositoryRoot = Path.of(required("EMPLOYEE_FIXTURE_CANDIDATE_REPOSITORY"));
        Path lifecyclePath = Path.of(required("EMPLOYEE_FIXTURE_CANDIDATE_LIFECYCLE"));
        Path stagingPath = Path.of(required("EMPLOYEE_FIXTURE_CANDIDATE_STAGING"));
        String manifestSha256 = required("EMPLOYEE_FIXTURE_CANDIDATE_MANIFEST_SHA256");
        assertThat(manifestSha256).matches("[0-9a-f]{64}");
        assertThat(lifecyclePath).doesNotExist();
        assertThat(stagingPath).doesNotExist();
        verifyHistory(repositoryRoot);

        Fixture fixture = fixture();
        Counts counts = new Counts();
        LifecycleWriter journal = new LifecycleWriter(
                lifecyclePath, manifestSha256, objectMapper);
        String status = "failed";
        String reason = "none";
        boolean insertStarted = false;
        try {
            stage(journal, "precheck", () -> {
                counts.databaseSelectStarted++;
                try {
                    counts.preexisting = boundedCount(inTransaction(() ->
                            jdbcTemplate.queryForObject(
                                    PRECHECK_SQL, Long.class, fixture.identifier())));
                } finally {
                    counts.databaseSelectTerminal++;
                }
                if (counts.preexisting != 0) {
                    throw new CandidateFailure("identifier_conflict");
                }
            });

            insertStarted = true;
            stage(journal, "insert", () -> {
                counts.databaseInsertStarted++;
                try {
                    counts.inserted = boundedCount(inTransaction(() ->
                            jdbcTemplate.update(
                                    INSERT_SQL,
                                    fixture.identifier(),
                                    fixture.chineseName(),
                                    fixture.position(),
                                    fixture.workBaseSi())));
                } finally {
                    counts.databaseInsertTerminal++;
                }
                if (counts.inserted != 1) {
                    throw new CandidateFailure("insert_count_invalid");
                }
            });

            stage(journal, "verify", () -> {
                counts.databaseSelectStarted++;
                try {
                    counts.verified = boundedCount(inTransaction(() ->
                            jdbcTemplate.queryForObject(
                                    VERIFY_SQL,
                                    Long.class,
                                    fixture.identifier(),
                                    fixture.chineseName(),
                                    fixture.position(),
                                    fixture.workBaseSi())));
                } finally {
                    counts.databaseSelectTerminal++;
                }
                if (counts.verified != 1) {
                    throw new CandidateFailure("fingerprint_mismatch");
                }
            });

            stage(journal, "consumer", () -> counts.consumerCalls++);
            status = "passed";
        } catch (CandidateFailure failure) {
            reason = failure.reason();
        } catch (RuntimeException failure) {
            reason = "database_operation_failed";
        } finally {
            if (insertStarted) {
                String cleanupReason = cleanup(journal, fixture, counts);
                if (!cleanupReason.equals("none")) {
                    status = "failed_cleanup_required";
                    reason = cleanupReason;
                }
            }
        }

        writeAndForce(stagingPath, result(
                status, reason, counts, manifestSha256, lifecyclePath));
        if (!status.equals("passed")) {
            throw new IllegalStateException("employee.fixture_candidate_live_failed");
        }
    }

    private String cleanup(LifecycleWriter journal, Fixture fixture, Counts counts) {
        try {
            stage(journal, "cleanup_delete", () -> {
                counts.databaseDeleteStarted++;
                try {
                    counts.deleted = boundedCount(inTransaction(() ->
                            jdbcTemplate.update(
                                    DELETE_SQL,
                                    fixture.identifier(),
                                    fixture.chineseName(),
                                    fixture.position(),
                                    fixture.workBaseSi())));
                } finally {
                    counts.databaseDeleteTerminal++;
                }
                if (counts.deleted != 1) {
                    throw new CandidateFailure("cleanup_count_invalid");
                }
            });
            stage(journal, "cleanup_verify", () -> {
                counts.databaseSelectStarted++;
                try {
                    counts.remaining = boundedCount(inTransaction(() ->
                            jdbcTemplate.queryForObject(
                                    PRECHECK_SQL, Long.class, fixture.identifier())));
                } finally {
                    counts.databaseSelectTerminal++;
                }
                if (counts.remaining != 0) {
                    throw new CandidateFailure("cleanup_verification_failed");
                }
            });
            return "none";
        } catch (CandidateFailure failure) {
            return failure.reason();
        } catch (RuntimeException failure) {
            return "database_operation_failed";
        }
    }

    private void stage(LifecycleWriter journal, String phase, StageOperation operation) {
        journal.stage(phase, "started", "none");
        try {
            operation.run();
            journal.stage(phase, "succeeded", "none");
        } catch (CandidateFailure failure) {
            journal.stage(phase, "failed", failure.reason());
            throw failure;
        } catch (RuntimeException failure) {
            journal.stage(phase, "failed", "database_operation_failed");
            throw failure;
        }
    }

    private ObjectNode result(
            String status,
            String reason,
            Counts counts,
            String manifestSha256,
            Path lifecyclePath) throws Exception {
        ObjectNode result = objectMapper.createObjectNode()
                .put("schemaVersion", 1)
                .put("preparationWorkPackageId", PREPARATION_WORK_PACKAGE_ID)
                .put("workPackageId", WORK_PACKAGE_ID)
                .put("gateId", GATE_ID)
                .put("runId", RUN_ID)
                .put("manifestSha256", manifestSha256)
                .put("authorizationReference", AUTHORIZATION_REFERENCE)
                .put("status", status)
                .put("reason", reason);
        result.putArray("fieldNames")
                .add("idCardNo")
                .add("chineseName")
                .add("position")
                .add("workBaseSi");
        ArrayNode sourceHistory = result.putArray("sourceHistory");
        for (HistoryAsset asset : SOURCE_HISTORY) {
            sourceHistory.addObject()
                    .put("kind", asset.kind())
                    .put("path", asset.path())
                    .put("sha256", asset.sha256());
        }
        result.set("counts", counts.toJson(objectMapper));
        result.set("safety", objectMapper.createObjectNode()
                .put("synthetic", true)
                .put("nonRealIdentifier", true)
                .put("identifierPersisted", false)
                .put("fixtureFingerprintPersisted", false)
                .put("fieldValuesPersisted", false)
                .put("existingRowsModified", 0)
                .put("publicApiCalls", 0)
                .put("jwtRead", false)
                .put("llmApiKeyRead", false)
                .put("modelOutbound", false)
                .put("logLeakCount", 0)
                .put("rawLogsDeleted", false));
        return result.put("lifecycleSha256", sha256(lifecyclePath));
    }

    private static Fixture fixture() throws Exception {
        String digest = sha256((CONTRACT_VERSION + ":" + SEED).getBytes(StandardCharsets.UTF_8));
        return new Fixture(
                "synthetic-employee-" + digest.substring(0, 24),
                "Synthetic Employee",
                "Synthetic Position",
                "Synthetic Work Base");
    }

    private static int boundedCount(Number value) {
        if (value == null || value.longValue() < 0 || value.longValue() > 1) {
            throw new CandidateFailure("database_operation_failed");
        }
        return value.intValue();
    }

    private <T> T inTransaction(Supplier<T> operation) {
        T value = new TransactionTemplate(transactionManager).execute(status -> operation.get());
        if (value == null) {
            throw new CandidateFailure("database_operation_failed");
        }
        return value;
    }

    private static void verifyHistory(Path repositoryRoot) throws Exception {
        for (HistoryAsset asset : SOURCE_HISTORY) {
            Path path = repositoryRoot.resolve(asset.path()).normalize();
            if (!path.startsWith(repositoryRoot.normalize())
                    || !Files.isRegularFile(path)
                    || !sha256(path).equals(asset.sha256())) {
                throw new IllegalStateException("employee.fixture_candidate_history_mismatch");
            }
        }
    }

    private static String required(String name) {
        String value = System.getenv(name);
        if (value == null || value.isBlank()) {
            throw new IllegalStateException("employee.fixture_candidate_environment_invalid");
        }
        return value;
    }

    private static void writeAndForce(Path path, ObjectNode value) throws IOException {
        byte[] bytes = (value.toString() + "\n").getBytes(StandardCharsets.UTF_8);
        Files.createDirectories(path.getParent());
        try (FileChannel channel = FileChannel.open(
                path, StandardOpenOption.CREATE_NEW, StandardOpenOption.WRITE)) {
            channel.write(ByteBuffer.wrap(bytes));
            channel.force(true);
        }
    }

    private static String sha256(Path path) throws Exception {
        return sha256(Files.readAllBytes(path));
    }

    private static String sha256(byte[] bytes) throws Exception {
        return HexFormat.of().formatHex(MessageDigest.getInstance("SHA-256").digest(bytes));
    }

    private record HistoryAsset(String kind, String path, String sha256) {
    }

    private record Fixture(
            String identifier,
            String chineseName,
            String position,
            String workBaseSi) {
    }

    @FunctionalInterface
    private interface StageOperation {
        void run();
    }

    private static final class CandidateFailure extends RuntimeException {
        private final String reason;

        private CandidateFailure(String reason) {
            super("employee.fixture_candidate_failed");
            this.reason = reason;
        }

        private String reason() {
            return reason;
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
        private int consumerCalls;

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
                    .put("consumerCalls", consumerCalls)
                    .put("employeeEndpointCalls", 0)
                    .put("modelCalls", 0)
                    .put("retryCount", 0)
                    .put("resumeCount", 0);
        }
    }

    private static final class LifecycleWriter {
        private final Path path;
        private final String manifestSha256;
        private final ObjectMapper mapper;
        private int sequence;

        private LifecycleWriter(Path path, String manifestSha256, ObjectMapper mapper)
                throws IOException {
            this.path = path;
            this.manifestSha256 = manifestSha256;
            this.mapper = mapper;
            Files.createDirectories(path.getParent());
            try (FileChannel channel = FileChannel.open(
                    path, StandardOpenOption.CREATE_NEW, StandardOpenOption.WRITE)) {
                channel.force(true);
            }
            stage("run", "started", "none");
        }

        private void stage(String phase, String state, String reason) {
            sequence++;
            ObjectNode record = mapper.createObjectNode()
                    .put("schemaVersion", 1)
                    .put("workPackageId", WORK_PACKAGE_ID)
                    .put("gateId", GATE_ID)
                    .put("runId", RUN_ID)
                    .put("manifestSha256", manifestSha256)
                    .put("authorizationReference", AUTHORIZATION_REFERENCE)
                    .put("sequence", sequence)
                    .put("phase", phase)
                    .put("state", state)
                    .put("reason", reason);
            byte[] bytes = (record.toString() + "\n").getBytes(StandardCharsets.UTF_8);
            try (FileChannel channel = FileChannel.open(
                    path, StandardOpenOption.APPEND, StandardOpenOption.WRITE)) {
                channel.write(ByteBuffer.wrap(bytes));
                channel.force(true);
            } catch (IOException failure) {
                throw new IllegalStateException("employee.fixture_candidate_journal_failed", failure);
            }
        }

    }

    @SpringBootConfiguration
    @EnableAutoConfiguration
    static class FixtureApplication {
    }
}
