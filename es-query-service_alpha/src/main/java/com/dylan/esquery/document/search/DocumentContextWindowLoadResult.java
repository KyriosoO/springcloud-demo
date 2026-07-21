package com.dylan.esquery.document.search;

import com.dylan.esquery.api.model.document.HybridSearchHit;

import java.util.List;

/** 单次上下文批量扩展结果。 */
public record DocumentContextWindowLoadResult(List<HybridSearchHit> hits, boolean truncated) {
    public DocumentContextWindowLoadResult {
        hits = List.copyOf(hits == null ? List.of() : hits);
    }
}
