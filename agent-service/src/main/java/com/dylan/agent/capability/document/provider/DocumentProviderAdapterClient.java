package com.dylan.agent.capability.document.provider;

import com.dylan.agent.adapter.api.document.DocumentResourceLimit;
import com.dylan.agent.adapter.api.document.provider.*;
import com.dylan.agent.adapter.api.operation.*;
import com.dylan.agent.api.contract.common.AgentExecutionContracts;
import com.dylan.agent.capability.document.embedding.DocumentEmbeddingPort;
import com.dylan.agent.capability.document.generation.DocumentGenerationPort;
import com.dylan.agent.capability.document.governance.provider.DocumentProviderActivationReadView;
import com.dylan.agent.capability.document.rerank.DocumentRerankPort;
import com.dylan.agent.capability.document.rewrite.DocumentQueryRewritePort;
import org.springframework.core.ParameterizedTypeReference;
import org.springframework.http.HttpHeaders;
import org.springframework.http.MediaType;
import org.springframework.web.client.RestClient;
import org.springframework.web.client.RestClientException;

import com.fasterxml.jackson.databind.DeserializationFeature;
import com.fasterxml.jackson.databind.JavaType;
import com.fasterxml.jackson.databind.ObjectMapper;

import java.time.Clock;
import java.time.Duration;
import java.util.Optional;
import java.util.Set;
import java.util.UUID;
import java.util.stream.Collectors;

/** 四类 Document provider operation 的唯一 agent-side internal adapter client。 */
public final class DocumentProviderAdapterClient implements
        DocumentQueryRewritePort, DocumentEmbeddingPort, DocumentRerankPort, DocumentGenerationPort {
    private static final String WIRE_VERSION = "DPW-1";

    private final RestClient restClient;
    private final DocumentProviderAuthHeaderProvider authHeaderProvider;
    private final DocumentProviderActivationReadView activationReadView;
    private final DocumentProviderOperationRequestBinder binder;
    private final DocumentProviderOutboundPolicyReferenceVerifier referenceVerifier;
    private final DocumentProviderOperationBindingRegistry operationBindingRegistry;
    private final Clock clock;
    private final ObjectMapper strictMapper;

    public DocumentProviderAdapterClient(
            RestClient restClient,
            DocumentProviderAuthHeaderProvider authHeaderProvider,
            DocumentProviderActivationReadView activationReadView,
            DocumentProviderOperationRequestBinder binder,
            DocumentProviderOutboundPolicyReferenceVerifier referenceVerifier,
            DocumentProviderOperationBindingRegistry operationBindingRegistry,
            Clock clock,
            ObjectMapper objectMapper) {
        this.restClient = restClient;
        this.authHeaderProvider = authHeaderProvider;
        this.activationReadView = activationReadView;
        this.binder = binder;
        this.referenceVerifier = referenceVerifier;
        this.operationBindingRegistry = operationBindingRegistry;
        this.clock = clock;
        this.strictMapper = objectMapper.copy()
                .enable(DeserializationFeature.FAIL_ON_UNKNOWN_PROPERTIES)
                .enable(DeserializationFeature.FAIL_ON_TRAILING_TOKENS);
    }

    @Override
    public CapabilityOperationOutcome<DocumentUntrustedRewritePayload> rewrite(DocumentRewriteOperationRequest request) {
        Prepared<DocumentRewriteInputProjection> prepared = prepare(request.input(), request.outboundPolicyReference(), request.operationContext());
        if (prepared.failure != null) return castFailure(prepared.failure);
        DocumentResourceLimit limit = limits(request.operationContext());
        if (request.input().maxCandidates() > limit.enhancement().maxRewriteCandidates()) {
            return failure(request.operationContext(), prepared.snapshot, 0, CapabilityOperationFailureCode.LIMIT_EXCEEDED, CapabilityOperationTermination.REJECTED, prepared.startedNanos);
        }
        CapabilityOperationOutcome<DocumentUntrustedRewritePayload> outcome = invoke("/internal/document-providers/rewrite", prepared,
                new ParameterizedTypeReference<DocumentProviderWireResponse<DocumentUntrustedRewritePayload>>() {});
        if (outcome instanceof CapabilityOperationSuccess<DocumentUntrustedRewritePayload> success
                && (success.candidate().candidates().size() > request.input().maxCandidates()
                || success.candidate().candidates().stream().anyMatch(
                        value -> codePoints(value) > limit.input().maxQueryChars()))) {
            return failure(request.operationContext(), prepared.snapshot, 1,
                    CapabilityOperationFailureCode.INVALID_RESPONSE,
                    CapabilityOperationTermination.REJECTED, prepared.startedNanos);
        }
        return outcome;
    }

    @Override
    public CapabilityOperationOutcome<DocumentUntrustedEmbeddingPayload> embed(DocumentEmbeddingOperationRequest request) {
        Prepared<DocumentEmbeddingInputProjection> prepared = prepare(request.input(), request.outboundPolicyReference(), request.operationContext());
        if (prepared.failure != null) return castFailure(prepared.failure);
        DocumentResourceLimit limit = limits(request.operationContext());
        if (request.input().texts().size() > limit.enhancement().maxEmbeddingTexts()) {
            return failure(request.operationContext(), prepared.snapshot, 0, CapabilityOperationFailureCode.LIMIT_EXCEEDED, CapabilityOperationTermination.REJECTED, prepared.startedNanos);
        }
        CapabilityOperationOutcome<DocumentUntrustedEmbeddingPayload> outcome = invoke(
                "/internal/document-providers/embedding", prepared,
                new ParameterizedTypeReference<DocumentProviderWireResponse<DocumentUntrustedEmbeddingPayload>>() {});
        if (outcome instanceof CapabilityOperationSuccess<DocumentUntrustedEmbeddingPayload> success) {
            var payload = success.candidate();
            if (payload.vectors().size() != request.input().texts().size()
                    || payload.dimension() > limit.enhancement().maxEmbeddingDimensions()
                    || payload.vectors().stream().anyMatch(vector -> vector.size() != payload.dimension()
                    || vector.stream().anyMatch(value -> value == null || !Float.isFinite(value)))) {
                return failure(request.operationContext(), prepared.snapshot, 1, CapabilityOperationFailureCode.INVALID_RESPONSE, CapabilityOperationTermination.REJECTED, prepared.startedNanos);
            }
        }
        return outcome;
    }

    @Override
    public CapabilityOperationOutcome<DocumentUntrustedRerankPayload> rerank(DocumentRerankOperationRequest request) {
        Prepared<DocumentRerankInputProjection> prepared = prepare(request.input(), request.outboundPolicyReference(), request.operationContext());
        if (prepared.failure != null) return castFailure(prepared.failure);
        if (request.input().items().size() > limits(request.operationContext()).enhancement().maxRerankCandidates()) {
            return failure(request.operationContext(), prepared.snapshot, 0, CapabilityOperationFailureCode.LIMIT_EXCEEDED, CapabilityOperationTermination.REJECTED, prepared.startedNanos);
        }
        CapabilityOperationOutcome<DocumentUntrustedRerankPayload> outcome = invoke("/internal/document-providers/rerank", prepared,
                new ParameterizedTypeReference<DocumentProviderWireResponse<DocumentUntrustedRerankPayload>>() {});
        if (outcome instanceof CapabilityOperationSuccess<DocumentUntrustedRerankPayload> success) {
            Set<String> inputIds = request.input().items().stream()
                    .map(DocumentRerankInputProjection.DocumentRerankInputItem::candidateId)
                    .collect(Collectors.toUnmodifiableSet());
            if (success.candidate().scores().size() > request.input().items().size()
                    || success.candidate().scores().stream().anyMatch(score -> !inputIds.contains(score.candidateId()))) {
                return failure(request.operationContext(), prepared.snapshot, 1,
                        CapabilityOperationFailureCode.INVALID_RESPONSE,
                        CapabilityOperationTermination.REJECTED, prepared.startedNanos);
            }
        }
        return outcome;
    }

    @Override
    public CapabilityOperationOutcome<DocumentUntrustedGenerationPayload> generate(DocumentGenerationOperationRequest request) {
        Prepared<DocumentGenerationInputProjection> prepared = prepare(request.input(), request.outboundPolicyReference(), request.operationContext());
        if (prepared.failure != null) return castFailure(prepared.failure);
        DocumentResourceLimit limit = limits(request.operationContext());
        int evidenceChars;
        try {
            evidenceChars = request.input().evidence().stream().mapToInt(item -> codePoints(item.text()))
                    .reduce(0, Math::addExact);
        } catch (ArithmeticException ex) {
            return failure(request.operationContext(), prepared.snapshot, 0,
                    CapabilityOperationFailureCode.LIMIT_EXCEEDED,
                    CapabilityOperationTermination.REJECTED, prepared.startedNanos);
        }
        if (request.input().evidence().size() > limit.output().maxEvidenceCount()
                || evidenceChars > limit.output().maxContextChars()
                || evidenceChars > limit.output().maxEvidenceChars()) {
            return failure(request.operationContext(), prepared.snapshot, 0, CapabilityOperationFailureCode.LIMIT_EXCEEDED, CapabilityOperationTermination.REJECTED, prepared.startedNanos);
        }
        CapabilityOperationOutcome<DocumentUntrustedGenerationPayload> outcome = invoke("/internal/document-providers/generation", prepared,
                new ParameterizedTypeReference<DocumentProviderWireResponse<DocumentUntrustedGenerationPayload>>() {});
        if (outcome instanceof CapabilityOperationSuccess<DocumentUntrustedGenerationPayload> success
                && !validGenerationPayload(success.candidate(), limit)) {
            return failure(request.operationContext(), prepared.snapshot, 1,
                    CapabilityOperationFailureCode.INVALID_RESPONSE,
                    CapabilityOperationTermination.REJECTED, prepared.startedNanos);
        }
        return outcome;
    }

    private <I> Prepared<I> prepare(
            I input,
            DocumentProviderOutboundPolicyReference reference,
            CapabilityOperationContext context) {
        long started = System.nanoTime();
        if (input == null || reference == null || context == null) {
            return Prepared.failed(failure(context, null, 0, CapabilityOperationFailureCode.INVALID_REQUEST,
                    CapabilityOperationTermination.REJECTED, started), started);
        }
        if (context.cancellation().isCancelled()) {
            return Prepared.failed(failure(context, null, 0, CapabilityOperationFailureCode.CANCELLED,
                    CapabilityOperationTermination.CANCELLED, started), started);
        }
        if (!clock.instant().isBefore(context.absoluteDeadline())) {
            return Prepared.failed(failure(context, null, 0, CapabilityOperationFailureCode.DEADLINE_EXCEEDED,
                    CapabilityOperationTermination.DEADLINE_EXCEEDED, started), started);
        }
        if (!referenceVerifier.verify(reference, input, context)) {
            return Prepared.failed(failure(context, null, 0, CapabilityOperationFailureCode.BINDING_MISMATCH,
                    CapabilityOperationTermination.REJECTED, started), started);
        }
        DocumentProviderActivationSnapshot snapshot;
        try {
            snapshot = activationReadView.requireCurrent(context.operationType());
        } catch (RuntimeException ex) {
            return Prepared.failed(failure(context, null, 0, CapabilityOperationFailureCode.PROVIDER_UNAVAILABLE,
                    CapabilityOperationTermination.FAILED, started), started);
        }
        if (snapshot.state() != DocumentProviderActivationState.ACTIVE) {
            return Prepared.failed(failure(context, snapshot, 0, CapabilityOperationFailureCode.DISABLED,
                    CapabilityOperationTermination.DISABLED, started), started);
        }
        if (snapshot.expectedProvider().isEmpty() || !clock.instant().isBefore(snapshot.validUntil())) {
            return Prepared.failed(failure(context, snapshot, 0, CapabilityOperationFailureCode.PROVIDER_UNAVAILABLE,
                    CapabilityOperationTermination.FAILED, started), started);
        }
        String requestDigest = binder.wireRequestDigest(WIRE_VERSION, context, snapshot.canonicalDigest(),
                snapshot.expectedProvider().orElseThrow().canonicalDigest(), input);
        return Prepared.ready(input, context, snapshot, requestDigest, started);
    }

    private <I, O> CapabilityOperationOutcome<O> invoke(
            String endpoint,
            Prepared<I> prepared,
            ParameterizedTypeReference<DocumentProviderWireResponse<O>> responseType) {
        CapabilityOperationContext context = prepared.context;
        if (context.cancellation().isCancelled() || !clock.instant().isBefore(context.absoluteDeadline())) {
            return failure(context, prepared.snapshot, 0,
                    context.cancellation().isCancelled() ? CapabilityOperationFailureCode.CANCELLED : CapabilityOperationFailureCode.DEADLINE_EXCEEDED,
                    context.cancellation().isCancelled() ? CapabilityOperationTermination.CANCELLED : CapabilityOperationTermination.DEADLINE_EXCEEDED,
                    prepared.startedNanos);
        }
        DocumentProviderActivationSnapshot latest;
        try {
            latest = activationReadView.requireCurrent(context.operationType());
        } catch (RuntimeException ex) {
            return failure(context, prepared.snapshot, 0, CapabilityOperationFailureCode.PROVIDER_UNAVAILABLE,
                    CapabilityOperationTermination.FAILED, prepared.startedNanos);
        }
        if (!latest.canonicalDigest().equals(prepared.snapshot.canonicalDigest())) {
            return failure(context, prepared.snapshot, 0, CapabilityOperationFailureCode.BINDING_MISMATCH,
                    CapabilityOperationTermination.REJECTED, prepared.startedNanos);
        }
        DocumentProviderWireRequest<I> wireRequest = new DocumentProviderWireRequest<>(
                WIRE_VERSION, context.operationId(), context.operationType(), prepared.requestDigest,
                context.absoluteDeadline().toEpochMilli(), prepared.snapshot.canonicalDigest(),
                prepared.snapshot.expectedProvider().orElseThrow().canonicalDigest(), prepared.input);
        try {
            long responseLimit = limits(context).output().maxResultBytes();
            WireExchange<O> exchange = restClient.post()
                    .uri(endpoint)
                    .header(HttpHeaders.AUTHORIZATION, authHeaderProvider.authorizationHeader())
                    .header("X-Agent-Operation-Id", context.operationId())
                    .body(wireRequest)
                    .exchange((request, response) -> readExchange(response, responseType, responseLimit));
            CapabilityOperationFailure<O> boundaryFailure = postExchangeBoundaryFailure(prepared);
            if (boundaryFailure != null) return boundaryFailure;
            if (exchange == null || !exchange.json) {
                return failure(context, prepared.snapshot, 1,
                        exchange != null && (exchange.status == 401 || exchange.status == 403)
                                ? CapabilityOperationFailureCode.SECURITY_REJECTED
                                : CapabilityOperationFailureCode.INVALID_RESPONSE,
                        CapabilityOperationTermination.REJECTED, prepared.startedNanos);
            }
            if (exchange.error != null) {
                return mapWireError(prepared, exchange.error);
            }
            DocumentProviderWireResponse<O> response = exchange.success;
            if (response == null || response.payload() == null
                    || !WIRE_VERSION.equals(response.wireContractVersion())
                    || !context.operationId().equals(response.operationId())
                    || !context.operationType().equals(response.operationType())
                    || !prepared.requestDigest.equals(response.requestDigest())
                    || !prepared.snapshot.canonicalDigest().equals(response.activationDigest())
                    || !prepared.snapshot.expectedProvider().orElseThrow().equals(response.providerBinding())) {
                return failure(context, prepared.snapshot, 1, CapabilityOperationFailureCode.INVALID_RESPONSE,
                        CapabilityOperationTermination.REJECTED, prepared.startedNanos);
            }
            operationBindingRegistry.publish(
                    context.operationId(), prepared.snapshot.expectedProvider().orElseThrow(),
                    context.absoluteDeadline());
            return new CapabilityOperationSuccess<>(response.payload(), metadata(
                    context, prepared.snapshot, 1, CapabilityOperationTermination.SUCCEEDED,
                    diagnosticId(), prepared.startedNanos));
        } catch (RestClientException ex) {
            return failure(context, prepared.snapshot, 1, CapabilityOperationFailureCode.PROVIDER_FAILED,
                    CapabilityOperationTermination.FAILED, prepared.startedNanos);
        } catch (RuntimeException ex) {
            return failure(context, prepared.snapshot, 1, CapabilityOperationFailureCode.INVALID_RESPONSE,
                    CapabilityOperationTermination.REJECTED, prepared.startedNanos);
        }
    }

    private <O> WireExchange<O> readExchange(
            org.springframework.http.client.ClientHttpResponse response,
            ParameterizedTypeReference<DocumentProviderWireResponse<O>> responseType,
            long maxBytes) throws java.io.IOException {
        int status = response.getStatusCode().value();
        MediaType contentType = response.getHeaders().getContentType();
        if (status == 401 || status == 403) return new WireExchange<>(status, false, null, null);
        if (contentType == null || !MediaType.APPLICATION_JSON.isCompatibleWith(contentType)) {
            return new WireExchange<>(status, false, null, null);
        }
        int bounded = (int) Math.min(maxBytes, Integer.MAX_VALUE - 1L);
        byte[] body = response.getBody().readNBytes(bounded + 1);
        if (body.length > bounded || body.length == 0) throw new IllegalArgumentException("provider response size invalid");
        if (response.getStatusCode().is2xxSuccessful()) {
            JavaType type = strictMapper.getTypeFactory().constructType(responseType.getType());
            return new WireExchange<>(status, true, strictMapper.readValue(body, type), null);
        }
        return new WireExchange<>(status, true, null,
                strictMapper.readValue(body, DocumentProviderWireError.class));
    }

    private <O> CapabilityOperationFailure<O> postExchangeBoundaryFailure(Prepared<?> prepared) {
        CapabilityOperationContext context = prepared.context;
        if (context.cancellation().isCancelled()) {
            return failure(context, prepared.snapshot, 1, CapabilityOperationFailureCode.CANCELLED,
                    CapabilityOperationTermination.CANCELLED, prepared.startedNanos);
        }
        if (!clock.instant().isBefore(context.absoluteDeadline())) {
            return failure(context, prepared.snapshot, 1, CapabilityOperationFailureCode.LATE_RESULT,
                    CapabilityOperationTermination.DEADLINE_EXCEEDED, prepared.startedNanos);
        }
        try {
            DocumentProviderActivationSnapshot after = activationReadView.requireCurrent(context.operationType());
            if (!after.canonicalDigest().equals(prepared.snapshot.canonicalDigest())) {
                return failure(context, prepared.snapshot, 1, CapabilityOperationFailureCode.BINDING_MISMATCH,
                        CapabilityOperationTermination.REJECTED, prepared.startedNanos);
            }
        } catch (RuntimeException ex) {
            return failure(context, prepared.snapshot, 1, CapabilityOperationFailureCode.BINDING_MISMATCH,
                    CapabilityOperationTermination.REJECTED, prepared.startedNanos);
        }
        return null;
    }

    private <O> CapabilityOperationFailure<O> mapWireError(
            Prepared<?> prepared,
            DocumentProviderWireError error) {
        CapabilityOperationContext context = prepared.context;
        if (!WIRE_VERSION.equals(error.wireContractVersion())
                || !context.operationId().equals(error.operationId())
                || !context.operationType().equals(error.operationType())
                || !prepared.requestDigest.equals(error.requestDigest())) {
            return failure(context, prepared.snapshot, 1, CapabilityOperationFailureCode.INVALID_RESPONSE,
                    CapabilityOperationTermination.REJECTED, prepared.startedNanos);
        }
        CapabilityOperationFailureCode code;
        CapabilityOperationTermination termination;
        switch (error.failureCode()) {
            case REQUEST_REJECTED, ACTIVATION_REJECTED -> {
                code = CapabilityOperationFailureCode.BINDING_MISMATCH;
                termination = CapabilityOperationTermination.REJECTED;
            }
            case DEADLINE_REJECTED -> {
                code = clock.instant().isBefore(context.absoluteDeadline())
                        ? CapabilityOperationFailureCode.LATE_RESULT
                        : CapabilityOperationFailureCode.DEADLINE_EXCEEDED;
                termination = CapabilityOperationTermination.DEADLINE_EXCEEDED;
            }
            case REQUEST_ABORTED -> {
                code = context.cancellation().isCancelled()
                        ? CapabilityOperationFailureCode.CANCELLED
                        : CapabilityOperationFailureCode.PROVIDER_FAILED;
                termination = context.cancellation().isCancelled()
                        ? CapabilityOperationTermination.CANCELLED
                        : CapabilityOperationTermination.FAILED;
            }
            case VENDOR_UNAVAILABLE -> {
                code = CapabilityOperationFailureCode.PROVIDER_UNAVAILABLE;
                termination = CapabilityOperationTermination.FAILED;
            }
            case VENDOR_TIMEOUT -> {
                code = CapabilityOperationFailureCode.PROVIDER_TIMEOUT;
                termination = CapabilityOperationTermination.FAILED;
            }
            case VENDOR_INVALID_RESPONSE -> {
                code = CapabilityOperationFailureCode.INVALID_RESPONSE;
                termination = CapabilityOperationTermination.REJECTED;
            }
            case VENDOR_FAILED -> {
                code = CapabilityOperationFailureCode.PROVIDER_FAILED;
                termination = CapabilityOperationTermination.FAILED;
            }
            default -> {
                code = CapabilityOperationFailureCode.INVALID_RESPONSE;
                termination = CapabilityOperationTermination.REJECTED;
            }
        }
        return failure(context, prepared.snapshot, 1, code, termination, prepared.startedNanos);
    }

    private DocumentResourceLimit limits(CapabilityOperationContext context) {
        return context.resourceLimits().require(AgentExecutionContracts.DOCUMENT_RESOURCE_LIMIT, DocumentResourceLimit.class);
    }

    private static boolean validGenerationPayload(
            DocumentUntrustedGenerationPayload payload,
            DocumentResourceLimit limit) {
        try {
            int answerChars = codePoints(payload.answerText());
            int summaryChars = codePoints(payload.summaryText());
            for (String bullet : payload.summaryBullets()) summaryChars = Math.addExact(summaryChars, codePoints(bullet));
            return answerChars <= limit.output().maxGeneratedChars()
                    && summaryChars <= limit.output().maxGeneratedChars()
                    && summaryChars <= limit.output().maxSummaryChars()
                    && payload.summaryBullets().size() <= limit.output().maxSummaryBullets()
                    && payload.citedIds().size() <= limit.output().maxCitationCount();
        } catch (ArithmeticException ex) {
            return false;
        }
    }

    private static int codePoints(String value) {
        return value == null ? 0 : value.codePointCount(0, value.length());
    }

    private <T> CapabilityOperationFailure<T> failure(
            CapabilityOperationContext context,
            DocumentProviderActivationSnapshot snapshot,
            int attempts,
            CapabilityOperationFailureCode code,
            CapabilityOperationTermination termination,
            long startedNanos) {
        String diagnosticId = diagnosticId();
        return new CapabilityOperationFailure<>(code, diagnosticId,
                metadata(context, snapshot, attempts, termination, diagnosticId, startedNanos));
    }

    private CapabilityOperationMetadata metadata(
            CapabilityOperationContext context,
            DocumentProviderActivationSnapshot snapshot,
            int attempts,
            CapabilityOperationTermination termination,
            String diagnosticId,
            long startedNanos) {
        ProviderSafeIdentity provider = snapshot == null || snapshot.expectedProvider().isEmpty()
                ? new ProviderSafeIdentity("unbound", Optional.empty())
                : snapshot.expectedProvider().orElseThrow().provider();
        return new CapabilityOperationMetadata(
                context == null ? "unbound" : context.operationId(),
                context == null ? CapabilityOperationType.of("UNKNOWN") : context.operationType(),
                provider, attempts, Duration.ofNanos(System.nanoTime() - startedNanos).toMillis(), termination,
                diagnosticId, context == null ? unavailableLimitReference() : context.resourceLimits().reference(),
                false, termination == CapabilityOperationTermination.DEADLINE_EXCEEDED,
                termination == CapabilityOperationTermination.CANCELLED);
    }

    private static ResourceLimitReference unavailableLimitReference() {
        return new ResourceLimitReference(AgentExecutionContracts.DOCUMENT_RESOURCE_LIMIT,
                "0".repeat(64), "unbound", "unbound");
    }

    @SuppressWarnings("unchecked")
    private static <T> CapabilityOperationFailure<T> castFailure(CapabilityOperationFailure<?> failure) {
        return (CapabilityOperationFailure<T>) failure;
    }

    private static String diagnosticId() { return "doc-provider-" + UUID.randomUUID().toString().replace("-", ""); }

    private static final class Prepared<I> {
        private final I input;
        private final CapabilityOperationContext context;
        private final DocumentProviderActivationSnapshot snapshot;
        private final String requestDigest;
        private final CapabilityOperationFailure<?> failure;
        private final long startedNanos;

        private Prepared(I input, CapabilityOperationContext context, DocumentProviderActivationSnapshot snapshot,
                         String requestDigest, CapabilityOperationFailure<?> failure, long startedNanos) {
            this.input = input; this.context = context; this.snapshot = snapshot;
            this.requestDigest = requestDigest; this.failure = failure; this.startedNanos = startedNanos;
        }
        private static <I> Prepared<I> ready(I input, CapabilityOperationContext context,
                                             DocumentProviderActivationSnapshot snapshot, String requestDigest,
                                             long startedNanos) {
            return new Prepared<>(input, context, snapshot, requestDigest, null, startedNanos);
        }
        private static <I> Prepared<I> failed(CapabilityOperationFailure<?> failure, long startedNanos) {
            return new Prepared<>(null, null, null, null, failure, startedNanos);
        }
    }

    private record WireExchange<O>(int status, boolean json,
                                   DocumentProviderWireResponse<O> success,
                                   DocumentProviderWireError error) {}
}
