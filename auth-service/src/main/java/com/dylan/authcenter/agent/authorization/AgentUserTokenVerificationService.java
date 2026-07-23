package com.dylan.authcenter.agent.authorization;

import java.time.Instant;

import org.springframework.beans.factory.annotation.Qualifier;
import org.springframework.security.oauth2.jwt.Jwt;
import org.springframework.security.oauth2.jwt.JwtDecoder;
import org.springframework.security.oauth2.jwt.JwtException;
import org.springframework.stereotype.Service;
import org.springframework.boot.autoconfigure.condition.ConditionalOnWebApplication;

import com.dylan.authcenter.agent.authorization.api.SensitiveBearerToken;
import com.dylan.authcenter.agent.permission.AgentPermissionErrorCode;
import com.dylan.authcenter.agent.permission.AgentPermissionException;
import com.dylan.authcenter.agent.permission.api.SubjectRefDto;
import com.dylan.authcenter.config.AuthRbacProperties;

@Service
@ConditionalOnWebApplication(type = ConditionalOnWebApplication.Type.SERVLET)
public class AgentUserTokenVerificationService {

	private final JwtDecoder userJwtDecoder;
	private final AuthRbacProperties rbacProperties;

	public AgentUserTokenVerificationService(@Qualifier("userJwtDecoder") JwtDecoder userJwtDecoder,
			AuthRbacProperties rbacProperties) {
		this.userJwtDecoder = userJwtDecoder;
		this.rbacProperties = rbacProperties;
	}

	public VerifiedUserIdentity verify(SensitiveBearerToken token) {
		if (token == null || token.value() == null || token.value().isBlank()) {
			throw new AgentPermissionException(AgentPermissionErrorCode.AGENT_PERMISSION_INVALID_REQUEST);
		}
		try {
			Jwt jwt = userJwtDecoder.decode(stripBearer(token.value()));
			String subject = jwt.getSubject();
			Instant expiresAt = jwt.getExpiresAt();
			if (!"user".equals(jwt.getClaimAsString("token_type")) || subject == null || subject.isBlank()
					|| expiresAt == null || !expiresAt.isAfter(Instant.now())) {
				throw new AgentPermissionException(AgentPermissionErrorCode.AGENT_PERMISSION_UNAUTHORIZED);
			}
			AuthRbacProperties.UserDefinition user = rbacProperties.getUsers().get(subject);
			if (user == null || user.getTenantRef() == null || user.getTenantRef().isBlank()) {
				throw new AgentPermissionException(AgentPermissionErrorCode.AGENT_PERMISSION_SUBJECT_NOT_FOUND);
			}
			return new VerifiedUserIdentity(new SubjectRefDto("USER", subject), user.getTenantRef(), expiresAt);
		} catch (JwtException ex) {
			throw new AgentPermissionException(AgentPermissionErrorCode.AGENT_PERMISSION_UNAUTHORIZED);
		}
	}

	private static String stripBearer(String value) {
		return value.regionMatches(true, 0, "Bearer ", 0, 7) ? value.substring(7).trim() : value.trim();
	}
}
