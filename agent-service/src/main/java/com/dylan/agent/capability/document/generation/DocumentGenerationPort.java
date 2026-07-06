package com.dylan.agent.capability.document.generation;

/** 文档执行后生成端口。 */
public interface DocumentGenerationPort {
    DocumentGenerationResult generate(DocumentGenerationRequest request);
}
