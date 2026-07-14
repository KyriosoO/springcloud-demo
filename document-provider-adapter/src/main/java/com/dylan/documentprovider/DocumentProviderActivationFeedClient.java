package com.dylan.documentprovider;

import com.dylan.agent.adapter.api.document.provider.DocumentProviderActivationSnapshot;
import com.dylan.agent.adapter.api.document.provider.DocumentProviderCanonicalizer;
import com.dylan.agent.adapter.api.operation.CapabilityOperationType;
import com.dylan.common.security.ServiceTokenProvider;
import org.springframework.http.HttpHeaders;
import org.springframework.core.ParameterizedTypeReference;
import org.springframework.scheduling.annotation.Scheduled;
import org.springframework.stereotype.Component;
import org.springframework.web.client.RestClient;
import java.time.Instant;
import java.util.*;

/** 从 07 authority 刷新完整 immutable snapshot；失败时不延长 ACTIVE。 */
@Component
final class DocumentProviderActivationFeedClient {
    private final RestClient client;
    private final DocumentProviderActivationReadView readView;
    private final DocumentProviderActivationFeedProperties properties;
    private final ServiceTokenProvider serviceTokenProvider;
    private final DocumentProviderCanonicalizer canonicalizer;

    DocumentProviderActivationFeedClient(DocumentProviderActivationReadView readView,
                                         DocumentProviderActivationFeedProperties properties,
                                         ServiceTokenProvider serviceTokenProvider,
                                         DocumentProviderCanonicalizer canonicalizer) {
        this.readView = readView;
        this.properties = properties;
        this.serviceTokenProvider = serviceTokenProvider;
        this.canonicalizer = canonicalizer;
        this.client = RestClient.builder().baseUrl(properties.getBaseUrl()).build();
    }

    @Scheduled(fixedDelayString = "${document-provider.activation-feed.refresh-delay:1s}")
    void refresh() {
        try {
            List<DocumentProviderActivationSnapshot> snapshots = client.get()
                    .uri("/internal/document-governance/provider-activations")
                    .header(HttpHeaders.AUTHORIZATION, "Bearer " + serviceTokenProvider.token())
                    .retrieve().body(new ParameterizedTypeReference<>() {});
            if (snapshots == null) throw new IllegalStateException("activation feed empty");
            Instant freshness = Instant.now().plus(properties.getMaxDistributionStaleness());
            Map<CapabilityOperationType, DocumentProviderActivationSnapshot> next = new LinkedHashMap<>();
            for (DocumentProviderActivationSnapshot snapshot : snapshots) {
                if (snapshot == null || snapshot.operationType() == null || snapshot.canonicalDigest() == null
                        || !snapshot.canonicalDigest().matches("[0-9a-f]{64}")
                        || snapshot.expectedProvider().filter(value -> !value.canonicalDigest().equals(
                        canonicalizer.providerBindingDigest(value))).isPresent()
                        || !snapshot.canonicalDigest().equals(canonicalizer.activationSnapshotDigest(snapshot))) {
                    throw new IllegalStateException("invalid snapshot");
                }
                if (next.putIfAbsent(snapshot.operationType(), snapshot) != null) throw new IllegalStateException("duplicate operation");
            }
            readView.replace(next, freshness);
            for (DocumentProviderActivationSnapshot snapshot : next.values()) {
                client.post().uri("/internal/document-governance/provider-activations/ack")
                        .header(HttpHeaders.AUTHORIZATION, "Bearer " + serviceTokenProvider.token())
                        .body(new Ack(properties.getConsumerId(), snapshot.operationType(),
                                properties.getDeploymentDigest(), snapshot.canonicalDigest()))
                        .retrieve().toBodilessEntity();
            }
        } catch (RuntimeException ex) {
            readView.replace(Map.of());
        }
    }

    private record Ack(String consumerId, CapabilityOperationType operationType,
                       String deploymentDigest, String activationDigest) {}
}
