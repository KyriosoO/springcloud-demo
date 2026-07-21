package com.dylan.agent.metadata.config;

/** 启动首个不可变 metadata bundle 的 marker seam。 */
public interface AgentMetadataBootstrap {
    AgentMetadataBundle bootstrap();
}
