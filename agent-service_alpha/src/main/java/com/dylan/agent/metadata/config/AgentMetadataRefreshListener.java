package com.dylan.agent.metadata.config;

/** 新 metadata bundle 原子发布后的可选监听器。 */
public interface AgentMetadataRefreshListener {
    void onPublished(AgentMetadataBundle bundle);
}
