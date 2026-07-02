package com.dylan.agent.metadata.config;

/** Marker seam for bootstrapping the first immutable metadata bundle. */
public interface AgentMetadataBootstrap {
    AgentMetadataBundle bootstrap();
}
