package com.dylan.agent.capability.document.governance.management;

import com.dylan.common.security.SecurityTokenUtils;
import org.springframework.security.access.AccessDeniedException;
import org.springframework.security.core.Authentication;
import org.springframework.security.oauth2.server.resource.authentication.JwtAuthenticationToken;

import java.nio.ByteBuffer;
import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.time.Instant;
import java.util.HexFormat;
import java.util.Objects;
import java.util.Set;

public final class JwtDocumentManagementAuthorizationContextResolver
        implements DocumentManagementAuthorizationContextResolver {
    private final Set<String> allowedServiceSubjects;

    public JwtDocumentManagementAuthorizationContextResolver(Set<String> allowedServiceSubjects) {
        this.allowedServiceSubjects = Set.copyOf(Objects.requireNonNull(allowedServiceSubjects));
    }

    @Override
    public DocumentManagementAuthorizationContext resolve(
            Authentication authentication, DocumentManagementOperation operation) {
        Objects.requireNonNull(operation, "operation must not be null");
        if (!(authentication instanceof JwtAuthenticationToken jwtAuthentication)
                || !SecurityTokenUtils.isServiceToken(jwtAuthentication.getToken())) {
            throw new AccessDeniedException("document governance service authentication required");
        }
        String subject = SecurityTokenUtils.subject(jwtAuthentication.getToken());
        if (subject == null || !allowedServiceSubjects.contains(subject)
                || jwtAuthentication.getAuthorities().stream().noneMatch(
                authority -> operation.authority().equals(authority.getAuthority()))) {
            throw new AccessDeniedException("document governance operation is not authorized");
        }
        Instant authenticatedAt = jwtAuthentication.getToken().getIssuedAt();
        if (authenticatedAt == null) throw new AccessDeniedException("service token issuedAt required");
        String tokenId = jwtAuthentication.getToken().getId();
        String evidenceDigest = canonical("DMA-1", subject, operation.name(),
                authenticatedAt.toString(), tokenId == null ? "" : tokenId);
        return new DocumentManagementAuthorizationContext(
                subject, "ACT-" + canonical("ACT-1", subject).substring(0, 32),
                Set.of(operation.scope()), authenticatedAt, evidenceDigest);
    }

    private static String canonical(String... values) {
        try {
            MessageDigest digest = MessageDigest.getInstance("SHA-256");
            for (String value : values) {
                byte[] bytes = value.getBytes(StandardCharsets.UTF_8);
                digest.update(ByteBuffer.allocate(4).putInt(bytes.length).array());
                digest.update(bytes);
            }
            return HexFormat.of().formatHex(digest.digest());
        } catch (Exception ex) {
            throw new IllegalStateException(ex);
        }
    }
}
