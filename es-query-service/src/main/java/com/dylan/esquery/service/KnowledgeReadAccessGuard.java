package com.dylan.esquery.service;

import java.util.Set;
import java.util.UUID;
import java.util.stream.Collectors;

import org.springframework.security.core.Authentication;
import org.springframework.security.oauth2.jwt.Jwt;
import org.springframework.security.oauth2.server.resource.authentication.JwtAuthenticationToken;

import com.dylan.common.security.SecurityTokenUtils;
import com.dylan.common.security.UserRoleJwtAuthenticationConverter;
import com.dylan.esquery.config.KnowledgeSearchProperties;
import com.dylan.esquery.config.KnowledgeSearchProperties.KnowledgeSearchProfile;
import com.dylan.esquery.web.KnowledgeSearchExceptions.KnowledgeForbiddenException;

public final class KnowledgeReadAccessGuard {
	private static final Set<String> ALLOWED_AUTHORITIES = Set.of(
			UserRoleJwtAuthenticationConverter.AUTHORITY_ADMIN,
			UserRoleJwtAuthenticationConverter.AUTHORITY_VIEWER);

	private final KnowledgeSearchProperties properties;

	public KnowledgeReadAccessGuard(KnowledgeSearchProperties properties) {
		this.properties = properties;
	}

	public KnowledgeReadDecision authorize(Authentication authentication,
			String logicalDomainId, String retrievalProfileId) {
		KnowledgeSearchProfile profile = properties.requireProfile(logicalDomainId, retrievalProfileId);
		Jwt jwt = authentication instanceof JwtAuthenticationToken token ? token.getToken() : null;
		Set<String> authorities = authentication == null ? Set.of()
				: authentication.getAuthorities().stream()
						.map(Object::toString)
						.collect(Collectors.toUnmodifiableSet());
		if (!SecurityTokenUtils.isUserToken(jwt) || authorities.isEmpty()
				|| !ALLOWED_AUTHORITIES.containsAll(authorities)) {
			throw new KnowledgeForbiddenException();
		}
		return new KnowledgeReadDecision(logicalDomainId, retrievalProfileId,
				profile.getProfileVersion(), profile.getReadPolicyVersion(), UUID.randomUUID().toString());
	}
}
