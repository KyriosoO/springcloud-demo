package com.dylan.agent.service.application;

import java.time.Duration;
import java.util.concurrent.TimeoutException;

import com.dylan.agent.service.config.AgentIngressProperties;
import com.dylan.agent.service.config.AgentRuntimeProperties;
import com.dylan.agent.service.contract.AgentRunResponse;
import com.dylan.agent.service.contract.CapabilityStatus;
import com.dylan.agent.service.contract.FailureResponse;
import com.dylan.agent.service.contract.FailureSource;
import com.dylan.agent.service.contract.RuntimeInspectResponse;
import com.dylan.agent.service.contract.RuntimeInvokeRequest;
import com.dylan.agent.service.contract.RuntimeSubject;
import com.dylan.agent.service.runtime.AgentRuntimeInspectionClient;
import com.dylan.agent.service.runtime.RuntimeClientException;
import com.dylan.agent.service.security.AgentUserContext;
import com.dylan.agent.service.security.AgentUserContextFactory;
import com.dylan.agent.service.web.AgentRequestMetadata;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.security.oauth2.jwt.Jwt;
import org.springframework.stereotype.Service;

import reactor.core.publisher.Mono;

@Service
public final class AgentRunApplicationService {
    private static final Logger LOGGER = LoggerFactory.getLogger(AgentRunApplicationService.class);
    private final AgentClocks clocks;
    private final AgentIngressProperties ingress;
    private final AgentRequestLimiter limiter;
    private final AgentQuestionValidator questionValidator;
    private final AgentRuntimeInspectionClient runtimeClient;
    private final int runtimeContractVersion;
    private final AgentUserContextFactory userContextFactory;

    public AgentRunApplicationService(
            AgentUserContextFactory userContextFactory,
            AgentQuestionValidator questionValidator,
            AgentRequestLimiter limiter,
            AgentRuntimeInspectionClient runtimeClient,
            AgentIngressProperties ingress,
            AgentRuntimeProperties runtimeProperties,
            AgentClocks clocks) {
        this.userContextFactory = userContextFactory;
        this.questionValidator = questionValidator;
        this.limiter = limiter;
        this.runtimeClient = runtimeClient;
        this.ingress = ingress;
        this.runtimeContractVersion = runtimeProperties.contractVersion();
        this.clocks = clocks;
    }

    public Mono<AgentRunResponse> inspect(AgentQueryCommand command, Jwt jwt, AgentRequestMetadata metadata) {
        return Mono.defer(() -> inspectDeferred(command, jwt, metadata));
    }

    private Mono<AgentRunResponse> inspectDeferred(
            AgentQueryCommand command,
            Jwt jwt,
            AgentRequestMetadata metadata) {
        if (command == null || metadata == null) {
            return Mono.error(AgentPublicException.invalidRequest());
        }
        AgentUserContext user = userContextFactory.requireUser(jwt);
        String question = questionValidator.normalize(command.question());
        AgentRequestLimiter.Lease lease = limiter.tryAcquire();
        long startedNanos = clocks.monotonicNanos();
        long hardDeadlineNanos = metadata.receivedMonotonicNanos() + ingress.totalTimeout().toNanos();
        long hardRemainingMillis = (hardDeadlineNanos - startedNanos) / 1_000_000;
        long reserveMillis = ingress.responseReserve().toMillis();
        if (hardRemainingMillis <= reserveMillis) {
            lease.close();
            return Mono.error(AgentPublicException.runtimeTimeout());
        }
        long runtimeRemaining = hardRemainingMillis - reserveMillis;
        int runtimeRemainingMillis = Math.toIntExact(Math.min(runtimeRemaining, 120_000));
        try {
            RuntimeInvokeRequest request = new RuntimeInvokeRequest(
                    runtimeContractVersion,
                    metadata.requestId(),
                    metadata.correlationId(),
                    question,
                    new RuntimeSubject(user.subjectId(), "user"),
                    clocks.epochMillis() + runtimeRemainingMillis,
                    runtimeRemainingMillis);
            return runtimeClient.inspect(request, user.rawTokenForRuntime())
                    .map(response -> mapResponse(response, metadata))
                    .timeout(Duration.ofMillis(hardRemainingMillis))
                    .onErrorResume(RuntimeClientException.class,
                            failure -> Mono.just(fromRuntimeFailure(failure, metadata)))
                    .onErrorResume(TimeoutException.class,
                            failure -> Mono.just(fixedFailure(
                                    metadata, CapabilityStatus.TIMEOUT,
                                    "downstream.runtime_timeout", FailureSource.DOWNSTREAM)))
                    .doOnNext(response -> LOGGER.info(
                            "agent_run_inspection_completed requestId={} correlationId={} status={} durationMs={}",
                            metadata.requestId(), metadata.correlationId(), response.status().wireValue(),
                            Math.max(0L, (clocks.monotonicNanos() - startedNanos) / 1_000_000)))
                    .doFinally(signal -> lease.close());
        } catch (RuntimeException failure) {
            lease.close();
            return Mono.error(failure);
        }
    }

    private AgentRunResponse mapResponse(
            RuntimeInspectResponse response,
            AgentRequestMetadata metadata) {
        return new AgentRunResponse(
                metadata.requestId(), metadata.correlationId(), response.status(),
                response.modelCalls(), response.plans(), response.downstreamCalls(),
                response.capabilityId(), response.answerText(), response.userResult(), response.failure());
    }

    private AgentRunResponse fromRuntimeFailure(
            RuntimeClientException failure,
            AgentRequestMetadata metadata) {
        return fixedFailure(metadata, failure.status(), failure.code(), failure.source());
    }

    private AgentRunResponse fixedFailure(
            AgentRequestMetadata metadata,
            CapabilityStatus status,
            String code,
            FailureSource source) {
        return new AgentRunResponse(
                metadata.requestId(), metadata.correlationId(), status,
                java.util.List.of(), java.util.List.of(), java.util.List.of(), null,
                fixedAnswer(status), null, new FailureResponse(code, source));
    }

    private String fixedAnswer(CapabilityStatus status) {
        return switch (status) {
            case UNAUTHENTICATED -> "用户身份无效。";
            case TIMEOUT -> "查询超时。";
            case DOWNSTREAM_FAILURE -> "下游查询暂时不可用。";
            case INTERNAL_FAILURE -> "查询处理失败。";
            default -> "查询处理失败。";
        };
    }
}
