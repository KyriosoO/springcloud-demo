package com.dylan.agent.capability.document.profile;

import com.dylan.agent.metadata.domain.port.CanonicalFieldRef;

import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.util.Comparator;
import java.util.HexFormat;

/** final server profile projection 的稳定完整摘要。 */
public final class DocumentProfileProjectionDigest {
    private DocumentProfileProjectionDigest() {}

    public static String compute(DocumentPlanningProfileProjection profile) {
        StringBuilder canonical = new StringBuilder("DPROFILE-PROJECTION-1\n");
        add(canonical, profile.domain()); add(canonical, profile.profileName()); add(canonical, profile.documentProfileVersion());
        profile.allowedCorpora().stream().sorted(Comparator.comparing(c -> c.domain() + "\u001f" + c.materialType()))
                .forEach(corpus -> { add(canonical, corpus.domain()); add(canonical, corpus.materialType()); });
        profile.allowedOperations().stream().map(Enum::name).sorted().forEach(value -> add(canonical, value));
        profile.allowedChannels().stream().map(Enum::name).sorted().forEach(value -> add(canonical, value));
        profile.requiredChannels().stream().map(Enum::name).sorted().forEach(value -> add(canonical, value));
        profile.channelWeights().entrySet().stream().sorted(java.util.Map.Entry.comparingByKey())
                .forEach(entry -> { add(canonical, entry.getKey().name()); add(canonical, entry.getValue().toString()); });
        var fusion = profile.fusionPolicy();
        add(canonical, Integer.toString(fusion.keywordCandidateCount())); add(canonical, Integer.toString(fusion.vectorCandidateCount()));
        add(canonical, Integer.toString(fusion.rrfK())); add(canonical, Integer.toString(fusion.numCandidates()));
        add(canonical, Integer.toString(fusion.rerankTopN()));
        add(canonical, Integer.toString(profile.dedupPolicy().maxChunksPerDocument()));
        add(canonical, Integer.toString(profile.contextPolicy().beforeChunks()));
        add(canonical, Integer.toString(profile.contextPolicy().afterChunks()));
        add(canonical, profile.rewritePolicy().name()); add(canonical, profile.embeddingPolicy().name());
        add(canonical, profile.rerankPolicy().name()); add(canonical, profile.generationPolicy().name());
        fields(canonical, profile.searchableFields()); fields(canonical, profile.returnableFields());
        try {
            return HexFormat.of().formatHex(MessageDigest.getInstance("SHA-256")
                    .digest(canonical.toString().getBytes(StandardCharsets.UTF_8)));
        } catch (Exception ex) { throw new IllegalStateException("SHA-256 unavailable", ex); }
    }

    private static void fields(StringBuilder canonical, java.util.Set<CanonicalFieldRef> fields) {
        fields.stream().sorted(Comparator.comparing(CanonicalFieldRef::domain).thenComparing(CanonicalFieldRef::field))
                .forEach(field -> { add(canonical, field.domain()); add(canonical, field.field()); });
    }
    private static void add(StringBuilder target, String value) { target.append(value.length()).append(':').append(value).append('\n'); }
}
