package com.dylan.agent.capability.document.governance.emergency;

import java.io.ByteArrayOutputStream;
import java.nio.ByteBuffer;
import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.time.Instant;
import java.util.ArrayList;
import java.util.HexFormat;
import java.util.List;

public final class DocumentEmergencyGateCanonicalizer {
    private DocumentEmergencyGateCanonicalizer() {
    }

    public static DocumentEmergencyGateTargetBinding targetBinding(DocumentEmergencyTargetRef target) {
        return new DocumentEmergencyGateTargetBinding(
                DocumentEmergencyTargetType.fromWire(target.type()),
                sha256(lengthPrefixed("DET-1", target.type(), target.key())));
    }

    public static byte[] canonicalBytes(DocumentEmergencyRolloutBinding rollout,
                                        List<DocumentEmergencyGateTargetBinding> orderedTargets,
                                        String emergencyViewVersion,
                                        DocumentEmergencyGateStatus status,
                                        Instant issuedAt,
                                        Instant validUntil) {
        List<String> fields = new ArrayList<>();
        fields.add("EGE-1");
        fields.add(rollout.unitType());
        fields.add(rollout.unitKeyDigest());
        fields.add(rollout.expectedStateDigest());
        fields.add(rollout.targetStateDigest());
        fields.add(rollout.validationReportId());
        fields.add(Integer.toString(orderedTargets.size()));
        for (var target : orderedTargets) {
            fields.add(target.targetType().name());
            fields.add(target.targetKeyDigest());
        }
        fields.add(emergencyViewVersion);
        fields.add(status.name());
        fields.add(issuedAt.toString());
        fields.add(validUntil.toString());
        return lengthPrefixed(fields.toArray(String[]::new));
    }

    public static String canonicalDigest(byte[] canonicalBytes) {
        return sha256(canonicalBytes);
    }

    public static String evidenceId(String canonicalDigest) {
        return sha256(lengthPrefixed("EGE-ID-1", canonicalDigest));
    }

    private static byte[] lengthPrefixed(String... values) {
        try {
            ByteArrayOutputStream output = new ByteArrayOutputStream();
            for (String value : values) {
                byte[] bytes = value.getBytes(StandardCharsets.UTF_8);
                output.write(ByteBuffer.allocate(4).putInt(bytes.length).array());
                output.write(bytes);
            }
            return output.toByteArray();
        } catch (java.io.IOException ex) {
            throw new IllegalStateException(ex);
        }
    }

    private static String sha256(byte[] bytes) {
        try {
            return HexFormat.of().formatHex(MessageDigest.getInstance("SHA-256").digest(bytes));
        } catch (Exception ex) {
            throw new IllegalStateException(ex);
        }
    }
}
