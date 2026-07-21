package com.dylan.documentprovider;

import com.dylan.agent.adapter.api.document.provider.*;
import com.dylan.common.security.SecurityTokenUtils;
import org.springframework.security.access.AccessDeniedException;
import org.springframework.security.oauth2.server.resource.authentication.JwtAuthenticationToken;
import org.springframework.web.bind.annotation.*;

@RestController
@RequestMapping("/internal/document-providers")
public final class DocumentProviderController {
    private static final String REQUIRED_AUTHORITY = "SCOPE_agent.document.provider.invoke";
    private final DocumentProviderOperationService service;
    DocumentProviderController(DocumentProviderOperationService service) { this.service = service; }

    @PostMapping("/rewrite")
    public DocumentProviderWireResponse<DocumentUntrustedRewritePayload> rewrite(
            JwtAuthenticationToken authentication,
            @RequestBody DocumentProviderWireRequest<DocumentRewriteInputProjection> request) {
        return service.rewrite(serviceIdentity(authentication), request);
    }
    @PostMapping("/embedding")
    public DocumentProviderWireResponse<DocumentUntrustedEmbeddingPayload> embedding(
            JwtAuthenticationToken authentication,
            @RequestBody DocumentProviderWireRequest<DocumentEmbeddingInputProjection> request) {
        return service.embedding(serviceIdentity(authentication), request);
    }
    @PostMapping("/rerank")
    public DocumentProviderWireResponse<DocumentUntrustedRerankPayload> rerank(
            JwtAuthenticationToken authentication,
            @RequestBody DocumentProviderWireRequest<DocumentRerankInputProjection> request) {
        return service.rerank(serviceIdentity(authentication), request);
    }
    @PostMapping("/generation")
    public DocumentProviderWireResponse<DocumentUntrustedGenerationPayload> generation(
            JwtAuthenticationToken authentication,
            @RequestBody DocumentProviderWireRequest<DocumentGenerationInputProjection> request) {
        return service.generation(serviceIdentity(authentication), request);
    }

    private static String serviceIdentity(JwtAuthenticationToken authentication) {
        if (authentication == null || !SecurityTokenUtils.isServiceToken(authentication.getToken())
                || authentication.getAuthorities().stream().map(value -> value.getAuthority())
                .noneMatch(REQUIRED_AUTHORITY::equals)) {
            throw new AccessDeniedException("document provider service scope required");
        }
        String subject = SecurityTokenUtils.subject(authentication.getToken());
        if (subject == null || subject.isBlank()) throw new AccessDeniedException("service subject required");
        return subject;
    }
}
