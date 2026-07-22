package com.dylan.baseline.agent.security.migration.control;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.fasterxml.jackson.databind.node.ObjectNode;
import java.nio.file.Files;
import java.nio.file.Path;
import java.security.KeyPair;
import java.security.KeyPairGenerator;
import java.security.Signature;
import java.util.Base64;
import java.util.LinkedHashMap;
import java.util.Map;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;

class Open04001IndependentExitReviewVerificationCliTest {

    private static final String OPERATOR = "a".repeat(64);
    private static final String REVIEWER = "b".repeat(64);
    private final ObjectMapper mapper = new ObjectMapper();

    @TempDir
    Path root;

    @Test
    void verifiesSignedIndependentReviewAndRejectsArtifactDrift() throws Exception {
        KeyPair keyPair = KeyPairGenerator.getInstance("Ed25519").generateKeyPair();
        Path publicKey = root.resolve("review-public-key.der");
        Files.write(publicKey, keyPair.getPublic().getEncoded());
        Map<String, Path> artifacts = writeArtifacts();
        ObjectNode review = review(artifacts);
        signAndWrite(keyPair, review);

        run(publicKey, "review-verification.json");
        JsonNode result = mapper.readTree(root.resolve("review-verification.json").toFile());
        assertThat(result.path("signatureVerified").booleanValue()).isTrue();
        assertThat(result.path("reviewerRefDigest").textValue()).isEqualTo(REVIEWER);

        Files.writeString(artifacts.get("observationRef"), "drifted");
        assertThatThrownBy(() -> run(publicKey, "review-verification-after-drift.json"))
                .isInstanceOf(IllegalArgumentException.class)
                .hasMessageContaining("reviewedArtifactHashes");
    }

    @Test
    void rejectsReviewThatIsNotStrictlyLaterThanAllReviewedArtifacts() throws Exception {
        KeyPair keyPair = KeyPairGenerator.getInstance("Ed25519").generateKeyPair();
        Path publicKey = root.resolve("review-public-key.der");
        Files.write(publicKey, keyPair.getPublic().getEncoded());
        ObjectNode review = review(writeArtifacts());
        review.put("reviewedAt", "2026-07-22T06:40:00Z");
        signAndWrite(keyPair, review);

        assertThatThrownBy(() -> run(publicKey, "review-verification.json"))
                .isInstanceOf(IllegalArgumentException.class)
                .hasMessageContaining("reviewedAt must follow");
    }

    private Map<String, Path> writeArtifacts() throws Exception {
        Map<String, Path> artifacts = new LinkedHashMap<>();
        artifacts.put("designRef", write("04.md", "design"));
        ObjectNode control = mapper.createObjectNode();
        control.put("approverRefDigest", REVIEWER);
        control.put("operatorRefDigest", OPERATOR);
        control.putObject("verificationKey").put("keyId", "review-key").put("keyVersion", "v1");
        control.put("validUntil", "2026-07-22T08:00:00Z");
        Path controlPath = writeJson("control.json", control);
        artifacts.put("controlRecordRef", controlPath);
        String controlDigest = Open04001CanonicalJson.sha256(Open04001CanonicalJson.canonical(mapper, control));

        ObjectNode verification = mapper.createObjectNode();
        verification.put("schemaVersion", "open-04-001-control-verification-v0.1");
        verification.put("verifiedAt", "2026-07-22T06:10:00Z");
        verification.put("signatureVerified", true);
        verification.put("evidenceDigest", controlDigest);
        verification.put("operatorRefDigest", OPERATOR);
        verification.put("approverRefDigest", REVIEWER);
        artifacts.put("controlVerificationRef", writeJson("control-verification.json", verification));

        ObjectNode migration = mapper.createObjectNode();
        migration.put("schemaVersion", "open-04-001-controlled-migration-result-v0.1");
        migration.put("completedAt", "2026-07-22T06:20:00Z");
        migration.put("signatureVerified", true);
        migration.put("rollbackExercisePassed", true);
        migration.put("controlRecordDigest", controlDigest);
        migration.put("operatorRefDigest", OPERATOR);
        migration.put("approverRefDigest", REVIEWER);
        artifacts.put("migrationResultRef", writeJson("migration.json", migration));

        ObjectNode observation = mapper.createObjectNode();
        observation.put("windowEnd", "2026-07-22T06:30:00Z");
        artifacts.put("observationRef", writeJson("observation.json", observation));
        artifacts.put("repositoryConsumerScanRef", write("repository-scan.json", "repository scan"));
        ObjectNode externalScan = mapper.createObjectNode();
        externalScan.put("generatedAt", "2026-07-22T06:35:00Z");
        artifacts.put("externalConsumerScanRef", writeJson("external-scan.json", externalScan));
        ObjectNode authContract = mapper.createObjectNode();
        authContract.put("generatedAt", "2026-07-22T06:40:00Z");
        artifacts.put("authContractEvidenceRef", writeJson("auth-contract.json", authContract));
        return artifacts;
    }

    private void signAndWrite(KeyPair keyPair, ObjectNode review) throws Exception {
        Signature signer = Signature.getInstance("Ed25519");
        signer.initSign(keyPair.getPrivate());
        signer.update(Open04001CanonicalJson.canonicalWithout(mapper, review, "signature"));
        review.put("signature", Base64.getUrlEncoder().withoutPadding().encodeToString(signer.sign()));
        Files.writeString(root.resolve("review.json"), mapper.writeValueAsString(review));
    }

    private ObjectNode review(Map<String, Path> artifacts) throws Exception {
        ObjectNode review = mapper.createObjectNode();
        review.put("schemaVersion", Open04001IndependentExitReviewVerificationCli.REVIEW_SCHEMA);
        review.put("reviewId", "review-1");
        review.put("reviewerRefDigest", REVIEWER);
        review.put("operatorRefDigest", OPERATOR);
        review.putObject("verificationKey").put("keyId", "review-key").put("keyVersion", "v1");
        review.put("reviewedAt", "2026-07-22T07:00:00Z");
        review.put("decision", "APPROVE_OPEN_04_001_EXIT");
        review.putArray("findings");
        ObjectNode hashes = review.putObject("reviewedArtifactHashes");
        for (Map.Entry<String, Path> entry : artifacts.entrySet()) {
            String relative = root.relativize(entry.getValue()).toString().replace('\\', '/');
            review.put(entry.getKey(), relative);
            hashes.put(relative, Open04001CanonicalJson.sha256(Files.readAllBytes(entry.getValue())));
        }
        return review;
    }

    private void run(Path publicKey, String output) throws Exception {
        Open04001IndependentExitReviewVerificationCli.main(new String[]{
                "--root", root.toString(), "--review", "review.json", "--public-key", publicKey.toString(),
                "--key-id", "review-key", "--key-version", "v1", "--output", output,
        });
    }

    private Path write(String name, String content) throws Exception {
        Path path = root.resolve(name);
        Files.writeString(path, content);
        return path;
    }

    private Path writeJson(String name, JsonNode content) throws Exception {
        return write(name, mapper.writeValueAsString(content));
    }
}
