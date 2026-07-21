package com.dylan.documentprovider;

import com.dylan.agent.adapter.api.document.provider.*;
import org.springframework.stereotype.Component;

/** 未装配受审 vendor client 时保持 fail closed，不能从配置自动激活。 */
@Component
final class UnavailableDocumentVendorClient implements DocumentVendorClient {
    @Override public DocumentUntrustedRewritePayload rewrite(DocumentRewriteInputProjection input, DocumentProviderBindingReference binding) { throw new VendorUnavailableException(); }
    @Override public DocumentUntrustedEmbeddingPayload embedding(DocumentEmbeddingInputProjection input, DocumentProviderBindingReference binding) { throw new VendorUnavailableException(); }
    @Override public DocumentUntrustedRerankPayload rerank(DocumentRerankInputProjection input, DocumentProviderBindingReference binding) { throw new VendorUnavailableException(); }
    @Override public DocumentUntrustedGenerationPayload generation(DocumentGenerationInputProjection input, DocumentProviderBindingReference binding) { throw new VendorUnavailableException(); }
    static final class VendorUnavailableException extends RuntimeException {}
}
