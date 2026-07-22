package com.dylan.baseline.agent.security.migration.control;

import com.dylan.baseline.agent.security.policy.admin.AuthFieldPolicyPayloadValidator;
import com.dylan.baseline.agent.security.policy.admin.PolicyAdministrationException;
import com.dylan.baseline.agent.security.policy.admin.SecurityChangeApprovalEvidencePort;
import com.dylan.common.security.Ed25519IntegritySupport;
import com.dylan.common.security.IntegrityKeyRef;
import com.dylan.common.security.IntegrityVerificationKeyProvider;
import com.fasterxml.jackson.core.JsonParser;
import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.fasterxml.jackson.databind.node.ArrayNode;
import com.fasterxml.jackson.databind.node.ObjectNode;
import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.security.MessageDigest;
import java.security.NoSuchAlgorithmException;
import java.time.Clock;
import java.time.Instant;
import java.time.format.DateTimeParseException;
import java.util.ArrayList;
import java.util.HashSet;
import java.util.Iterator;
import java.util.List;
import java.util.Objects;
import java.util.Set;
import java.util.TreeSet;
import java.util.regex.Pattern;

/** DR-04-045受控非生产迁移批准适配器；不得装配到普通或生产profile。 */
public final class Open04001MigrationApprovalEvidenceAdapter
        implements SecurityChangeApprovalEvidencePort {

    public static final String SCHEMA_VERSION = "open-04-001-migration-control-v0.1";
    private static final String ENVIRONMENT_CLASS = "NON_PRODUCTION_CONTROLLED";
    private static final int MAX_RECORD_BYTES = 1_048_576;
    private static final Pattern DIGEST = Pattern.compile("[0-9a-f]{64}");
    private static final Pattern ID = Pattern.compile("[A-Za-z0-9._:-]{1,128}");
    private static final Set<String> ROOT_FIELDS = Set.of(
            "schemaVersion", "recordId", "environmentClass", "repositoryRevision",
            "configurationDigest", "databaseRefDigest", "policyVersion", "policyPayloadRef",
            "policyDigest", "policySchemaVersion", "rollbackExercisePolicyVersion",
            "rollbackExercisePolicyPayloadRef", "rollbackExercisePolicyDigest",
            "rollbackExercisePolicySchemaVersion", "trafficProfileRef", "trafficProfileDigest",
            "thresholdsRef", "thresholdsDigest", "observationRunnerRef", "consumerScannerRef",
            "exitVerifierRef", "phaseSequence", "policyOperations", "enabledModelTargetIds",
            "runtimeToolTrafficEnabled", "businessTrafficEnabled", "operatorRefDigest",
            "approverRefDigest", "verificationKey", "issuedAt", "windowNotBefore",
            "windowNotAfter", "validUntil", "sourceHashes", "signature");
    private static final Set<String> OPERATION_FIELDS = Set.of(
            "operation", "fromPolicyDigest", "toPolicyDigest", "changeClass", "expectedStateVersion");

    private final Path repositoryRoot;
    private final Path controlRecordPath;
    private final String expectedRepositoryRevision;
    private final String expectedConfigurationDigest;
    private final String expectedDatabaseRefDigest;
    private final String expectedApproverRefDigest;
    private final IntegrityVerificationKeyProvider verificationKeyProvider;
    private final AuthFieldPolicyPayloadValidator policyPayloadValidator;
    private final ObjectMapper objectMapper;
    private final Clock clock;

    public Open04001MigrationApprovalEvidenceAdapter(
            Path repositoryRoot,
            Path controlRecordPath,
            String expectedRepositoryRevision,
            String expectedConfigurationDigest,
            String expectedDatabaseRefDigest,
            String expectedApproverRefDigest,
            IntegrityVerificationKeyProvider verificationKeyProvider,
            AuthFieldPolicyPayloadValidator policyPayloadValidator,
            ObjectMapper objectMapper,
            Clock clock) {
        this.repositoryRoot = Objects.requireNonNull(repositoryRoot, "repositoryRoot").toAbsolutePath().normalize();
        this.controlRecordPath = resolveInsideRepository(controlRecordPath, "controlRecordPath");
        this.expectedRepositoryRevision = requireText(expectedRepositoryRevision, "expectedRepositoryRevision");
        this.expectedConfigurationDigest = requireDigest(expectedConfigurationDigest, "expectedConfigurationDigest");
        this.expectedDatabaseRefDigest = requireDigest(expectedDatabaseRefDigest, "expectedDatabaseRefDigest");
        this.expectedApproverRefDigest = requireDigest(expectedApproverRefDigest, "expectedApproverRefDigest");
        this.verificationKeyProvider = Objects.requireNonNull(verificationKeyProvider, "verificationKeyProvider");
        this.policyPayloadValidator = Objects.requireNonNull(policyPayloadValidator, "policyPayloadValidator");
        this.objectMapper = Objects.requireNonNull(objectMapper, "objectMapper").copy()
                .enable(JsonParser.Feature.STRICT_DUPLICATE_DETECTION);
        this.clock = Objects.requireNonNull(clock, "clock");
    }

    @Override
    public VerifiedApprovalEvidence verify(ApprovalVerificationRequest request) {
        Objects.requireNonNull(request, "request");
        JsonNode root = readRecord();
        requireObject(root, "record");
        requireExactFields(root, ROOT_FIELDS, "record");

        requireEquals(SCHEMA_VERSION, text(root, "schemaVersion"), "schemaVersion");
        String recordId = requireId(text(root, "recordId"), "recordId");
        requireEquals(request.approvalRef(), recordId, "recordId");
        requireEquals(ENVIRONMENT_CLASS, text(root, "environmentClass"), "environmentClass");
        requireEquals(expectedRepositoryRevision, text(root, "repositoryRevision"), "repositoryRevision");
        requireEquals(expectedConfigurationDigest, digest(root, "configurationDigest"), "configurationDigest");
        requireEquals(expectedDatabaseRefDigest, digest(root, "databaseRefDigest"), "databaseRefDigest");

        String operator = digest(root, "operatorRefDigest");
        String approver = digest(root, "approverRefDigest");
        requireEquals(request.actorRefDigest(), operator, "operatorRefDigest");
        requireEquals(expectedApproverRefDigest, approver, "approverRefDigest");
        if (operator.equals(approver)) {
            throw invalid("operator and approver must be independent");
        }

        requireEmptyArray(root.get("enabledModelTargetIds"), "enabledModelTargetIds");
        requireFalse(root.get("runtimeToolTrafficEnabled"), "runtimeToolTrafficEnabled");
        requireFalse(root.get("businessTrafficEnabled"), "businessTrafficEnabled");
        requirePhaseSequence(root.get("phaseSequence"));

        Instant issuedAt = instant(root, "issuedAt");
        Instant windowNotBefore = instant(root, "windowNotBefore");
        Instant windowNotAfter = instant(root, "windowNotAfter");
        Instant validUntil = instant(root, "validUntil");
        if (issuedAt.isAfter(windowNotBefore)
                || !windowNotBefore.isBefore(windowNotAfter)
                || windowNotAfter.isAfter(validUntil)) {
            throw invalid("control-record time ordering is invalid");
        }
        Instant now = clock.instant();
        if (now.isBefore(windowNotBefore) || !now.isBefore(windowNotAfter) || !now.isBefore(validUntil)) {
            throw invalid("control record is outside its execution window or expired");
        }

        JsonNode sourceHashes = root.get("sourceHashes");
        requireObject(sourceHashes, "sourceHashes");
        Set<String> requiredRefs;
        try {
            requiredRefs = Set.of(
                    safeRef(root, "policyPayloadRef"), safeRef(root, "rollbackExercisePolicyPayloadRef"),
                    safeRef(root, "trafficProfileRef"),
                    safeRef(root, "thresholdsRef"), safeRef(root, "observationRunnerRef"),
                    safeRef(root, "consumerScannerRef"), safeRef(root, "exitVerifierRef"));
        } catch (IllegalArgumentException ex) {
            throw new PolicyAdministrationException(
                    "SECURITY_POLICY_APPROVAL_INVALID", "explicit source references must be distinct", ex);
        }
        verifySourceHashes(sourceHashes, requiredRefs);
        requireEquals(digest(root, "trafficProfileDigest"), digest(sourceHashes, text(root, "trafficProfileRef")),
                "trafficProfileDigest");
        requireEquals(digest(root, "thresholdsDigest"), digest(sourceHashes, text(root, "thresholdsRef")),
                "thresholdsDigest");

        String primaryVersion = requireText(text(root, "policyVersion"), "policyVersion");
        String primaryDigest = validatePolicy(
                root, "policyPayloadRef", "policySchemaVersion", "policyDigest");
        String drillVersion = requireText(
                text(root, "rollbackExercisePolicyVersion"), "rollbackExercisePolicyVersion");
        String drillDigest = validatePolicy(
                root, "rollbackExercisePolicyPayloadRef", "rollbackExercisePolicySchemaVersion",
                "rollbackExercisePolicyDigest");
        if (primaryVersion.equals(drillVersion) || primaryDigest.equals(drillDigest)) {
            throw invalid("primary and rollback-exercise policies must be distinct");
        }
        requireBoundOperation(root.get("policyOperations"), request, primaryDigest, drillDigest);
        IntegrityKeyRef keyRef = verificationKeyRef(root.get("verificationKey"));
        String signature = text(root, "signature");
        byte[] signedBytes = canonicalWithoutSignature(root);
        java.security.PublicKey publicKey;
        try {
            publicKey = verificationKeyProvider.requireEd25519PublicKey(keyRef);
        } catch (RuntimeException ex) {
            throw new PolicyAdministrationException(
                    "SECURITY_POLICY_APPROVAL_INVALID", "verification key is unavailable", ex);
        }
        if (!Ed25519IntegritySupport.verifyBase64Url(signedBytes, signature, publicKey)) {
            throw invalid("control-record signature is invalid");
        }

        return new VerifiedApprovalEvidence(
                recordId, sha256(canonical(root)), request.operation(), request.fromPolicyDigest(),
                request.toPolicyDigest(), request.changeClass(), request.expectedStateVersion(), approver, validUntil);
    }

    private JsonNode readRecord() {
        try {
            long size = Files.size(controlRecordPath);
            if (size <= 0 || size > MAX_RECORD_BYTES) {
                throw invalid("control record is empty or exceeds 1048576 bytes");
            }
            return objectMapper.readTree(Files.readAllBytes(controlRecordPath));
        } catch (IOException ex) {
            throw new PolicyAdministrationException(
                    "SECURITY_POLICY_APPROVAL_INVALID", "cannot read controlled migration approval", ex);
        }
    }

    private void verifySourceHashes(JsonNode hashes, Set<String> requiredRefs) {
        Set<String> actual = new HashSet<>();
        hashes.fieldNames().forEachRemaining(actual::add);
        if (!actual.containsAll(requiredRefs)) {
            throw invalid("sourceHashes must bind all explicit source references");
        }
        for (String ref : actual) {
            Path source = resolveRef(ref);
            String expected = digest(hashes, ref);
            try {
                String actualDigest = sha256(Files.readAllBytes(source));
                requireEquals(expected, actualDigest, "sourceHashes." + ref);
            } catch (IOException ex) {
                throw new PolicyAdministrationException(
                        "SECURITY_POLICY_APPROVAL_INVALID", "cannot read hash-bound source", ex);
            }
        }
    }

    private String validatePolicy(JsonNode root, String refField, String schemaField, String digestField) {
        String schema = requireText(text(root, schemaField), schemaField);
        String payload = readUtf8(resolveRef(text(root, refField)), refField);
        String validated = policyPayloadValidator.validate(schema, payload).digest();
        requireEquals(digest(root, digestField), validated, digestField);
        return validated;
    }

    private static void requireBoundOperation(
            JsonNode operations, ApprovalVerificationRequest request, String primaryDigest, String drillDigest) {
        if (operations == null || !operations.isArray() || operations.size() != 3) {
            throw invalid("policyOperations must contain the exact three-step rollback exercise");
        }
        boolean matched = false;
        for (int index = 0; index < operations.size(); index++) {
            JsonNode operation = operations.get(index);
            requireObject(operation, "policyOperations[]");
            requireExactFields(operation, OPERATION_FIELDS, "policyOperations[]");
            String from = nullableDigest(operation.get("fromPolicyDigest"), "fromPolicyDigest");
            String to = digest(operation, "toPolicyDigest");
            String operationName = text(operation, "operation");
            String changeClass = text(operation, "changeClass");
            long stateVersion = integer(operation.get("expectedStateVersion"), "expectedStateVersion");
            boolean expectedStep = switch (index) {
                case 0 -> "CREATE_AND_ACTIVATE".equals(operationName) && from == null
                        && primaryDigest.equals(to) && "INITIAL".equals(changeClass) && stateVersion == 0;
                case 1 -> "CREATE_AND_ACTIVATE".equals(operationName) && primaryDigest.equals(from)
                        && drillDigest.equals(to) && "TIGHTENING".equals(changeClass) && stateVersion == 1;
                case 2 -> "ROLLBACK".equals(operationName) && drillDigest.equals(from)
                        && primaryDigest.equals(to) && "EXPANSION".equals(changeClass) && stateVersion == 2;
                default -> false;
            };
            if (!expectedStep) {
                throw invalid("policyOperations does not match the exact INITIAL/TIGHTENING/ROLLBACK sequence");
            }
            boolean current = Objects.equals(request.operation(), operationName)
                    && Objects.equals(request.fromPolicyDigest(), from)
                    && Objects.equals(request.toPolicyDigest(), to)
                    && Objects.equals(request.changeClass(), changeClass)
                    && request.expectedStateVersion() == stateVersion;
            if (current) {
                if (matched) {
                    throw invalid("policyOperations contains duplicate matching operations");
                }
                matched = true;
            }
        }
        if (!matched) {
            throw invalid("requested policy operation is not bound by the control record");
        }
    }

    private static void requirePhaseSequence(JsonNode phases) {
        if (phases == null || !phases.isArray() || phases.size() != 2
                || !"DUAL_READ_ENFORCE_INTERSECTION".equals(phases.get(0).textValue())
                || !"AGENT_FIELD_AUTHORITY".equals(phases.get(1).textValue())) {
            throw invalid("phaseSequence must be exactly B then C");
        }
    }

    private IntegrityKeyRef verificationKeyRef(JsonNode key) {
        requireObject(key, "verificationKey");
        requireExactFields(key, Set.of("keyId", "keyVersion"), "verificationKey");
        try {
            return new IntegrityKeyRef(text(key, "keyId"), text(key, "keyVersion"));
        } catch (IllegalArgumentException ex) {
            throw new PolicyAdministrationException(
                    "SECURITY_POLICY_APPROVAL_INVALID", "verificationKey is invalid", ex);
        }
    }

    private byte[] canonicalWithoutSignature(JsonNode root) {
        ObjectNode copy = root.deepCopy();
        copy.remove("signature");
        return canonical(copy);
    }

    private byte[] canonical(JsonNode node) {
        try {
            return objectMapper.writeValueAsBytes(canonicalNode(node));
        } catch (IOException ex) {
            throw new PolicyAdministrationException(
                    "SECURITY_POLICY_APPROVAL_INVALID", "cannot canonicalize control record", ex);
        }
    }

    private JsonNode canonicalNode(JsonNode node) {
        if (node.isObject()) {
            ObjectNode result = objectMapper.createObjectNode();
            TreeSet<String> names = new TreeSet<>();
            node.fieldNames().forEachRemaining(names::add);
            names.forEach(name -> result.set(name, canonicalNode(node.get(name))));
            return result;
        }
        if (node.isArray()) {
            ArrayNode result = objectMapper.createArrayNode();
            node.forEach(value -> result.add(canonicalNode(value)));
            return result;
        }
        if (!node.isTextual() && !node.isBoolean() && !node.isIntegralNumber() && !node.isNull()) {
            throw invalid("control record contains an unsupported JSON value type");
        }
        return node.deepCopy();
    }

    private String safeRef(JsonNode root, String field) {
        String ref = requireText(text(root, field), field);
        resolveRef(ref);
        return ref;
    }

    private Path resolveRef(String relative) {
        Path path;
        try {
            path = Path.of(relative);
        } catch (RuntimeException ex) {
            throw new PolicyAdministrationException(
                    "SECURITY_POLICY_APPROVAL_INVALID", "source reference is invalid", ex);
        }
        String normalized = path.normalize().toString().replace('\\', '/');
        if (path.isAbsolute() || relative.contains("\\") || !relative.equals(normalized)
                || relative.startsWith("./") || relative.endsWith("/")) {
            throw invalid("source reference must be a canonical repository-relative path");
        }
        try {
            return resolveInsideRepository(path, "source reference");
        } catch (IllegalArgumentException ex) {
            throw new PolicyAdministrationException(
                    "SECURITY_POLICY_APPROVAL_INVALID", "source reference escapes repository root", ex);
        }
    }

    private Path resolveInsideRepository(Path path, String label) {
        Objects.requireNonNull(path, label);
        Path resolved = (path.isAbsolute() ? path : repositoryRoot.resolve(path)).toAbsolutePath().normalize();
        if (!resolved.startsWith(repositoryRoot)) {
            throw new IllegalArgumentException(label + " escapes repository root");
        }
        return resolved;
    }

    private static String readUtf8(Path path, String label) {
        try {
            return Files.readString(path, StandardCharsets.UTF_8);
        } catch (IOException ex) {
            throw new PolicyAdministrationException(
                    "SECURITY_POLICY_APPROVAL_INVALID", "cannot read " + label, ex);
        }
    }

    private static void requireExactFields(JsonNode node, Set<String> expected, String label) {
        Set<String> actual = new HashSet<>();
        node.fieldNames().forEachRemaining(actual::add);
        if (!actual.equals(expected)) {
            throw invalid(label + " fields do not match the closed schema");
        }
    }

    private static void requireObject(JsonNode node, String label) {
        if (node == null || !node.isObject()) {
            throw invalid(label + " must be an object");
        }
    }

    private static void requireEmptyArray(JsonNode node, String label) {
        if (node == null || !node.isArray() || !node.isEmpty()) {
            throw invalid(label + " must be an empty array");
        }
    }

    private static void requireFalse(JsonNode node, String label) {
        if (node == null || !node.isBoolean() || node.booleanValue()) {
            throw invalid(label + " must be false");
        }
    }

    private static String text(JsonNode node, String field) {
        JsonNode value = node == null ? null : node.get(field);
        if (value == null || !value.isTextual()) {
            throw invalid(field + " must be a string");
        }
        return value.textValue();
    }

    private static String digest(JsonNode node, String field) {
        try {
            return requireDigest(text(node, field), field);
        } catch (IllegalArgumentException ex) {
            throw new PolicyAdministrationException(
                    "SECURITY_POLICY_APPROVAL_INVALID", field + " must be a lowercase SHA-256", ex);
        }
    }

    private static String nullableDigest(JsonNode node, String label) {
        if (node == null || node.isNull()) {
            return null;
        }
        if (!node.isTextual()) {
            throw invalid(label + " must be null or a lowercase SHA-256");
        }
        return requireDigest(node.textValue(), label);
    }

    private static long integer(JsonNode node, String label) {
        if (node == null || !node.isIntegralNumber() || !node.canConvertToLong() || node.longValue() < 0) {
            throw invalid(label + " must be a non-negative integer");
        }
        return node.longValue();
    }

    private static Instant instant(JsonNode root, String field) {
        try {
            return Instant.parse(text(root, field));
        } catch (DateTimeParseException ex) {
            throw new PolicyAdministrationException(
                    "SECURITY_POLICY_APPROVAL_INVALID", field + " must be UTC ISO-8601", ex);
        }
    }

    private static String requireId(String value, String label) {
        if (value == null || !ID.matcher(value).matches()) {
            throw invalid(label + " is not a stable identifier");
        }
        return value;
    }

    private static String requireDigest(String value, String label) {
        if (value == null || !DIGEST.matcher(value).matches()) {
            throw new IllegalArgumentException(label + " must be a lowercase SHA-256");
        }
        return value;
    }

    private static String requireText(String value, String label) {
        if (value == null || value.isBlank()) {
            throw new IllegalArgumentException(label + " must not be blank");
        }
        return value;
    }

    private static void requireEquals(Object expected, Object actual, String label) {
        if (!Objects.equals(expected, actual)) {
            throw invalid(label + " does not match the controlled migration request");
        }
    }

    private static String sha256(byte[] value) {
        try {
            return java.util.HexFormat.of().formatHex(MessageDigest.getInstance("SHA-256").digest(value));
        } catch (NoSuchAlgorithmException ex) {
            throw new IllegalStateException("SHA-256 is unavailable", ex);
        }
    }

    private static PolicyAdministrationException invalid(String message) {
        return new PolicyAdministrationException("SECURITY_POLICY_APPROVAL_INVALID", message);
    }
}
