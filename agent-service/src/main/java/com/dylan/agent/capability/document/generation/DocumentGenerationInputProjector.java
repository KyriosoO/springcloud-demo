package com.dylan.agent.capability.document.generation;

import com.dylan.agent.adapter.api.document.provider.DocumentGenerationEvidenceItem;
import com.dylan.agent.adapter.api.document.provider.DocumentGenerationInputProjection;
import com.dylan.agent.adapter.api.document.provider.DocumentGenerationInstructionCode;
import com.dylan.agent.adapter.api.document.provider.DocumentGenerationOutputShape;

/** 从 ECP 投影唯一 Provider wire 输入，不携带 identity/security sidecar。 */
public final class DocumentGenerationInputProjector {
    public DocumentGenerationInputProjection project(
            EvidenceContextPackage context,
            DocumentGenerationInstructionCode instruction,
            DocumentGenerationOutputShape outputShape) {
        var evidence = context.items().stream()
                .map(item -> new DocumentGenerationEvidenceItem(
                        item.citationId(), item.outboundTitle(), item.outboundSection(),
                        item.outboundPage(), item.outboundText()))
                .toList();
        return new DocumentGenerationInputProjection(
                context.packageId(), context.canonicalDigest(), context.operation(),
                instruction, evidence, outputShape);
    }
}
