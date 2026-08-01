package com.dylan.agent.service.runtime;

import com.dylan.agent.service.contract.RuntimeInvokeRequest;
import com.dylan.agent.service.contract.RuntimeInvokeResponse;

import reactor.core.publisher.Mono;

public interface AgentRuntimeClient {
    Mono<RuntimeInvokeResponse> invoke(RuntimeInvokeRequest request, String rawUserToken);
}
