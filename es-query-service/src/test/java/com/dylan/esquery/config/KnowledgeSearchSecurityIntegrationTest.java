package com.dylan.esquery.config;

import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.eq;
import static org.mockito.Mockito.never;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

import java.time.Instant;
import java.util.List;

import org.junit.jupiter.api.Test;
import org.springframework.boot.test.autoconfigure.web.servlet.WebMvcTest;
import org.springframework.context.annotation.Import;
import org.springframework.http.HttpHeaders;
import org.springframework.http.MediaType;
import org.springframework.security.oauth2.jwt.Jwt;
import org.springframework.security.oauth2.jwt.JwtDecoder;
import org.springframework.test.context.ContextConfiguration;
import org.springframework.test.context.TestPropertySource;
import org.springframework.test.context.bean.override.mockito.MockitoBean;
import org.springframework.test.web.servlet.MockMvc;

import com.dylan.common.security.SecurityTokenUtils;
import com.dylan.common.security.UserRoleAuthorityAutoConfiguration;
import com.dylan.esquery.api.knowledge.KnowledgeSearchResponse;
import com.dylan.esquery.controller.KnowledgeSearchController;
import com.dylan.esquery.service.KnowledgeProfileVerifier;
import com.dylan.esquery.service.KnowledgeReadAccessGuard;
import com.dylan.esquery.service.KnowledgeReadDecision;
import com.dylan.esquery.service.KnowledgeSearchService;

@WebMvcTest(KnowledgeSearchController.class)
@ContextConfiguration(classes = KnowledgeSearchController.class)
@Import({ KnowledgeSearchConfiguration.class, ExistingEsEndpointsSecurityConfiguration.class,
		UserRoleAuthorityAutoConfiguration.class })
@TestPropertySource(properties = { "es.query.knowledge.enabled=true",
		"spring.cloud.config.enabled=false", "spring.config.import=" })
class KnowledgeSearchSecurityIntegrationTest {
	@jakarta.annotation.Resource
	private MockMvc mvc;
	@MockitoBean
	private JwtDecoder jwtDecoder;
	@MockitoBean
	private KnowledgeReadAccessGuard accessGuard;
	@MockitoBean
	private KnowledgeSearchService searchService;
	@MockitoBean
	private KnowledgeProfileVerifier profileVerifier;

	@Test
	void adminAndViewerCanSearch() throws Exception {
		KnowledgeReadDecision decision = new KnowledgeReadDecision(
				"tax.policy", "tax-policy-v1", "profile-v1", "policy-v1", "decision-1");
		KnowledgeSearchResponse response = new KnowledgeSearchResponse(1, "tax.policy",
				"tax-policy-v1", "keyword", "profile-v1", "snapshot-1", "policy-v1", false,
				List.of());
		when(accessGuard.authorize(any(), eq("tax.policy"), eq("tax-policy-v1"))).thenReturn(decision);
		when(searchService.search(any(), eq(decision))).thenReturn(response);

		for (String role : List.of("ADMIN", "VIEWER")) {
			when(jwtDecoder.decode("token-" + role)).thenReturn(jwt("user", List.of(role)));
			mvc.perform(org.springframework.test.web.servlet.request.MockMvcRequestBuilders
					.post("/es/knowledge/search")
					.header(HttpHeaders.AUTHORIZATION, "Bearer token-" + role)
					.contentType(MediaType.APPLICATION_JSON).content(searchBody()))
					.andExpect(org.springframework.test.web.servlet.result.MockMvcResultMatchers.status().isOk());
		}

		verify(searchService, org.mockito.Mockito.times(2)).search(any(), eq(decision));
	}

	@Test
	void invalidRoleAndServiceTokenAreRejectedBeforeTheController() throws Exception {
		when(jwtDecoder.decode("unknown")).thenReturn(jwt("user", List.of("UNKNOWN")));
		when(jwtDecoder.decode("service")).thenReturn(jwt("service", List.of("ADMIN")));

		mvc.perform(org.springframework.test.web.servlet.request.MockMvcRequestBuilders
				.post("/es/knowledge/search").header(HttpHeaders.AUTHORIZATION, "Bearer unknown")
				.contentType(MediaType.APPLICATION_JSON).content(searchBody()))
				.andExpect(org.springframework.test.web.servlet.result.MockMvcResultMatchers.status().isForbidden());
		mvc.perform(org.springframework.test.web.servlet.request.MockMvcRequestBuilders
				.post("/es/knowledge/search").header(HttpHeaders.AUTHORIZATION, "Bearer service")
				.contentType(MediaType.APPLICATION_JSON).content(searchBody()))
				.andExpect(org.springframework.test.web.servlet.result.MockMvcResultMatchers.status().isUnauthorized());

		verify(searchService, never()).search(any(), any());
	}

	@Test
	void fallbackChainKeepsNonKnowledgePathsPublic() throws Exception {
		mvc.perform(org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get("/not-a-knowledge-path"))
				.andExpect(org.springframework.test.web.servlet.result.MockMvcResultMatchers.status().isNotFound());
	}

	private static String searchBody() {
		return "{\"schemaVersion\":1,\"logicalDomainId\":\"tax.policy\","
				+ "\"retrievalProfileId\":\"tax-policy-v1\",\"path\":\"keyword\","
				+ "\"queryText\":\"synthetic question\",\"queryVector\":null,\"limit\":5}";
	}

	private static Jwt jwt(String tokenType, List<String> roles) {
		Instant now = Instant.parse("2026-08-03T00:00:00Z");
		return Jwt.withTokenValue("token").header("alg", "none").subject("synthetic-user")
				.issuedAt(now).expiresAt(now.plusSeconds(300))
				.claim(SecurityTokenUtils.TOKEN_TYPE_CLAIM, tokenType)
				.claim("role", roles).build();
	}
}
