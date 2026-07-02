package com.dylan.agent.metadata.config;

/** Optional listener invoked after a new metadata bundle is atomically published. */
public interface AgentMetadataRefreshListener {
    void onPublished(AgentMetadataBundle bundle);
}
