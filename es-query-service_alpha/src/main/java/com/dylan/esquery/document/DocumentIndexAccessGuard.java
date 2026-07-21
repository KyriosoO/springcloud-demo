package com.dylan.esquery.document;

import com.dylan.esquery.service.EsIndexAliasService;

import java.io.IOException;
import java.util.List;

/** 将 Document alias/physical index 与通用 raw ES API 完全隔离。 */
public final class DocumentIndexAccessGuard {
    private final DocumentCorpusCatalog catalog;
    private final EsIndexAliasService aliases;
    public DocumentIndexAccessGuard(DocumentCorpusCatalog catalog, EsIndexAliasService aliases) {
        this.catalog = catalog;
        this.aliases = aliases;
    }
    public void requireGenericTarget(String target) {
        List<String> targets = parseExactTargets(target);
        if (targets.stream().anyMatch(catalog::isDocumentTarget)) {
            throw new DocumentSpecializedEndpointRequiredException();
        }
        for (String candidate : targets) {
            try {
                if (aliases.readCurrent(candidate).targets().stream().anyMatch(catalog::isDocumentTarget)) {
                    throw new DocumentSpecializedEndpointRequiredException();
                }
            } catch (DocumentSpecializedEndpointRequiredException denied) {
                throw denied;
            } catch (IOException | RuntimeException classificationFailure) {
                throw new IllegalStateException("DOCUMENT_TARGET_CLASSIFICATION_UNAVAILABLE", classificationFailure);
            }
        }
    }
    private static List<String> parseExactTargets(String target) {
        if (target == null || target.isBlank() || "_all".equals(target)
                || target.indexOf('*') >= 0 || target.indexOf('?') >= 0) {
            throw new DocumentSpecializedEndpointRequiredException();
        }
        List<String> targets = java.util.Arrays.stream(target.split(",", -1)).map(String::trim).toList();
        if (targets.isEmpty() || targets.stream().anyMatch(value ->
                value.isEmpty() || !value.matches("[a-z0-9._+-]+"))) {
            throw new DocumentSpecializedEndpointRequiredException();
        }
        return targets;
    }
    public static final class DocumentSpecializedEndpointRequiredException extends IllegalArgumentException {
        public DocumentSpecializedEndpointRequiredException() { super("DOCUMENT_SPECIALIZED_ENDPOINT_REQUIRED"); }
    }
}
