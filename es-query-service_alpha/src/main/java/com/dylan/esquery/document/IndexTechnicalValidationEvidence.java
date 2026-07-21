package com.dylan.esquery.document;

import java.util.List;

/** 交给 07 的技术验证事实；不表示 release approval。 */
public record IndexTechnicalValidationEvidence(
        DocumentPhysicalIndexManifest manifest,
        boolean mappingValid,
        boolean aclValid,
        boolean vectorValid,
        boolean countValid,
        List<String> diagnosticRefs) {
    public IndexTechnicalValidationEvidence { diagnosticRefs = List.copyOf(diagnosticRefs == null ? List.of() : diagnosticRefs); }
    public boolean passed() { return mappingValid && aclValid && vectorValid && countValid; }
}
