package com.dylan.esquery.document;

import java.util.List;

/** 稳定 keyset 分页结果。complete=true 时 nextCursor 必须为空。 */
public record DocumentSourcePage(List<SourceDocument> documents, ProtectedSourceCursor nextCursor, boolean complete) {
    public DocumentSourcePage {
        documents = List.copyOf(documents == null ? List.of() : documents);
        nextCursor = nextCursor == null ? new ProtectedSourceCursor(null) : nextCursor;
        if (complete && !nextCursor.isInitial()) throw new IllegalArgumentException("complete page must not contain next cursor");
        if (!complete && nextCursor.isInitial()) throw new IllegalArgumentException("non-terminal page requires next cursor");
    }
}
