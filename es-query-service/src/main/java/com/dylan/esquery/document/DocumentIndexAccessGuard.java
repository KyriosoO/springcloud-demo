package com.dylan.esquery.document;

/** 将 Document alias/physical index 与通用 raw ES API 完全隔离。 */
public final class DocumentIndexAccessGuard {
    private final DocumentCorpusCatalog catalog;
    public DocumentIndexAccessGuard(DocumentCorpusCatalog catalog) { this.catalog = catalog; }
    public void requireGenericTarget(String target) {
        if (catalog.isDocumentTarget(target)) {
            throw new DocumentSpecializedEndpointRequiredException();
        }
    }
    public static final class DocumentSpecializedEndpointRequiredException extends IllegalArgumentException {
        public DocumentSpecializedEndpointRequiredException() { super("DOCUMENT_SPECIALIZED_ENDPOINT_REQUIRED"); }
    }
}
