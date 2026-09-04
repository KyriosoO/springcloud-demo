package com.dylan.agent.service.runtime;

import com.dylan.agent.service.contract.RuntimeInspectResponse;
import com.dylan.agent.service.contract.RuntimeInvokeRequest;

import reactor.core.publisher.Mono;

public interface AgentRuntimeInspectionClient {
    Mono<RuntimeInspectResponse> inspect(RuntimeInvokeRequest request, String rawUserToken);
}
