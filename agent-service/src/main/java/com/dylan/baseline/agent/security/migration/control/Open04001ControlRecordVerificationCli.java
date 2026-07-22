package com.dylan.baseline.agent.security.migration.control;

import com.dylan.baseline.agent.security.policy.admin.AuthFieldPolicyPayloadValidator;
import com.dylan.baseline.agent.security.policy.admin.SecurityChangeApprovalEvidencePort.ApprovalVerificationRequest;
import com.dylan.common.security.IntegrityVerificationKeyProvider;
import com.fasterxml.jackson.databind.ObjectMapper;
import java.nio.file.Files;
import java.nio.file.Path;
import java.security.KeyFactory;
import java.security.PublicKey;
import java.security.spec.X509EncodedKeySpec;
import java.time.Clock;
import java.util.LinkedHashMap;
import java.util.Map;

/** 受控环境只读CLI；输出签名校验结果，不执行策略或数据库变更。 */
public final class Open04001ControlRecordVerificationCli {

    private Open04001ControlRecordVerificationCli() {
    }

    public static void main(String[] args) throws Exception {
        Map<String, String> values = parse(args);
        ObjectMapper mapper = new ObjectMapper();
        byte[] publicKeyDer = Files.readAllBytes(Path.of(require(values, "public-key")));
        PublicKey publicKey = KeyFactory.getInstance("Ed25519").generatePublic(
                new X509EncodedKeySpec(publicKeyDer));
        String expectedKeyId = require(values, "key-id");
        String expectedKeyVersion = require(values, "key-version");
        String approverRefDigest = require(values, "approver-ref-digest");
        IntegrityVerificationKeyProvider keys = keyRef -> {
            if (!expectedKeyId.equals(keyRef.keyId()) || !expectedKeyVersion.equals(keyRef.keyVersion())) {
                throw new IllegalArgumentException("verification key reference does not match CLI trust configuration");
            }
            return publicKey;
        };
        var adapter = new Open04001MigrationApprovalEvidenceAdapter(
                Path.of(require(values, "root")), Path.of(require(values, "record")),
                require(values, "repository-revision"), Open04001ExecutionBinding.configurationDigest(
                        expectedKeyId, expectedKeyVersion, approverRefDigest, publicKeyDer),
                Open04001ExecutionBinding.databaseRefDigest(
                        require(values, "jdbc-url"), values.getOrDefault("db-user", "root")),
                approverRefDigest, keys,
                new AuthFieldPolicyPayloadValidator(mapper), mapper, Clock.systemUTC());
        var evidence = adapter.verify(new ApprovalVerificationRequest(
                require(values, "approval-ref"), require(values, "operation"), nullable(values.get("from-digest")),
                require(values, "to-digest"), require(values, "change-class"),
                Long.parseLong(require(values, "expected-state-version")), require(values, "actor-ref-digest")));
        Map<String, Object> output = new LinkedHashMap<>();
        output.put("schemaVersion", "open-04-001-control-verification-v0.1");
        output.put("signatureVerified", true);
        output.put("approvalRef", evidence.approvalRef());
        output.put("evidenceDigest", evidence.evidenceDigest());
        output.put("approverRefDigest", evidence.approverRefDigest());
        output.put("validUntil", evidence.validUntil().toString());
        System.out.println(mapper.writeValueAsString(output));
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

    private static String nullable(String value) {
        return value == null || "null".equals(value) ? null : value;
    }
}
