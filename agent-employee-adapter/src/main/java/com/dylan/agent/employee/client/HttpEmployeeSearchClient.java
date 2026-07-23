package com.dylan.agent.employee.client;

import java.io.IOException;
import java.net.http.HttpClient;
import java.net.http.HttpRequest;
import java.net.http.HttpResponse;
import java.time.Duration;

import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.http.HttpHeaders;
import org.springframework.http.HttpStatus;
import org.springframework.stereotype.Component;

import com.dylan.agent.employee.api.AgentBusinessException;
import com.dylan.agent.employee.config.AgentEmployeeAdapterProperties;
import com.dylan.common.security.ServiceTokenProvider;
import com.fasterxml.jackson.core.JsonProcessingException;
import com.fasterxml.jackson.databind.ObjectMapper;

@Component
public class HttpEmployeeSearchClient implements EmployeeSearchClient {

	private final AgentEmployeeAdapterProperties properties;
	private final ServiceTokenProvider tokenProvider;
	private final ObjectMapper objectMapper;
	private final HttpClient httpClient;

	@Autowired
	public HttpEmployeeSearchClient(AgentEmployeeAdapterProperties properties,
			ServiceTokenProvider tokenProvider, ObjectMapper objectMapper) {
		this(properties, tokenProvider, objectMapper,
				HttpClient.newBuilder().followRedirects(HttpClient.Redirect.NEVER).build());
	}

	HttpEmployeeSearchClient(AgentEmployeeAdapterProperties properties,
			ServiceTokenProvider tokenProvider, ObjectMapper objectMapper, HttpClient httpClient) {
		this.properties = properties;
		this.tokenProvider = tokenProvider;
		this.objectMapper = objectMapper;
		this.httpClient = httpClient;
	}

	@Override
	public String search(EmployeeSearchRequest request, Duration timeout) {
		properties.validate();
		try {
			HttpRequest httpRequest = HttpRequest.newBuilder(properties.getEmployeeSearchUrl())
					.timeout(timeout)
					.header(HttpHeaders.AUTHORIZATION, "Bearer " + tokenProvider.token())
					.header(HttpHeaders.CONTENT_TYPE, "application/json")
					.POST(HttpRequest.BodyPublishers.ofString(objectMapper.writeValueAsString(request)))
					.build();
			HttpResponse<String> response = httpClient.send(httpRequest, HttpResponse.BodyHandlers.ofString());
			if (response.statusCode() == HttpStatus.FORBIDDEN.value()) {
				throw new AgentBusinessException("AGENT_BUSINESS_FORBIDDEN", HttpStatus.FORBIDDEN);
			}
			if (response.statusCode() != HttpStatus.OK.value()) {
				throw unavailable();
			}
			return response.body();
		} catch (JsonProcessingException ex) {
			throw new AgentBusinessException("AGENT_BUSINESS_INTERNAL_ERROR", HttpStatus.INTERNAL_SERVER_ERROR);
		} catch (InterruptedException ex) {
			Thread.currentThread().interrupt();
			throw unavailable();
		} catch (IOException | IllegalArgumentException ex) {
			throw unavailable();
		}
	}

	private static AgentBusinessException unavailable() {
		return new AgentBusinessException("AGENT_BUSINESS_UNAVAILABLE", HttpStatus.SERVICE_UNAVAILABLE);
	}
}
