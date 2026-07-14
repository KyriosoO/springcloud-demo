package com.dylan.agent.capability.document.profile;

import com.dylan.agent.metadata.domain.port.CanonicalFieldRef;
import com.dylan.agent.shared.ref.AgentProfileRef;

import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.util.Comparator;
import java.util.HexFormat;
import java.util.List;
import java.util.Map;
import java.util.Set;

/** DPROFILE-1/DPOLICY-1 的稳定 canonical 编码和完整 SHA-256。 */
public final class DocumentProfileCanonicalizer {
    private DocumentProfileCanonicalizer() {}

    public static CanonicalAsset canonicalize(AgentProfileRef owner, List<DocumentRetrievalProfile> profiles) {
        Writer writer = new Writer("DPROFILE-1");
        writer.text(owner.agentId()).text(owner.expectedVersion().orElseThrow());
        writer.label("profiles").number(profiles.size());
        profiles.stream().sorted(Comparator.comparing(DocumentRetrievalProfile::domain)
                        .thenComparing(DocumentRetrievalProfile::profileName))
                .forEach(profile -> writeProfile(writer, profile));
        String digest = sha256(writer.value());
        return new CanonicalAsset("dp1-" + digest, digest);
    }

    public static String policyDigest(
            String policyVersion,
            Map<String, Set<String>> profiles,
            Map<String, ? extends Set<? extends Enum<?>>> channels,
            Map<String, ? extends Set<? extends Enum<?>>> operations) {
        Writer writer = new Writer("DPOLICY-1").text(policyVersion);
        profiles.keySet().stream().sorted().forEach(domain -> {
            writer.label("domain").text(domain)
                    .label("profiles").strings(profiles.get(domain))
                    .label("channels").enums(channels.get(domain))
                    .label("operations").enums(operations.get(domain));
        });
        return sha256(writer.value());
    }

    public static String selectionDigest(
            DocumentProfileAssetRef ref,
            String profileName,
            String policyEvidenceRef,
            String capabilityId,
            String domain,
            String materialType) {
        return sha256(new Writer("DPROFILE-SELECTION-1")
                .text(ref.toString()).text(profileName).text(policyEvidenceRef)
                .text(capabilityId).text(domain).text(materialType == null ? "" : materialType).value());
    }

    private static void writeProfile(Writer writer, DocumentRetrievalProfile profile) {
        writer.label("profile").text(profile.domain()).text(profile.profileName()).bool(profile.defaultProfile())
                .label("materials").strings(profile.allowedMaterialTypes())
                .label("operations").enums(profile.allowedOperations())
                .label("allowedChannels").enums(profile.allowedChannels())
                .label("requiredChannels").enums(profile.requiredChannels())
                .label("weights").number(profile.channelWeights().size());
        profile.channelWeights().entrySet().stream().sorted(Map.Entry.comparingByKey())
                .forEach(entry -> writer.text(entry.getKey().name()).number(entry.getValue()));
        writer.number(profile.fusionPolicy().keywordCandidateCount())
                .number(profile.fusionPolicy().vectorCandidateCount())
                .number(profile.fusionPolicy().rrfK())
                .number(profile.fusionPolicy().numCandidates())
                .number(profile.fusionPolicy().rerankTopN())
                .number(profile.dedupPolicy().maxChunksPerDocument())
                .number(profile.contextPolicy().beforeChunks())
                .number(profile.contextPolicy().afterChunks())
                .text(profile.rewritePolicy().name()).text(profile.embeddingPolicy().name())
                .text(profile.rerankPolicy().name());
        writer.label("generationPolicy").number(profile.generationPolicy().size());
        profile.generationPolicy().entrySet().stream().sorted(Map.Entry.comparingByKey())
                .forEach(entry -> writer.text(entry.getKey().name()).text(entry.getValue().name()));
        writer.label("searchableFields"); fields(writer, profile.searchableFields());
        writer.label("returnableFields"); fields(writer, profile.returnableFields());
    }

    private static void fields(Writer writer, Set<CanonicalFieldRef> fields) {
        writer.number(fields.size());
        fields.stream().sorted(Comparator.comparing(CanonicalFieldRef::domain).thenComparing(CanonicalFieldRef::field))
                .forEach(field -> writer.text(field.domain()).text(field.field()));
    }

    private static String sha256(String value) {
        try {
            return HexFormat.of().formatHex(MessageDigest.getInstance("SHA-256")
                    .digest(value.getBytes(StandardCharsets.UTF_8)));
        } catch (Exception ex) {
            throw new IllegalStateException("SHA-256 unavailable", ex);
        }
    }

    public record CanonicalAsset(String documentProfileVersion, String assetDigest) {}

    private static final class Writer {
        private final StringBuilder value = new StringBuilder();
        private Writer(String prefix) { text(prefix); }
        private Writer text(String text) { value.append(text.length()).append(':').append(text).append('|'); return this; }
        private Writer label(String label) { return text("#" + label); }
        private Writer number(long number) { return text(Long.toString(number)); }
        private Writer bool(boolean flag) { return text(Boolean.toString(flag)); }
        private Writer strings(Set<String> values) { number(values.size()); values.stream().sorted().forEach(this::text); return this; }
        private Writer enums(Set<? extends Enum<?>> values) { number(values.size()); values.stream().map(Enum::name).sorted().forEach(this::text); return this; }
        private String value() { return value.toString(); }
    }
}
