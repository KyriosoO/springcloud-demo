package com.dylan.esquery.config;

import static org.assertj.core.api.Assertions.assertThat;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.eq;
import static org.mockito.Mockito.never;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

import java.time.Instant;
import java.util.List;

import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.beans.factory.annotation.Qualifier;
import org.springframework.boot.test.autoconfigure.web.servlet.WebMvcTest;
import org.springframework.boot.test.system.CapturedOutput;
import org.springframework.boot.test.system.OutputCaptureExtension;
import org.springframework.context.annotation.Import;
import org.springframework.http.HttpHeaders;
import org.springframework.http.MediaType;
import org.springframework.core.convert.converter.Converter;
import org.springframework.security.authentication.AbstractAuthenticationToken;
import org.springframework.security.oauth2.jwt.Jwt;
import org.springframework.security.oauth2.jwt.JwtDecoder;
import org.springframework.test.context.ContextConfiguration;
import org.springframework.test.context.TestPropertySource;
import org.springframework.test.context.bean.override.mockito.MockitoBean;
import org.springframework.test.web.servlet.MockMvc;
import org.springframework.test.web.servlet.MvcResult;

import com.dylan.common.security.SecurityTokenUtils;
import com.dylan.common.security.UserRoleAuthorityAutoConfiguration;
import com.dylan.common.security.UserRoleJwtAuthenticationConverter;
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
@ExtendWith(OutputCaptureExtension.class)
class KnowledgeSearchSecurityIntegrationTest {
	private static final String SENSITIVE_TOKEN = "sensitive-knowledge-token";
	private static final String SENSITIVE_SUBJECT = "sensitive-knowledge-subject";
	private static final String SENSITIVE_ROLE = "SENSITIVE_KNOWLEDGE_ROLE";
	private static final String SENSITIVE_QUERY = "sensitive-knowledge-query";
	@jakarta.annotation.Resource
	private MockMvc mvc;
	@Autowired
	@Qualifier("userRoleJwtAuthenticationConverter")
	private Converter<Jwt, AbstractAuthenticationToken> userRoleConverter;
	@MockitoBean
	private JwtDecoder jwtDecoder;
	@MockitoBean
	private KnowledgeReadAccessGuard accessGuard;
	@MockitoBean
	private KnowledgeSearchService searchService;
	@MockitoBean
	private KnowledgeProfileVerifier profileVerifier;

	@Test
	void usesTheSharedServletConverterWithoutProviderOverride() {
		assertThat(userRoleConverter)
				.isInstanceOf(UserRoleJwtAuthenticationConverter.class);
	}

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
	void rejectedRequestsDoNotReachTheControllerOrLeakSensitiveValues(CapturedOutput output) throws Exception {
		when(jwtDecoder.decode(SENSITIVE_TOKEN))
				.thenReturn(jwt(SENSITIVE_TOKEN, SENSITIVE_SUBJECT, "user", List.of(SENSITIVE_ROLE)));
		when(jwtDecoder.decode("sensitive-knowledge-service-token"))
				.thenReturn(jwt("sensitive-knowledge-service-token", "sensitive-knowledge-service-subject",
						"service", List.of("ADMIN")));

		MvcResult forbidden = mvc.perform(org.springframework.test.web.servlet.request.MockMvcRequestBuilders
				.post("/es/knowledge/search").header(HttpHeaders.AUTHORIZATION, "Bearer " + SENSITIVE_TOKEN)
				.contentType(MediaType.APPLICATION_JSON).content(sensitiveSearchBody()))
				.andExpect(org.springframework.test.web.servlet.result.MockMvcResultMatchers.status().isForbidden())
				.andReturn();
		MvcResult unauthorized = mvc.perform(org.springframework.test.web.servlet.request.MockMvcRequestBuilders
				.post("/es/knowledge/search")
				.header(HttpHeaders.AUTHORIZATION, "Bearer sensitive-knowledge-service-token")
				.contentType(MediaType.APPLICATION_JSON).content(sensitiveSearchBody()))
				.andExpect(org.springframework.test.web.servlet.result.MockMvcResultMatchers.status().isUnauthorized())
				.andReturn();
		mvc.perform(org.springframework.test.web.servlet.request.MockMvcRequestBuilders
				.post("/es/knowledge/search")
				.contentType(MediaType.APPLICATION_JSON).content(sensitiveSearchBody()))
				.andExpect(org.springframework.test.web.servlet.result.MockMvcResultMatchers.status().isUnauthorized());

		verify(searchService, never()).search(any(), any());
		assertNoSensitiveValues(forbidden.getResponse().getContentAsString());
		assertNoSensitiveValues(unauthorized.getResponse().getContentAsString());
		assertNoSensitiveValues(output.getAll());
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

	private static String sensitiveSearchBody() {
		return searchBody().replace("synthetic question", SENSITIVE_QUERY);
	}

	private static void assertNoSensitiveValues(String actual) {
		assertThat(actual).doesNotContain(SENSITIVE_TOKEN, SENSITIVE_SUBJECT, SENSITIVE_ROLE, SENSITIVE_QUERY,
				"sensitive-knowledge-service-token", "sensitive-knowledge-service-subject");
	}

	private static Jwt jwt(String tokenType, List<String> roles) {
		return jwt("token", "synthetic-user", tokenType, roles);
	}

	private static Jwt jwt(String tokenValue, String subject, String tokenType, List<String> roles) {
		Instant now = Instant.parse("2026-08-03T00:00:00Z");
		return Jwt.withTokenValue(tokenValue).header("alg", "none").subject(subject)
				.issuedAt(now).expiresAt(now.plusSeconds(300))
				.claim(SecurityTokenUtils.TOKEN_TYPE_CLAIM, tokenType)
				.claim("role", roles).build();
	}
}
