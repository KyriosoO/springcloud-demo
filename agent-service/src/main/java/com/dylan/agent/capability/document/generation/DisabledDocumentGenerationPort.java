package com.dylan.agent.capability.document.generation;

import com.dylan.agent.adapter.api.document.generation.DocumentGenerationRequest;
import com.dylan.agent.adapter.api.document.generation.DocumentGenerationResult;

/** 默认关闭的文档生成端口，防止未配置 provider 时误调用。 */
public final class DisabledDocumentGenerationPort implements DocumentGenerationPort {
    @Override
    public DocumentGenerationResult generate(DocumentGenerationRequest request) {
        throw new IllegalStateException("document generation is disabled");
    }
}
