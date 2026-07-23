package com.dylan.esquery.document;

import com.dylan.esquery.api.model.DocumentCorpusKeyDto;

import java.util.Collection;
import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.util.HexFormat;
import java.util.LinkedHashMap;
import java.util.Map;
import java.util.Comparator;

/** 原子发布的 Corpus Catalog 当前快照。 */
public final class DocumentCorpusCatalog {
    private final Map<DocumentCorpusKeyDto, DocumentCorpusDefinition> definitions;
    private final Map<String, DocumentCorpusDefinition> aliases;
    private final DocumentCorpusCatalogSnapshot snapshot;

    public DocumentCorpusCatalog(Collection<DocumentCorpusDefinition> candidates) {
        Map<DocumentCorpusKeyDto, DocumentCorpusDefinition> byKey = new LinkedHashMap<>();
        Map<String, DocumentCorpusDefinition> byAlias = new LinkedHashMap<>();
        for (DocumentCorpusDefinition definition : candidates == null ? java.util.List.<DocumentCorpusDefinition>of() : candidates) {
            if (byKey.putIfAbsent(definition.corpusKey(), definition) != null) throw new IllegalArgumentException("duplicate corpus key");
            if (byAlias.putIfAbsent(definition.readAlias(), definition) != null) throw new IllegalArgumentException("duplicate corpus alias");
        }
        this.definitions = Map.copyOf(byKey);
        this.aliases = Map.copyOf(byAlias);
        String digest = digest(this.definitions);
        this.snapshot = new DocumentCorpusCatalogSnapshot("DCC-1:" + digest.substring(0, 12), digest, this.definitions);
    }

    public DocumentCorpusDefinition require(DocumentCorpusKeyDto key) {
        DocumentCorpusDefinition definition = definitions.get(key);
        if (definition == null) throw new IllegalArgumentException("unknown document corpus");
        return definition;
    }

    public DocumentCorpusDefinition requireByKeyDigest(String keyDigest) {
        if (keyDigest == null || !keyDigest.matches("[0-9a-f]{64}")) {
            throw new IllegalArgumentException("document corpus key digest invalid");
        }
        return definitions.entrySet().stream()
                .filter(entry -> keyDigest.equals(sha256(entry.getKey().canonicalBytes())))
                .map(Map.Entry::getValue)
                .findFirst()
                .orElseThrow(() -> new IllegalArgumentException("unknown document corpus digest"));
    }

    public boolean isDocumentTarget(String target) {
        return target != null && (target.startsWith("agent-doc-") || aliases.containsKey(target));
    }

    public DocumentCorpusCatalogSnapshot snapshot() { return snapshot; }

    private static String digest(Map<DocumentCorpusKeyDto, DocumentCorpusDefinition> definitions) {
        try {
            MessageDigest digest = MessageDigest.getInstance("SHA-256");
            digest.update("DCC-1".getBytes(StandardCharsets.UTF_8));
            definitions.values().stream()
                    .sorted(Comparator.comparing((DocumentCorpusDefinition value) -> value.corpusKey().domain())
                            .thenComparing(value -> value.corpusKey().materialType()))
                    .map(value -> String.join("\u001f", value.corpusKey().domain(), value.corpusKey().materialType(),
                            value.readAlias(), value.schemaRef().canonicalDigest(), value.analyzerRef(), value.vectorPolicyRef(),
                            value.chunkStrategyRef(), value.sourceConnectorId(),
                            value.indexedBusinessFields().stream().sorted().reduce((left, right) -> left + "\u001e" + right).orElse("")))
                    .forEach(value -> {
                        byte[] bytes = value.getBytes(StandardCharsets.UTF_8);
                        digest.update(java.nio.ByteBuffer.allocate(Integer.BYTES).putInt(bytes.length).array());
                        digest.update(bytes);
                    });
            return HexFormat.of().formatHex(digest.digest());
        } catch (Exception ex) {
            throw new IllegalStateException("catalog digest unavailable", ex);
        }
    }

    private static String sha256(byte[] bytes) {
        try {
            return HexFormat.of().formatHex(MessageDigest.getInstance("SHA-256").digest(bytes));
        } catch (Exception ex) {
            throw new IllegalStateException("corpus key digest unavailable", ex);
        }
    }
}
