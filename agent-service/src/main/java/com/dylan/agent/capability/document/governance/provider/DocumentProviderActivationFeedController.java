package com.dylan.agent.capability.document.governance.provider;

import com.dylan.agent.adapter.api.document.provider.DocumentProviderActivationSnapshot;
import com.dylan.common.security.SecurityTokenUtils;
import org.springframework.security.access.AccessDeniedException;
import org.springframework.security.oauth2.server.resource.authentication.JwtAuthenticationToken;
import org.springframework.web.bind.annotation.*;
import java.util.List;

@RestController
@RequestMapping("/internal/document-governance/provider-activations")
public final class DocumentProviderActivationFeedController {
    private static final String REQUIRED_AUTHORITY = "SCOPE_agent.document.provider.activation";
    private final DocumentProviderActivationPublisher publisher;
    DocumentProviderActivationFeedController(DocumentProviderActivationPublisher publisher) { this.publisher = publisher; }

    @GetMapping
    public List<DocumentProviderActivationSnapshot> current(JwtAuthenticationToken authentication) {
        requireConsumer(authentication);
        return publisher.current();
    }

    @PostMapping("/ack")
    public void acknowledge(JwtAuthenticationToken authentication, @RequestBody Acknowledgement request) {
        String consumer = requireConsumer(authentication);
        if (request == null || !consumer.equals(request.consumerId())) {
            throw new AccessDeniedException("activation acknowledgement consumer mismatch");
        }
        publisher.acknowledge(consumer, request.operationType(), request.deploymentDigest(), request.activationDigest());
    }

    private static String requireConsumer(JwtAuthenticationToken authentication) {
        if (authentication == null || !SecurityTokenUtils.isServiceToken(authentication.getToken())
                || authentication.getAuthorities().stream().map(value -> value.getAuthority())
                .noneMatch(REQUIRED_AUTHORITY::equals)) {
            throw new AccessDeniedException("document provider activation scope required");
        }
        String subject = SecurityTokenUtils.subject(authentication.getToken());
        if (subject == null || subject.isBlank()) throw new AccessDeniedException("service subject required");
        return subject;
    }

    public record Acknowledgement(String consumerId, com.dylan.agent.adapter.api.operation.CapabilityOperationType operationType,
                                  String deploymentDigest, String activationDigest) {}
}
