package com.dylan.baseline.agent.security.migration.control;

import com.dylan.common.security.Ed25519IntegritySupport;
import com.fasterxml.jackson.core.JsonParser;
import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import java.nio.file.Files;
import java.nio.file.Path;
import java.security.KeyFactory;
import java.security.PublicKey;
import java.security.spec.X509EncodedKeySpec;
import java.time.Instant;
import java.util.HashSet;
import java.util.LinkedHashMap;
import java.util.Map;
import java.util.Set;
import java.util.regex.Pattern;

/** 验证独立关闭复审签名及其八类原始制品绑定，不执行数据库操作。 */
public final class Open04001IndependentExitReviewVerificationCli {

    static final String REVIEW_SCHEMA = "open-04-001-independent-exit-review-v0.1";
    private static final String OUTPUT_SCHEMA = "open-04-001-independent-review-verification-v0.1";
    private static final Pattern DIGEST = Pattern.compile("[0-9a-f]{64}");
    private static final Set<String> REVIEW_FIELDS = Set.of(
            "schemaVersion", "reviewId", "reviewerRefDigest", "operatorRefDigest", "verificationKey",
            "reviewedAt", "decision", "findings", "designRef", "controlRecordRef",
            "controlVerificationRef", "migrationResultRef", "observationRef",
            "repositoryConsumerScanRef", "externalConsumerScanRef", "authContractEvidenceRef",
            "reviewedArtifactHashes", "signature");
    private static final Set<String> ROLE_FIELDS = Set.of(
            "designRef", "controlRecordRef", "controlVerificationRef", "migrationResultRef",
            "observationRef", "repositoryConsumerScanRef", "externalConsumerScanRef", "authContractEvidenceRef");

    private Open04001IndependentExitReviewVerificationCli() {
    }

    public static void main(String[] args) throws Exception {
        Map<String, String> values = parse(args);
        ObjectMapper mapper = new ObjectMapper().enable(JsonParser.Feature.STRICT_DUPLICATE_DETECTION);
        Path root = Path.of(require(values, "root")).toAbsolutePath().normalize();
        Path reviewPath = resolveInside(root, require(values, "review"));
        JsonNode review = mapper.readTree(Files.readAllBytes(reviewPath));
        requireExactFields(review, REVIEW_FIELDS, "review");
        requireEquals(REVIEW_SCHEMA, text(review, "schemaVersion"), "schemaVersion");
        requireEquals("APPROVE_OPEN_04_001_EXIT", text(review, "decision"), "decision");
        if (!review.path("findings").isArray() || !review.path("findings").isEmpty()) {
            throw new IllegalArgumentException("findings must be an empty array for approval");
        }

        String reviewer = digest(review, "reviewerRefDigest");
        String operator = digest(review, "operatorRefDigest");
        if (reviewer.equals(operator)) {
            throw new IllegalArgumentException("independent reviewer must differ from operator");
        }
        JsonNode key = review.path("verificationKey");
        requireExactFields(key, Set.of("keyId", "keyVersion"), "verificationKey");
        String keyId = require(values, "key-id");
        String keyVersion = require(values, "key-version");
        requireEquals(keyId, text(key, "keyId"), "verificationKey.keyId");
        requireEquals(keyVersion, text(key, "keyVersion"), "verificationKey.keyVersion");

        Map<String, String> refs = new LinkedHashMap<>();
        for (String role : ROLE_FIELDS) {
            refs.put(role, text(review, role));
        }
        if (new HashSet<>(refs.values()).size() != ROLE_FIELDS.size()) {
            throw new IllegalArgumentException("independent review role references must be distinct");
        }
        JsonNode hashes = review.path("reviewedArtifactHashes");
        if (!hashes.isObject()) {
            throw new IllegalArgumentException("reviewedArtifactHashes must be an object");
        }
        Set<String> hashRefs = new HashSet<>();
        hashes.fieldNames().forEachRemaining(hashRefs::add);
        if (!hashRefs.equals(new HashSet<>(refs.values()))) {
            throw new IllegalArgumentException("reviewedArtifactHashes must exactly bind the eight role references");
        }
        for (String ref : hashRefs) {
            String expected = digest(hashes, ref);
            String actual = Open04001CanonicalJson.sha256(Files.readAllBytes(resolveInside(root, ref)));
            requireEquals(expected, actual, "reviewedArtifactHashes." + ref);
        }

        JsonNode control = read(mapper, resolveInside(root, refs.get("controlRecordRef")));
        JsonNode controlVerification = read(mapper, resolveInside(root, refs.get("controlVerificationRef")));
        JsonNode migration = read(mapper, resolveInside(root, refs.get("migrationResultRef")));
        JsonNode observation = read(mapper, resolveInside(root, refs.get("observationRef")));
        JsonNode externalScan = read(mapper, resolveInside(root, refs.get("externalConsumerScanRef")));
        JsonNode authContract = read(mapper, resolveInside(root, refs.get("authContractEvidenceRef")));
        requireEquals(reviewer, digest(control, "approverRefDigest"), "reviewerRefDigest");
        requireEquals(operator, digest(control, "operatorRefDigest"), "operatorRefDigest");
        JsonNode controlKey = control.path("verificationKey");
        requireEquals(keyId, text(controlKey, "keyId"), "control verification keyId");
        requireEquals(keyVersion, text(controlKey, "keyVersion"), "control verification keyVersion");
        requireEquals("open-04-001-control-verification-v0.1",
                text(controlVerification, "schemaVersion"), "control verification schema");
        requireEquals("open-04-001-controlled-migration-result-v0.1",
                text(migration, "schemaVersion"), "migration result schema");
        if (!controlVerification.path("signatureVerified").asBoolean(false)
                || !migration.path("signatureVerified").asBoolean(false)
                || !migration.path("rollbackExercisePassed").asBoolean(false)) {
            throw new IllegalArgumentException("control verification and migration result must be successful");
        }
        String controlDigest = Open04001CanonicalJson.sha256(Open04001CanonicalJson.canonical(mapper, control));
        requireEquals(controlDigest, digest(controlVerification, "evidenceDigest"), "control verification digest");
        requireEquals(controlDigest, digest(migration, "controlRecordDigest"), "migration control digest");
        requireEquals(operator, digest(controlVerification, "operatorRefDigest"), "verification operator");
        requireEquals(operator, digest(migration, "operatorRefDigest"), "migration operator");
        requireEquals(reviewer, digest(controlVerification, "approverRefDigest"), "verification approver");
        requireEquals(reviewer, digest(migration, "approverRefDigest"), "migration approver");

        Instant reviewedAt = instant(review, "reviewedAt");
        Instant latestRunArtifact = max(
                instant(controlVerification, "verifiedAt"),
                instant(migration, "completedAt"),
                instant(observation, "windowEnd"),
                instant(externalScan, "generatedAt"),
                instant(authContract, "generatedAt"));
        if (!reviewedAt.isAfter(latestRunArtifact) || reviewedAt.isAfter(instant(control, "validUntil"))) {
            throw new IllegalArgumentException("reviewedAt must follow run artifacts and not exceed validUntil");
        }

        byte[] publicKeyDer = Files.readAllBytes(Path.of(require(values, "public-key")));
        PublicKey publicKey = KeyFactory.getInstance("Ed25519").generatePublic(new X509EncodedKeySpec(publicKeyDer));
        byte[] signed = Open04001CanonicalJson.canonicalWithout(mapper, review, "signature");
        if (!Ed25519IntegritySupport.verifyBase64Url(signed, text(review, "signature"), publicKey)) {
            throw new IllegalArgumentException("independent review signature is invalid");
        }

        Map<String, Object> output = new LinkedHashMap<>();
        output.put("schemaVersion", OUTPUT_SCHEMA);
        output.put("verifiedAt", Instant.now().toString());
        output.put("signatureVerified", true);
        output.put("reviewRef", require(values, "review"));
        output.put("reviewId", text(review, "reviewId"));
        output.put("reviewDigest", Open04001CanonicalJson.sha256(Open04001CanonicalJson.canonical(mapper, review)));
        output.put("reviewerRefDigest", reviewer);
        output.put("operatorRefDigest", operator);
        output.put("controlRecordDigest", controlDigest);
        output.put("reviewedArtifactHashes", mapper.convertValue(hashes, Map.class));
        Path outputPath = resolveInside(root, require(values, "output"));
        Open04001EvidenceWriter.writeNew(
                outputPath, mapper.writerWithDefaultPrettyPrinter().writeValueAsString(output) + "\n");
        System.out.println("OPEN-04-001 INDEPENDENT REVIEW VERIFIED: " + require(values, "output"));
    }

    private static JsonNode read(ObjectMapper mapper, Path path) throws Exception {
        return mapper.readTree(Files.readAllBytes(path));
    }

    private static Instant max(Instant first, Instant... remaining) {
        Instant result = first;
        for (Instant value : remaining) {
            if (value.isAfter(result)) {
                result = value;
            }
        }
        return result;
    }

    private static Instant instant(JsonNode value, String field) {
        return Instant.parse(text(value, field));
    }

    private static String digest(JsonNode value, String field) {
        String result = text(value, field);
        if (!DIGEST.matcher(result).matches()) {
            throw new IllegalArgumentException(field + " must be a lowercase SHA-256");
        }
        return result;
    }

    private static String text(JsonNode value, String field) {
        JsonNode node = value.get(field);
        if (node == null || !node.isTextual() || node.textValue().isBlank()) {
            throw new IllegalArgumentException(field + " must be non-blank text");
        }
        return node.textValue();
    }

    private static void requireExactFields(JsonNode value, Set<String> expected, String label) {
        if (value == null || !value.isObject()) {
            throw new IllegalArgumentException(label + " must be an object");
        }
        Set<String> actual = new HashSet<>();
        value.fieldNames().forEachRemaining(actual::add);
        if (!actual.equals(expected)) {
            throw new IllegalArgumentException(label + " fields do not match the closed schema");
        }
    }

    private static void requireEquals(String expected, String actual, String label) {
        if (!expected.equals(actual)) {
            throw new IllegalArgumentException(label + " does not match");
        }
    }

    private static Path resolveInside(Path root, String relative) {
        Path path = Path.of(relative);
        if (path.isAbsolute() || relative.contains("\\")
                || !relative.equals(path.normalize().toString().replace('\\', '/'))) {
            throw new IllegalArgumentException("path must be canonical and repository-relative");
        }
        Path resolved = root.resolve(path).normalize();
        if (!resolved.startsWith(root)) {
            throw new IllegalArgumentException("path escapes repository root");
        }
        return resolved;
    }

    private static Map<String, String> parse(String[] args) {
        Map<String, String> result = new LinkedHashMap<>();
        for (int index = 0; index < args.length; index += 2) {
            if (index + 1 >= args.length || !args[index].startsWith("--")) {
                throw new IllegalArgumentException("arguments must be --name value pairs");
            }
            if (result.putIfAbsent(args[index].substring(2), args[index + 1]) != null) {
                throw new IllegalArgumentException("duplicate argument: " + args[index]);
            }
        }
        return result;
    }

    private static String require(Map<String, String> values, String key) {
        String value = values.get(key);
        if (value == null || value.isBlank()) {
            throw new IllegalArgumentException("missing --" + key);
        }
        return value;
    }
}
