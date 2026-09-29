package com.dylan.esquery.service;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.verifyNoInteractions;
import static org.mockito.Mockito.when;

import java.io.IOException;
import java.net.SocketTimeoutException;
import java.nio.charset.StandardCharsets;
import java.time.Instant;
import java.util.List;
import java.util.Map;

import org.apache.http.entity.ContentType;
import org.apache.http.nio.entity.NStringEntity;
import org.apache.http.HttpHost;
import org.apache.http.message.BasicRequestLine;
import org.apache.http.message.BasicStatusLine;
import org.apache.http.HttpVersion;
import org.elasticsearch.client.Request;
import org.elasticsearch.client.Response;
import org.elasticsearch.client.ResponseException;
import org.elasticsearch.client.RestClient;
import org.junit.jupiter.api.Test;
import org.mockito.ArgumentCaptor;
import org.springframework.boot.context.properties.bind.Bindable;
import org.springframework.boot.context.properties.bind.Binder;
import org.springframework.boot.env.YamlPropertySourceLoader;
import org.springframework.core.io.ClassPathResource;
import org.springframework.mock.env.MockEnvironment;
import org.springframework.security.core.authority.SimpleGrantedAuthority;
import org.springframework.security.oauth2.jwt.Jwt;
import org.springframework.security.oauth2.server.resource.authentication.JwtAuthenticationToken;

import com.dylan.common.security.SecurityTokenUtils;
import com.dylan.esquery.api.knowledge.KnowledgeSearchRequest;
import com.dylan.esquery.api.knowledge.KnowledgeSearchResponse;
import com.dylan.esquery.config.KnowledgeSearchProperties;
import com.dylan.esquery.web.KnowledgeSearchExceptions.KnowledgeAuthorityUnavailableException;
import com.dylan.esquery.web.KnowledgeSearchExceptions.KnowledgeForbiddenException;
import com.dylan.esquery.web.KnowledgeSearchExceptions.KnowledgeProviderException;
import com.dylan.esquery.web.KnowledgeSearchExceptions.KnowledgeRateLimitedException;
import com.dylan.esquery.web.KnowledgeSearchExceptions.KnowledgeTimeoutException;
import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;

class KnowledgeBIsolationSearchTest {
	private static final String RUN_ID = "b-run-12345";
	private static final String READ_ALIAS = "b-b-run-12345-0123456789abcdef-read";
	private static final String INDEX_NAME = "b-physical-index-1";
	private static final String PRODUCTION_ALIAS = "agent-doc-tax-policy-v2-read";
	private final ObjectMapper mapper = new ObjectMapper();

	@Test
	void bothDomainsAndPathsKeepTheSameDslAuthorizationAndCandidateDecoding() throws Exception {
		for (String domain : List.of("tax.policy", "tax.law")) {
			for (String path : List.of("keyword", "vector")) {
				KnowledgeSearchRequest request = request(domain, path);
				String hit = mapper.writeValueAsString(Map.of("hits", Map.of("hits", List.of(hit()))));
				SearchResult normal = search(false, request, hit);
				SearchResult isolated = search(true, request, hit);
				assertThat(normal.request().getEndpoint()).isEqualTo("/" + PRODUCTION_ALIAS + "/_search");
				assertThat(isolated.request().getEndpoint()).isEqualTo("/" + INDEX_NAME + "/_search");
				assertThat(normal.request().getMethod()).isEqualTo("POST");
				assertThat(isolated.request().getMethod()).isEqualTo("POST");
				assertThat(body(normal.request())).isEqualTo(body(isolated.request()));
				assertThat(normal.response().schemaVersion()).isEqualTo(isolated.response().schemaVersion());
				assertThat(normal.response().logicalDomainId()).isEqualTo(isolated.response().logicalDomainId());
				assertThat(normal.response().retrievalProfileId()).isEqualTo(isolated.response().retrievalProfileId());
				assertThat(normal.response().path()).isEqualTo(isolated.response().path());
				assertThat(normal.response().profileVersion()).isEqualTo(isolated.response().profileVersion());
				assertThat(normal.response().readPolicyVersion()).isEqualTo(isolated.response().readPolicyVersion());
				assertThat(normal.response().truncated()).isEqualTo(isolated.response().truncated());
				assertThat(normal.response().candidates()).isEqualTo(isolated.response().candidates());
				assertThat(normal.response().indexSnapshotId()).isNotEqualTo(isolated.response().indexSnapshotId());
				assertThat(isolated.response().candidates()).singleElement().satisfies(candidate -> {
					assertThat(candidate.logicalDomainId()).isEqualTo(domain);
					assertThat(candidate.documentId()).isEqualTo("document-1");
					assertThat(candidate.content()).isEqualTo("正文");
					assertThat(candidate.policyRef()).isEqualTo("public");
				});
			}
		}
	}

	@Test
	void zeroHitsStillIssueTheFixedPhysicalSearchRequestForBothDomainsAndPaths() throws Exception {
		String emptyHits = "{\"hits\":{\"hits\":[]}}";
		for (String domain : List.of("tax.policy", "tax.law")) {
			for (String path : List.of("keyword", "vector")) {
				SearchResult isolated = search(true, request(domain, path), emptyHits);
				assertThat(isolated.response().candidates()).isEmpty();
				assertThat(isolated.request().getEndpoint()).isEqualTo("/" + INDEX_NAME + "/_search");
			}
		}
	}

	@Test
	void bothModesPreserveAccessDenialsBeforeAnyEsCall() throws Exception {
		for (boolean fixed : new boolean[] {false, true}) {
			KnowledgeSearchProperties properties = properties(fixed);
			KnowledgeReadAccessGuard guard = new KnowledgeReadAccessGuard(properties);
			RestClient client = mock(RestClient.class);
			KnowledgeSearchService service = new KnowledgeSearchService(client, mapper, properties);
			for (String domain : List.of("tax.policy", "tax.law")) {
				String profileId = profileId(domain);
				for (String role : List.of("ROLE_ADMIN", "ROLE_VIEWER")) {
					assertThat(guard.authorize(authentication("user", role), domain, profileId)
							.readPolicyVersion()).isEqualTo("tax-public-authenticated-v1");
				}
				for (String tokenType : List.of("service", "user")) {
					String role = tokenType.equals("service") ? "ROLE_ADMIN" : "ROLE_OTHER";
					assertThatThrownBy(() -> guard.authorize(authentication(tokenType, role), domain, profileId))
							.isInstanceOf(KnowledgeForbiddenException.class);
				}
				KnowledgeSearchRequest request = request(domain, "keyword");
				KnowledgeReadDecision wrong = new KnowledgeReadDecision(domain, profileId,
						"wrong-profile-version", "tax-public-authenticated-v1", "decision");
				assertThatThrownBy(() -> service.search(request, wrong))
						.isInstanceOf(KnowledgeAuthorityUnavailableException.class);
			}
			verifyNoInteractions(client);
		}
	}

	@Test
	void bothModesPreserveTimeoutProviderAndDecodeFailures() throws Exception {
		for (boolean fixed : new boolean[] {false, true}) {
			KnowledgeSearchProperties properties = properties(fixed);
			for (String domain : List.of("tax.policy", "tax.law")) {
				for (String path : List.of("keyword", "vector")) {
					KnowledgeSearchRequest request = request(domain, path);
					KnowledgeReadDecision decision = new KnowledgeReadAccessGuard(properties).authorize(
							authentication("user", "ROLE_ADMIN"), domain, profileId(domain));
					for (IOException error : List.of(new SocketTimeoutException("synthetic"),
							new IOException("synthetic"))) {
						RestClient client = mock(RestClient.class);
						when(client.performRequest(any())).thenThrow(error);
						KnowledgeSearchService service = new KnowledgeSearchService(client, mapper, properties);
						assertThatThrownBy(() -> service.search(request, decision))
								.isInstanceOf(error instanceof SocketTimeoutException
										? KnowledgeTimeoutException.class : KnowledgeProviderException.class);
						verify(client).performRequest(any());
					}
					RestClient client = mock(RestClient.class);
					Response invalidResponse = response("{\"hits\":{\"hits\":[{\"_score\":1,\"_source\":{\"unknown\":\"x\"}}]}");
					when(client.performRequest(any())).thenReturn(invalidResponse);
					KnowledgeSearchService service = new KnowledgeSearchService(client, mapper, properties);
					assertThatThrownBy(() -> service.search(request, decision))
							.isInstanceOf(KnowledgeProviderException.class);
					verify(client).performRequest(any());
					for (int status : List.of(429, 503)) {
						RestClient rejectedClient = mock(RestClient.class);
						ResponseException rejection = rejection(status);
						when(rejectedClient.performRequest(any())).thenThrow(rejection);
						KnowledgeSearchService rejectedService = new KnowledgeSearchService(
								rejectedClient, mapper, properties);
						assertThatThrownBy(() -> rejectedService.search(request, decision))
								.isInstanceOf(status == 429 ? KnowledgeRateLimitedException.class
										: KnowledgeProviderException.class);
						verify(rejectedClient).performRequest(any());
					}
				}
			}
		}
	}

	private SearchResult search(boolean fixed, KnowledgeSearchRequest request, String json) throws Exception {
		KnowledgeSearchProperties properties = properties(fixed);
		RestClient client = mock(RestClient.class);
		Response esResponse = response(json);
		when(client.performRequest(any())).thenReturn(esResponse);
		KnowledgeReadDecision decision = new KnowledgeReadAccessGuard(properties).authorize(
				authentication("user", "ROLE_ADMIN"), request.logicalDomainId(), request.retrievalProfileId());
		KnowledgeSearchResponse result = new KnowledgeSearchService(client, mapper, properties)
				.search(request, decision);
		ArgumentCaptor<Request> captured = ArgumentCaptor.forClass(Request.class);
		verify(client).performRequest(captured.capture());
		return new SearchResult(result, captured.getValue());
	}

	private static KnowledgeSearchProperties properties(boolean fixed) throws Exception {
		MockEnvironment environment = new MockEnvironment()
				.withProperty("AGENT_KNOWLEDGE_READ_ALIAS", fixed ? READ_ALIAS : PRODUCTION_ALIAS)
				.withProperty("AGENT_KNOWLEDGE_EXPECTED_INDEX_NAME", INDEX_NAME)
				.withProperty("AGENT_KNOWLEDGE_EXPECTED_INDEX_UUID", "index-uuid-1")
				.withProperty("AGENT_KNOWLEDGE_MAPPING_VERSION", "mapping-v1")
				.withProperty("AGENT_KNOWLEDGE_POLICY_SNAPSHOT_ID", "0".repeat(64))
				.withProperty("AGENT_KNOWLEDGE_LAW_SNAPSHOT_ID", "1".repeat(64));
		if (fixed) {
			environment.withProperty("es.query.knowledge.b-isolation-fixed-target", "true")
					.withProperty("es.query.knowledge.b-isolation-run-id", RUN_ID);
		}
		new YamlPropertySourceLoader().load("knowledge-live", new ClassPathResource("application-knowledge-live.yml"))
				.forEach(source -> environment.getPropertySources().addLast(source));
		KnowledgeSearchProperties properties = Binder.get(environment)
				.bind("es.query.knowledge", Bindable.of(KnowledgeSearchProperties.class)).get();
		if (fixed) {
			for (String profileId : List.of("tax-policy-v1", "tax-law-v1")) {
				KnowledgeSearchProperties.KnowledgeSearchProfile profile = properties.getProfiles().get(profileId);
				profile.setIndexSnapshotId(KnowledgeProfileVerifier.snapshot(
						profileId, INDEX_NAME, "index-uuid-1", "tax-knowledge-search-v1", "mapping-v1"));
			}
		}
		properties.afterPropertiesSet();
		return properties;
	}

	private static KnowledgeSearchRequest request(String domain, String path) {
		return new KnowledgeSearchRequest(1, domain, profileId(domain), path,
				path.equals("keyword") ? "政策" : null,
				path.equals("vector") ? java.util.Collections.nCopies(1024, 0.25d) : null, 5);
	}

	private static String profileId(String domain) {
		return domain.equals("tax.policy") ? "tax-policy-v1" : "tax-law-v1";
	}

	private static JwtAuthenticationToken authentication(String tokenType, String authority) {
		Instant now = Instant.parse("2026-08-03T00:00:00Z");
		Jwt jwt = Jwt.withTokenValue("synthetic-token").header("alg", "none").subject("synthetic-user")
				.issuedAt(now).expiresAt(now.plusSeconds(300))
				.claim(SecurityTokenUtils.TOKEN_TYPE_CLAIM, tokenType).build();
		return new JwtAuthenticationToken(jwt, List.of(new SimpleGrantedAuthority(authority)));
	}

	private static Response response(String json) {
		Response response = mock(Response.class);
		when(response.getEntity()).thenReturn(new NStringEntity(json, ContentType.APPLICATION_JSON));
		when(response.getHeader("Content-Type")).thenReturn("application/json");
		return response;
	}

	private static ResponseException rejection(int status) throws Exception {
		Response response = mock(Response.class);
		when(response.getRequestLine()).thenReturn(new BasicRequestLine("POST", "/_search", HttpVersion.HTTP_1_1));
		when(response.getHost()).thenReturn(new HttpHost("localhost", 9200));
		when(response.getStatusLine()).thenReturn(new BasicStatusLine(HttpVersion.HTTP_1_1, status, "synthetic"));
		return new ResponseException(response);
	}

	private static Map<String, Object> hit() {
		return Map.of("_score", 0.75, "_source", Map.of(
				"documentId", "document-1", "chunkId", "chunk-1", "title", "标题", "content", "正文",
				"sourceUrl", "/source", "documentNo", "文号", "writtenDate", "2025-01-01",
				"materialType", "tax_policy", "aclRef", "public"));
	}

	private JsonNode body(Request request) throws Exception {
		try (var input = request.getEntity().getContent()) {
			return mapper.readTree(new String(input.readAllBytes(), StandardCharsets.UTF_8));
		}
	}

	private record SearchResult(KnowledgeSearchResponse response, Request request) {
	}
}
