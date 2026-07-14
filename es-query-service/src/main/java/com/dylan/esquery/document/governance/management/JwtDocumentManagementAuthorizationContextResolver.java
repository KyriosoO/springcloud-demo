package com.dylan.esquery.document.governance.management;

import com.dylan.common.security.SecurityTokenUtils;
import org.springframework.security.access.AccessDeniedException;
import org.springframework.security.core.Authentication;
import org.springframework.security.oauth2.server.resource.authentication.JwtAuthenticationToken;

import java.nio.ByteBuffer;
import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.time.Instant;
import java.util.HexFormat;
import java.util.Set;

public final class JwtDocumentManagementAuthorizationContextResolver implements DocumentManagementAuthorizationContextResolver {
    private final Set<String> allowedServiceSubjects;
    public JwtDocumentManagementAuthorizationContextResolver(Set<String> allowedServiceSubjects){this.allowedServiceSubjects=Set.copyOf(allowedServiceSubjects);}
    @Override public DocumentManagementAuthorizationContext resolve(Authentication authentication,DocumentManagementOperation operation){
        if(!(authentication instanceof JwtAuthenticationToken jwt)||!SecurityTokenUtils.isServiceToken(jwt.getToken()))throw new AccessDeniedException("document governance service authentication required");
        String subject=SecurityTokenUtils.subject(jwt.getToken());
        if(subject==null||!allowedServiceSubjects.contains(subject)||jwt.getAuthorities().stream().noneMatch(a->operation.authority().equals(a.getAuthority())))throw new AccessDeniedException("document governance operation is not authorized");
        Instant issuedAt=jwt.getToken().getIssuedAt();if(issuedAt==null)throw new AccessDeniedException("service token issuedAt required");
        String tokenId=jwt.getToken().getId();String evidence=canonical("DMA-1",subject,operation.name(),issuedAt.toString(),tokenId==null?"":tokenId);
        return new DocumentManagementAuthorizationContext(subject,"ACT-"+canonical("ACT-1",subject).substring(0,32),Set.of(operation.scope()),issuedAt,evidence);
    }
    static String canonical(String... values){try{MessageDigest d=MessageDigest.getInstance("SHA-256");for(String value:values){byte[] bytes=value.getBytes(StandardCharsets.UTF_8);d.update(ByteBuffer.allocate(4).putInt(bytes.length).array());d.update(bytes);}return HexFormat.of().formatHex(d.digest());}catch(Exception ex){throw new IllegalStateException(ex);}}
}
