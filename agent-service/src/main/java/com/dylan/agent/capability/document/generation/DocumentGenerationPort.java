package com.dylan.agent.capability.document.generation;

import com.dylan.agent.adapter.api.document.generation.DocumentGenerationRequest;
import com.dylan.agent.adapter.api.document.generation.DocumentGenerationResult;

/** 文档执行后生成端口。 */
public interface DocumentGenerationPort {
    DocumentGenerationResult generate(DocumentGenerationRequest request);
}
