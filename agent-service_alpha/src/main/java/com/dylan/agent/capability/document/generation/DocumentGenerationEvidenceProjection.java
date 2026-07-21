package com.dylan.agent.capability.document.generation;

import java.util.List;

/** Provider 外发证据的 all-or-none 有序投影及其实际资源使用量。 */
public record DocumentGenerationEvidenceProjection(
        List<GenerationEvidencePackageItem> items,
        DocumentEvidenceUsage usage) {
    public DocumentGenerationEvidenceProjection {
        items = List.copyOf(items);
        if (usage == null || usage.itemCount() != items.size()) {
            throw new IllegalArgumentException("generation evidence projection usage mismatch");
        }
    }
}
