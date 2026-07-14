package com.dylan.agent.capability.document.governance.emergency;

import org.springframework.jdbc.core.JdbcTemplate;

import java.nio.ByteBuffer;
import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.time.Clock;
import java.time.Instant;
import java.util.ArrayList;
import java.util.HashMap;
import java.util.HashSet;
import java.util.HexFormat;
import java.util.List;
import java.util.Map;
import java.util.Set;

/** 07 authoritative current emergency read；单批读取，partial/unavailable 均 fail closed。 */
public final class JdbcDocumentEmergencyControlRepository implements DocumentEmergencyControlReadPort {
    private static final int MAX_TARGETS = 200;
    private final JdbcTemplate jdbc;
    private final Clock clock;

    public JdbcDocumentEmergencyControlRepository(JdbcTemplate jdbc, Clock clock) {
        this.jdbc = jdbc;
        this.clock = clock;
    }

    @Override
    public DocumentEmergencyView readCurrent(List<DocumentEmergencyTargetRef> targets, Instant deadline) {
        Instant now = clock.instant();
        List<TargetKey> keys;
        try {
            keys = keys(targets);
        } catch (RuntimeException ex) {
            return failure(List.of(new TargetKey("TARGET_SET", digest("INVALID_TARGET_SET"))),
                    now, "INVALID_TARGET_SET");
        }
        if (deadline == null || !now.isBefore(deadline)) return failure(keys, now, "DEADLINE");
        try {
            Map<TargetKey, String> current = readBatch(keys);
            List<DocumentEmergencyView.Decision> decisions = new ArrayList<>(keys.size());
            for (TargetKey key : keys) {
                String state = current.get(key);
                DocumentEmergencyView.Outcome outcome;
                String reason = null;
                if (state == null || "CLEARED".equals(state)) {
                    outcome = DocumentEmergencyView.Outcome.NOT_BLOCKED;
                } else if ("ACTIVE".equals(state)) {
                    outcome = DocumentEmergencyView.Outcome.BLOCKED;
                    reason = "EMERGENCY_ACTIVE";
                } else {
                    return failure(keys, now, "UNKNOWN_STATE");
                }
                decisions.add(new DocumentEmergencyView.Decision(key.type(), key.digest(), outcome, reason));
            }
            Instant validUntil = min(deadline, now.plusSeconds(2));
            String canonical = viewDigest(decisions, now, validUntil);
            return new DocumentEmergencyView("DEV-" + canonical.substring(0, 16), decisions,
                    now, validUntil, canonical);
        } catch (RuntimeException ex) {
            return failure(keys, now, "STORE_UNAVAILABLE");
        }
    }

    private Map<TargetKey, String> readBatch(List<TargetKey> keys) {
        if (keys.isEmpty()) return Map.of();
        String predicates = String.join(" OR ", java.util.Collections.nCopies(keys.size(),
                "(target_type=? AND target_key_digest=?)"));
        List<Object> arguments = new ArrayList<>(keys.size() * 2);
        keys.forEach(key -> { arguments.add(key.type()); arguments.add(key.digest()); });
        Map<TargetKey, String> result = new HashMap<>();
        jdbc.query("SELECT target_type,target_key_digest,state FROM document_emergency_control WHERE " + predicates,
                rs -> {
                    TargetKey key = new TargetKey(rs.getString(1), rs.getString(2));
                    if (result.putIfAbsent(key, rs.getString(3)) != null) {
                        throw new IllegalStateException("duplicate emergency current row");
                    }
                }, arguments.toArray());
        return Map.copyOf(result);
    }

    private DocumentEmergencyView failure(List<TargetKey> keys, Instant now, String reason) {
        List<DocumentEmergencyView.Decision> decisions = keys.stream()
                .map(key -> new DocumentEmergencyView.Decision(key.type(), key.digest(),
                        DocumentEmergencyView.Outcome.FAILURE, reason)).toList();
        String canonical = viewDigest(decisions, now, now);
        return new DocumentEmergencyView("DEV-" + canonical.substring(0, 16), decisions,
                now, now, canonical);
    }

    private static List<TargetKey> keys(List<DocumentEmergencyTargetRef> targets) {
        if (targets == null || targets.size() > MAX_TARGETS) throw new IllegalArgumentException("target count invalid");
        List<TargetKey> result = new ArrayList<>(targets.size());
        Set<TargetKey> seen = new HashSet<>();
        for (DocumentEmergencyTargetRef target : targets) {
            if (target == null) throw new IllegalArgumentException("target must not be null");
            var binding = DocumentEmergencyGateCanonicalizer.targetBinding(target);
            TargetKey key = new TargetKey(binding.targetType().name(), binding.targetKeyDigest());
            if (!seen.add(key)) throw new IllegalArgumentException("duplicate emergency target");
            result.add(key);
        }
        return List.copyOf(result);
    }

    private static String viewDigest(List<DocumentEmergencyView.Decision> decisions,
                                     Instant checkedAt, Instant validUntil) {
        List<String> fields = new ArrayList<>();
        fields.add("DEV-1");
        for (var decision : decisions) {
            fields.add(decision.targetType());
            fields.add(decision.targetDigest());
            fields.add(decision.outcome().name());
            fields.add(decision.reasonCode() == null ? "" : decision.reasonCode());
        }
        fields.add(checkedAt.toString());
        fields.add(validUntil.toString());
        return digest(fields.toArray(String[]::new));
    }

    private static Instant min(Instant left, Instant right) { return left.isBefore(right) ? left : right; }

    private static String digest(String... values) {
        try {
            MessageDigest digest = MessageDigest.getInstance("SHA-256");
            for (String value : values) {
                byte[] bytes = value.getBytes(StandardCharsets.UTF_8);
                digest.update(ByteBuffer.allocate(4).putInt(bytes.length).array());
                digest.update(bytes);
            }
            return HexFormat.of().formatHex(digest.digest());
        } catch (Exception ex) { throw new IllegalStateException(ex); }
    }

    private record TargetKey(String type, String digest) {}
}
