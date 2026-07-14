package com.dylan.esquery.document;

import com.dylan.esquery.api.model.DocumentCorpusKeyDto;
import com.dylan.esquery.api.model.DocumentTargetBindingDto;

/** 单次 hybrid request 解析并冻结的唯一 sealed+attested physical target。 */
public record ResolvedIndexTargetRef(
        DocumentCorpusKeyDto corpusKey,
        String alias,
        String physicalIndex,
        DocumentTargetBindingDto binding,
        String validationReportRef,
        String vectorField,
        Integer vectorDimension,
        String vectorBindingDigest) {
    public ResolvedIndexTargetRef {
        if (corpusKey == null || binding == null || alias == null || alias.isBlank()
                || physicalIndex == null || physicalIndex.isBlank()
                || validationReportRef == null || validationReportRef.isBlank()) {
            throw new IllegalArgumentException("resolved document target binding must be complete");
        }
        boolean anyVector = vectorField != null || vectorDimension != null || vectorBindingDigest != null;
        if (anyVector && (vectorField == null || vectorField.isBlank() || vectorDimension == null || vectorDimension <= 0
                || vectorBindingDigest == null || !vectorBindingDigest.matches("[0-9a-f]{64}"))) {
            throw new IllegalArgumentException("resolved document vector binding is incomplete");
        }
    }
}
