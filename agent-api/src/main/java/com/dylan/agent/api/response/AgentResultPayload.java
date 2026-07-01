package com.dylan.agent.api.response;

import com.dylan.agent.api.enums.AgentResultKind;

/**
 * Single extension point for successful Agent result payloads.
 *
 * <p>New result shapes extend this Java sealed hierarchy instead of adding
 * parallel fields to {@link AgentChatResponse}.
 */
public sealed interface AgentResultPayload
        permits QueryAgentResultPayload, AggregateAgentResultPayload {

    AgentResultKind getResultKind();
}
