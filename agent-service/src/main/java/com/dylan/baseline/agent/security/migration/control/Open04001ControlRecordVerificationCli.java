package com.dylan.baseline.agent.security.migration.control;

import com.dylan.baseline.agent.security.policy.admin.AuthFieldPolicyPayloadValidator;
import com.dylan.baseline.agent.security.policy.admin.SecurityChangeApprovalEvidencePort.ApprovalVerificationRequest;
import com.dylan.common.security.IntegrityVerificationKeyProvider;
import com.fasterxml.jackson.core.JsonParser;
import com.fasterxml.jackson.databind.ObjectMapper;
import java.nio.file.Files;
import java.nio.file.Path;
import java.security.KeyFactory;
import java.security.PublicKey;
import java.security.spec.X509EncodedKeySpec;
import java.time.Clock;
import java.time.Instant;
import java.util.ArrayList;
import java.util.List;
import java.util.LinkedHashMap;
import java.util.Map;

/** 受控环境只读CLI；输出签名校验结果，不执行策略或数据库变更。 */
public final class Open04001ControlRecordVerificationCli {

    private Open04001ControlRecordVerificationCli() {
    }

    public static void main(String[] args) throws Exception {
        Map<String, String> values = parse(args);
        ObjectMapper mapper = new ObjectMapper().enable(JsonParser.Feature.STRICT_DUPLICATE_DETECTION);
        byte[] publicKeyDer = Files.readAllBytes(Path.of(require(values, "public-key")));
        PublicKey publicKey = KeyFactory.getInstance("Ed25519").generatePublic(
                new X509EncodedKeySpec(publicKeyDer));
        String expectedKeyId = require(values, "key-id");
        String expectedKeyVersion = require(values, "key-version");
        String approverRefDigest = require(values, "approver-ref-digest");
        String actorRefDigest = require(values, "actor-ref-digest");
        IntegrityVerificationKeyProvider keys = keyRef -> {
            if (!expectedKeyId.equals(keyRef.keyId()) || !expectedKeyVersion.equals(keyRef.keyVersion())) {
                throw new IllegalArgumentException("verification key reference does not match CLI trust configuration");
            }
            return publicKey;
        };
        String configurationDigest = Open04001ExecutionBinding.configurationDigest(
                expectedKeyId, expectedKeyVersion, approverRefDigest, publicKeyDer);
        String databaseRefDigest = Open04001ExecutionBinding.databaseRefDigest(
                require(values, "jdbc-url"), values.getOrDefault("db-user", "root"));
        Path root = Path.of(require(values, "root")).toAbsolutePath().normalize();
        Path recordPath = resolveInside(root, require(values, "record"));
        var adapter = new Open04001MigrationApprovalEvidenceAdapter(
                root, recordPath, require(values, "repository-revision"), configurationDigest, databaseRefDigest,
                approverRefDigest, keys,
                new AuthFieldPolicyPayloadValidator(mapper), mapper, Clock.systemUTC());
        var record = mapper.readTree(Files.readAllBytes(recordPath));
        List<com.dylan.baseline.agent.security.policy.admin.SecurityChangeApprovalEvidencePort.VerifiedApprovalEvidence>
                verified = new ArrayList<>();
        for (ApprovalVerificationRequest request
                : Open04001ControlRecordOperations.verificationRequests(record, actorRefDigest)) {
            verified.add(adapter.verify(request));
        }
        Map<String, Object> output = new LinkedHashMap<>();
        output.put("schemaVersion", "open-04-001-control-verification-v0.1");
        output.put("verifiedAt", Instant.now().toString());
        output.put("signatureVerified", true);
        output.put("repositoryRevision", require(values, "repository-revision"));
        output.put("configurationDigest", configurationDigest);
        output.put("databaseRefDigest", databaseRefDigest);
        output.put("controlRecordRef", require(values, "record"));
        output.put("approvalRef", verified.getFirst().approvalRef());
        output.put("evidenceDigest", verified.getFirst().evidenceDigest());
        output.put("operatorRefDigest", actorRefDigest);
        output.put("approverRefDigest", verified.getFirst().approverRefDigest());
        output.put("validUntil", verified.getFirst().validUntil().toString());
        output.put("verifiedOperations", verified.stream().map(evidence -> Map.of(
                "operation", evidence.operation(),
                "toPolicyDigest", evidence.toPolicyDigest(),
                "changeClass", evidence.changeClass(),
                "expectedStateVersion", evidence.expectedStateVersion())).toList());
        Path outputPath = resolveInside(root, require(values, "output"));
        Open04001EvidenceWriter.writeNew(
                outputPath, mapper.writerWithDefaultPrettyPrinter().writeValueAsString(output) + "\n");
        System.out.println("OPEN-04-001 CONTROL RECORD VERIFIED: " + require(values, "output"));
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
}
