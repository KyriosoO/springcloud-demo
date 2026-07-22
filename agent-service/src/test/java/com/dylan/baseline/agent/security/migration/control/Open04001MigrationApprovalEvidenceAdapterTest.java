package com.dylan.baseline.agent.security.migration.control;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

import com.dylan.baseline.agent.security.policy.admin.AuthFieldPolicyPayloadValidator;
import com.dylan.baseline.agent.security.policy.admin.PolicyAdministrationException;
import com.dylan.baseline.agent.security.policy.admin.SecurityChangeApprovalEvidencePort.ApprovalVerificationRequest;
import com.dylan.common.security.Ed25519IntegritySupport;
import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.fasterxml.jackson.databind.node.ArrayNode;
import com.fasterxml.jackson.databind.node.ObjectNode;
import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.security.KeyPair;
import java.security.KeyPairGenerator;
import java.security.MessageDigest;
import java.time.Clock;
import java.time.Instant;
import java.time.ZoneOffset;
import java.util.TreeSet;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;

class Open04001MigrationApprovalEvidenceAdapterTest {

    private static final Instant NOW = Instant.parse("2026-07-22T08:00:00Z");
    private static final String CONFIG_DIGEST = "c".repeat(64);
    private static final String DATABASE_DIGEST = "d".repeat(64);
    private static final String OPERATOR = "a".repeat(64);
    private static final String APPROVER = "b".repeat(64);
    private final ObjectMapper mapper = new ObjectMapper();

    @TempDir
    Path root;

    @Test
    void verifiesSignedClosedRecordAndReturnsExactBoundApproval() throws Exception {
        Fixture fixture = fixture();

        var approval = fixture.adapter().verify(request(fixture.policyDigest()));

        assertThat(approval.approvalRef()).isEqualTo("open-04-001-control-1");
        assertThat(approval.approverRefDigest()).isEqualTo(APPROVER);
        assertThat(approval.evidenceDigest()).matches("[0-9a-f]{64}");
        assertThat(approval.validUntil()).isEqualTo(Instant.parse("2026-07-22T10:00:00Z"));
    }

    @Test
    void rejectsEnvironmentPrivilegeTimeAndActorBoundaryViolationsEvenWhenResigned() throws Exception {
        Fixture fixture = fixture();

        assertInvalid(fixture.resigned(rootNode -> rootNode.put("environmentClass", "PRODUCTION")));
        assertInvalid(fixture.resigned(rootNode -> rootNode.put("runtimeToolTrafficEnabled", true)));
        assertInvalid(fixture.resigned(rootNode -> rootNode.put("approverRefDigest", OPERATOR)));
        assertInvalid(fixture.resigned(rootNode -> rootNode.put("windowNotAfter", "2026-07-22T07:59:59Z")));
        assertInvalid(fixture.resigned(rootNode ->
                ((ObjectNode) rootNode.get("policyOperations").get(0)).put("expectedStateVersion", 3)));
    }

    @Test
    void rejectsMissingExplicitSourceBindingHashDriftAndSignatureTampering() throws Exception {
        Fixture fixture = fixture();
        assertInvalid(fixture.resigned(rootNode ->
                ((ObjectNode) rootNode.get("sourceHashes")).remove("scripts/security/controlled-observation-runner.py")));

        Files.writeString(root.resolve("profiles/traffic.json"), "drift", StandardCharsets.UTF_8);
        assertInvalid(fixture);

        Fixture fresh = fixture();
        ObjectNode tampered = fresh.record().deepCopy();
        tampered.put("signature", "A".repeat(86));
        writeRecord(tampered);
        assertInvalid(fresh);
    }

    @Test
    void rejectsUnknownFieldsDuplicateJsonKeysAndNonCanonicalPathReferences() throws Exception {
        Fixture fixture = fixture();
        assertInvalid(fixture.resigned(rootNode -> rootNode.put("unexpected", true)));
        assertInvalid(fixture.resigned(rootNode -> rootNode.put("trafficProfileRef", "../traffic.json")));
        assertInvalid(fixture.resigned(rootNode -> rootNode.put("trafficProfileRef", "profiles/../profiles/traffic.json")));
        assertInvalid(fixture.resigned(rootNode -> rootNode.put("configurationDigest", "NOT_A_DIGEST")));
        assertInvalid(fixture.resigned(rootNode -> rootNode.put(
                "observationRunnerRef", rootNode.get("consumerScannerRef").textValue())));

        String duplicate = Files.readString(fixture.recordPath(), StandardCharsets.UTF_8)
                .replaceFirst("\\{", "{\"schemaVersion\":\"duplicate\",");
        Files.writeString(fixture.recordPath(), duplicate, StandardCharsets.UTF_8);
        assertInvalid(fixture);
    }

    private void assertInvalid(Fixture fixture) {
        assertThatThrownBy(() -> fixture.adapter().verify(request(fixture.policyDigest())))
                .isInstanceOfSatisfying(PolicyAdministrationException.class,
                        ex -> assertThat(ex.code()).isEqualTo("SECURITY_POLICY_APPROVAL_INVALID"));
    }

    private Fixture fixture() throws Exception {
        Files.createDirectories(root.resolve("policy"));
        Files.createDirectories(root.resolve("profiles"));
        Files.createDirectories(root.resolve("scripts/security"));
        String policy = """
                {"fieldPolicies":{"agent-viewer":{"allowedFunctions":{},"allowedOperators":{},"displayableFields":{"employee":["email","name"]},"filterableFields":{"employee":["email","name"]}}}}
                """.strip();
        String drillPolicy = """
                {"fieldPolicies":{"agent-viewer":{"allowedFunctions":{},"allowedOperators":{},"displayableFields":{"employee":["name"]},"filterableFields":{"employee":["name"]}}}}
                """.strip();
        Path policyPath = write("policy/agent-field-policy.json", policy);
        Path drillPolicyPath = write("policy/rollback-exercise-policy.json", drillPolicy);
        Path trafficPath = write("profiles/traffic.json", "{\"profiles\":[\"agent-viewer\"]}");
        Path thresholdsPath = write("profiles/thresholds.json", "{\"minimumPerPhase\":100}");
        Path runnerPath = write("scripts/security/controlled-observation-runner.py", "runner");
        Path scannerPath = write("scripts/security/external-consumer-scanner.py", "scanner");
        Path verifierPath = write("scripts/security/exit-verifier.py", "verifier");
        String policyDigest = new AuthFieldPolicyPayloadValidator(mapper)
                .validate(AuthFieldPolicyPayloadValidator.SCHEMA_VERSION, policy).digest();
        String drillPolicyDigest = new AuthFieldPolicyPayloadValidator(mapper)
                .validate(AuthFieldPolicyPayloadValidator.SCHEMA_VERSION, drillPolicy).digest();
        KeyPair keyPair = KeyPairGenerator.getInstance("Ed25519").generateKeyPair();

        ObjectNode record = mapper.createObjectNode();
        record.put("schemaVersion", Open04001MigrationApprovalEvidenceAdapter.SCHEMA_VERSION);
        record.put("recordId", "open-04-001-control-1");
        record.put("environmentClass", "NON_PRODUCTION_CONTROLLED");
        record.put("repositoryRevision", "revision-1");
        record.put("configurationDigest", CONFIG_DIGEST);
        record.put("databaseRefDigest", DATABASE_DIGEST);
        record.put("policyVersion", "policy-v1");
        record.put("policyPayloadRef", relative(policyPath));
        record.put("policyDigest", policyDigest);
        record.put("policySchemaVersion", AuthFieldPolicyPayloadValidator.SCHEMA_VERSION);
        record.put("rollbackExercisePolicyVersion", "policy-v1-rollback-drill");
        record.put("rollbackExercisePolicyPayloadRef", relative(drillPolicyPath));
        record.put("rollbackExercisePolicyDigest", drillPolicyDigest);
        record.put("rollbackExercisePolicySchemaVersion", AuthFieldPolicyPayloadValidator.SCHEMA_VERSION);
        record.put("trafficProfileRef", relative(trafficPath));
        record.put("trafficProfileDigest", sha256(trafficPath));
        record.put("thresholdsRef", relative(thresholdsPath));
        record.put("thresholdsDigest", sha256(thresholdsPath));
        record.put("observationRunnerRef", relative(runnerPath));
        record.put("consumerScannerRef", relative(scannerPath));
        record.put("exitVerifierRef", relative(verifierPath));
        record.putArray("phaseSequence")
                .add("DUAL_READ_ENFORCE_INTERSECTION")
                .add("AGENT_FIELD_AUTHORITY");
        ArrayNode operations = record.putArray("policyOperations");
        ObjectNode operation = operations.addObject();
        operation.put("operation", "CREATE_AND_ACTIVATE");
        operation.putNull("fromPolicyDigest");
        operation.put("toPolicyDigest", policyDigest);
        operation.put("changeClass", "INITIAL");
        operation.put("expectedStateVersion", 0);
        ObjectNode tightening = operations.addObject();
        tightening.put("operation", "CREATE_AND_ACTIVATE");
        tightening.put("fromPolicyDigest", policyDigest);
        tightening.put("toPolicyDigest", drillPolicyDigest);
        tightening.put("changeClass", "TIGHTENING");
        tightening.put("expectedStateVersion", 1);
        ObjectNode rollback = operations.addObject();
        rollback.put("operation", "ROLLBACK");
        rollback.put("fromPolicyDigest", drillPolicyDigest);
        rollback.put("toPolicyDigest", policyDigest);
        rollback.put("changeClass", "EXPANSION");
        rollback.put("expectedStateVersion", 2);
        record.putArray("enabledModelTargetIds");
        record.put("runtimeToolTrafficEnabled", false);
        record.put("businessTrafficEnabled", false);
        record.put("operatorRefDigest", OPERATOR);
        record.put("approverRefDigest", APPROVER);
        record.putObject("verificationKey").put("keyId", "reviewer-1").put("keyVersion", "v1");
        record.put("issuedAt", "2026-07-22T07:00:00Z");
        record.put("windowNotBefore", "2026-07-22T07:30:00Z");
        record.put("windowNotAfter", "2026-07-22T09:00:00Z");
        record.put("validUntil", "2026-07-22T10:00:00Z");
        ObjectNode hashes = record.putObject("sourceHashes");
        for (Path source : new Path[]{
                policyPath, drillPolicyPath, trafficPath, thresholdsPath, runnerPath, scannerPath, verifierPath}) {
            hashes.put(relative(source), sha256(source));
        }
        sign(record, keyPair);
        Path recordPath = writeRecord(record);
        return new Fixture(recordPath, record, keyPair, policyDigest);
    }

    private ApprovalVerificationRequest request(String policyDigest) {
        return new ApprovalVerificationRequest(
                "open-04-001-control-1", "CREATE_AND_ACTIVATE", null, policyDigest,
                "INITIAL", 0, OPERATOR);
    }

    private Path write(String relative, String value) throws IOException {
        Path path = root.resolve(relative);
        Files.createDirectories(path.getParent());
        Files.writeString(path, value, StandardCharsets.UTF_8);
        return path;
    }

    private Path writeRecord(ObjectNode record) throws IOException {
        Path path = root.resolve("control-record.json");
        mapper.writeValue(path.toFile(), record);
        return path;
    }

    private void sign(ObjectNode record, KeyPair keyPair) throws Exception {
        record.remove("signature");
        record.put("signature", Ed25519IntegritySupport.signBase64Url(
                mapper.writeValueAsBytes(canonical(record)), keyPair.getPrivate()));
    }

    private JsonNode canonical(JsonNode node) {
        if (node.isObject()) {
            ObjectNode result = mapper.createObjectNode();
            TreeSet<String> names = new TreeSet<>();
            node.fieldNames().forEachRemaining(names::add);
            names.forEach(name -> result.set(name, canonical(node.get(name))));
            return result;
        }
        if (node.isArray()) {
            ArrayNode result = mapper.createArrayNode();
            node.forEach(item -> result.add(canonical(item)));
            return result;
        }
        return node.deepCopy();
    }

    private String relative(Path path) {
        return root.relativize(path).toString().replace('\\', '/');
    }

    private static String sha256(Path path) throws Exception {
        return java.util.HexFormat.of().formatHex(
                MessageDigest.getInstance("SHA-256").digest(Files.readAllBytes(path)));
    }

    private final class Fixture {
        private final Path recordPath;
        private final ObjectNode record;
        private final KeyPair keyPair;
        private final String policyDigest;

        private Fixture(Path recordPath, ObjectNode record, KeyPair keyPair, String policyDigest) {
            this.recordPath = recordPath;
            this.record = record;
            this.keyPair = keyPair;
            this.policyDigest = policyDigest;
        }

        Open04001MigrationApprovalEvidenceAdapter adapter() {
            return new Open04001MigrationApprovalEvidenceAdapter(
                    root, recordPath, "revision-1", CONFIG_DIGEST, DATABASE_DIGEST, APPROVER,
                    keyRef -> keyPair.getPublic(), new AuthFieldPolicyPayloadValidator(mapper), mapper,
                    Clock.fixed(NOW, ZoneOffset.UTC));
        }

        Fixture resigned(java.util.function.Consumer<ObjectNode> mutation) throws Exception {
            ObjectNode copy = record.deepCopy();
            mutation.accept(copy);
            sign(copy, keyPair);
            writeRecord(copy);
            return new Fixture(recordPath, copy, keyPair, policyDigest);
        }

        Path recordPath() {
            return recordPath;
        }

        ObjectNode record() {
            return record;
        }

        String policyDigest() {
            return policyDigest;
        }
    }
}
