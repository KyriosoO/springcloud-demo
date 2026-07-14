package com.dylan.agent.metadata.authorization.model;

import com.dylan.agent.adapter.api.operation.CapabilityOperationType;
import com.dylan.agent.metadata.domain.port.CanonicalFieldRef;

import java.nio.ByteBuffer;
import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.security.NoSuchAlgorithmException;
import java.util.Comparator;
import java.util.HexFormat;
import java.util.Map;
import java.util.Objects;
import java.util.Set;
import java.util.TreeMap;

/** 当前 Invocation 内 capability-neutral 的外部处理授权证据。 */
public final class ExternalProcessingAuthorizationEvidence {

    private final Map<String, Set<CapabilityOperationType>> domainPurposes;
    private final Map<CanonicalFieldRef, ExternalProcessingFieldRule> fieldRules;
    private final String policyEvidenceDigest;
    private final String permissionEvidenceDigest;
    private final String canonicalDigest;

    public ExternalProcessingAuthorizationEvidence(
            Map<String, Set<CapabilityOperationType>> domainPurposes,
            Map<CanonicalFieldRef, ExternalProcessingFieldRule> fieldRules,
            String policyEvidenceDigest,
            String permissionEvidenceDigest) {
        this.domainPurposes = copyDomainPurposes(domainPurposes);
        this.fieldRules = Map.copyOf(Objects.requireNonNull(fieldRules, "fieldRules must not be null"));
        this.policyEvidenceDigest = requireDigest(policyEvidenceDigest, "policyEvidenceDigest");
        this.permissionEvidenceDigest = requireDigest(permissionEvidenceDigest, "permissionEvidenceDigest");
        validateRules();
        this.canonicalDigest = canonicalDigest(
                this.domainPurposes, this.fieldRules, this.policyEvidenceDigest, this.permissionEvidenceDigest);
    }

    public Map<String, Set<CapabilityOperationType>> domainPurposes() { return domainPurposes; }
    public Map<CanonicalFieldRef, ExternalProcessingFieldRule> fieldRules() { return fieldRules; }
    public String policyEvidenceDigest() { return policyEvidenceDigest; }
    public String permissionEvidenceDigest() { return permissionEvidenceDigest; }
    public String canonicalDigest() { return canonicalDigest; }

    public boolean allowsDomain(String domain, CapabilityOperationType purpose) {
        if (domain == null || purpose == null) return false;
        return domainPurposes.getOrDefault(domain, Set.of()).contains(purpose);
    }

    public ExternalProcessingFieldRule requireFieldRule(
            CanonicalFieldRef field,
            CapabilityOperationType purpose) {
        ExternalProcessingFieldRule rule = fieldRules.get(Objects.requireNonNull(field, "field must not be null"));
        if (rule == null || purpose == null || !rule.allowedPurposes().contains(purpose)) {
            throw new IllegalArgumentException("external processing field rule is not allowed");
        }
        return rule;
    }

    public ExternalProcessingAuthorizationEvidence rebindPermission(String evidenceId, String version) {
        return new ExternalProcessingAuthorizationEvidence(
                domainPurposes, fieldRules, policyEvidenceDigest,
                permissionDigest(evidenceId, version, domainPurposes.keySet(), fieldRules.keySet()));
    }

    public ExternalProcessingAuthorizationEvidence narrowTo(
            Set<String> allowedDomains,
            Map<String, Set<String>> allowedFields) {
        Objects.requireNonNull(allowedDomains, "allowedDomains must not be null");
        Objects.requireNonNull(allowedFields, "allowedFields must not be null");
        Map<String, Set<CapabilityOperationType>> narrowedDomains = domainPurposes.entrySet().stream()
                .filter(entry -> allowedDomains.contains(entry.getKey()))
                .collect(java.util.stream.Collectors.toUnmodifiableMap(
                        Map.Entry::getKey, Map.Entry::getValue));
        Map<CanonicalFieldRef, ExternalProcessingFieldRule> narrowedRules = fieldRules.entrySet().stream()
                .filter(entry -> narrowedDomains.containsKey(entry.getKey().domain()))
                .filter(entry -> allowedFields.getOrDefault(
                        entry.getKey().domain(), Set.of()).contains(entry.getKey().field()))
                .collect(java.util.stream.Collectors.toUnmodifiableMap(
                        Map.Entry::getKey, Map.Entry::getValue));
        return new ExternalProcessingAuthorizationEvidence(
                narrowedDomains, narrowedRules, policyEvidenceDigest, permissionEvidenceDigest);
    }

    public boolean isSameOrNarrowerThan(ExternalProcessingAuthorizationEvidence previous) {
        Objects.requireNonNull(previous, "previous must not be null");
        if (!policyEvidenceDigest.equals(previous.policyEvidenceDigest)) return false;
        for (var entry : domainPurposes.entrySet()) {
            if (!previous.domainPurposes.getOrDefault(entry.getKey(), Set.of()).containsAll(entry.getValue())) {
                return false;
            }
        }
        for (var entry : fieldRules.entrySet()) {
            ExternalProcessingFieldRule before = previous.fieldRules.get(entry.getKey());
            ExternalProcessingFieldRule current = entry.getValue();
            if (before == null
                    || !before.classification().equals(current.classification())
                    || before.maskType() != current.maskType()
                    || !before.allowedPurposes().containsAll(current.allowedPurposes())) {
                return false;
            }
        }
        return true;
    }

    public static String policyDigest(
            String policyVersion,
            Map<String, Set<CapabilityOperationType>> domainPurposes,
            Map<CanonicalFieldRef, ExternalProcessingFieldRule> fieldRules) {
        DigestWriter writer = new DigestWriter("EPP-1").text(requireNonBlank(policyVersion, "policyVersion"));
        writeDomainPurposes(writer, copyDomainPurposes(domainPurposes));
        writeFieldRules(writer, Map.copyOf(fieldRules));
        return writer.hex();
    }

    public static String permissionDigest(
            String evidenceId,
            String version,
            Set<String> domains,
            Set<CanonicalFieldRef> fields) {
        DigestWriter writer = new DigestWriter("EPM-1")
                .text(requireNonBlank(evidenceId, "evidenceId"))
                .text(requireNonBlank(version, "version"));
        domains.stream().sorted().forEach(writer::text);
        fields.stream().sorted(fieldComparator()).forEach(field -> writer.text(field.domain()).text(field.field()));
        return writer.hex();
    }

    private void validateRules() {
        for (var entry : fieldRules.entrySet()) {
            if (!entry.getKey().equals(entry.getValue().field())) {
                throw new IllegalArgumentException("field rule key mismatch");
            }
            Set<CapabilityOperationType> domainAllowed = domainPurposes.get(entry.getKey().domain());
            if (domainAllowed == null || !domainAllowed.containsAll(entry.getValue().allowedPurposes())) {
                throw new IllegalArgumentException("field purpose exceeds domain purpose");
            }
        }
    }

    private static String canonicalDigest(
            Map<String, Set<CapabilityOperationType>> domainPurposes,
            Map<CanonicalFieldRef, ExternalProcessingFieldRule> fieldRules,
            String policyDigest,
            String permissionDigest) {
        DigestWriter writer = new DigestWriter("EPA-1").text(policyDigest).text(permissionDigest);
        writeDomainPurposes(writer, domainPurposes);
        writeFieldRules(writer, fieldRules);
        return writer.hex();
    }

    private static void writeDomainPurposes(
            DigestWriter writer,
            Map<String, Set<CapabilityOperationType>> domainPurposes) {
        writer.integer(domainPurposes.size());
        domainPurposes.entrySet().stream().sorted(Map.Entry.comparingByKey()).forEach(entry -> {
            writer.text(entry.getKey()).integer(entry.getValue().size());
            entry.getValue().stream().map(CapabilityOperationType::value).sorted().forEach(writer::text);
        });
    }

    private static void writeFieldRules(
            DigestWriter writer,
            Map<CanonicalFieldRef, ExternalProcessingFieldRule> fieldRules) {
        writer.integer(fieldRules.size());
        fieldRules.entrySet().stream().sorted(Map.Entry.comparingByKey(fieldComparator())).forEach(entry -> {
            ExternalProcessingFieldRule rule = entry.getValue();
            writer.text(entry.getKey().domain()).text(entry.getKey().field());
            writer.text(rule.classification().canonicalDigest()).text(rule.maskType().name());
            writer.integer(rule.allowedPurposes().size());
            rule.allowedPurposes().stream().map(CapabilityOperationType::value).sorted().forEach(writer::text);
        });
    }

    private static Map<String, Set<CapabilityOperationType>> copyDomainPurposes(
            Map<String, Set<CapabilityOperationType>> source) {
        Objects.requireNonNull(source, "domainPurposes must not be null");
        Map<String, Set<CapabilityOperationType>> result = new TreeMap<>();
        source.forEach((domain, purposes) -> result.put(
                requireNonBlank(domain, "domain"),
                Set.copyOf(Objects.requireNonNull(purposes, "purposes must not be null"))));
        return Map.copyOf(result);
    }

    private static Comparator<CanonicalFieldRef> fieldComparator() {
        return Comparator.comparing(CanonicalFieldRef::domain).thenComparing(CanonicalFieldRef::field);
    }

    private static String requireDigest(String value, String name) {
        String checked = requireNonBlank(value, name);
        if (!checked.matches("[0-9a-f]{64}")) throw new IllegalArgumentException(name + " must be sha256 hex");
        return checked;
    }

    private static String requireNonBlank(String value, String name) {
        Objects.requireNonNull(value, name + " must not be null");
        String normalized = value.trim();
        if (normalized.isEmpty()) throw new IllegalArgumentException(name + " must not be blank");
        return normalized;
    }

    private static final class DigestWriter {
        private final MessageDigest digest;

        private DigestWriter(String prefix) {
            try {
                digest = MessageDigest.getInstance("SHA-256");
            } catch (NoSuchAlgorithmException ex) {
                throw new IllegalStateException("SHA-256 unavailable", ex);
            }
            text(prefix);
        }

        private DigestWriter text(String value) {
            byte[] bytes = Objects.requireNonNull(value).getBytes(StandardCharsets.UTF_8);
            integer(bytes.length);
            digest.update(bytes);
            return this;
        }

        private DigestWriter integer(int value) {
            digest.update(ByteBuffer.allocate(Integer.BYTES).putInt(value).array());
            return this;
        }

        private String hex() { return HexFormat.of().formatHex(digest.digest()); }
    }
}
