package com.dylan.documentprovider;

import com.dylan.agent.adapter.api.document.provider.*;

/** 每个 operation 仅允许一次 vendor 调用；实现不得重试或 fallback。 */
public interface DocumentVendorClient {
    DocumentUntrustedRewritePayload rewrite(DocumentRewriteInputProjection input, DocumentProviderBindingReference binding);
    DocumentUntrustedEmbeddingPayload embedding(DocumentEmbeddingInputProjection input, DocumentProviderBindingReference binding);
    DocumentUntrustedRerankPayload rerank(DocumentRerankInputProjection input, DocumentProviderBindingReference binding);
    DocumentUntrustedGenerationPayload generation(DocumentGenerationInputProjection input, DocumentProviderBindingReference binding);
}
