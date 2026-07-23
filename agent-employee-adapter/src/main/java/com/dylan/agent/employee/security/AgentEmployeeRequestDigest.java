package com.dylan.agent.employee.security;

import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.security.NoSuchAlgorithmException;
import java.util.HexFormat;

import com.dylan.agent.employee.api.AgentBusinessException;
import com.dylan.agent.employee.api.model.AgentEmployeeQueryRequest;
import com.fasterxml.jackson.core.JsonProcessingException;
import com.fasterxml.jackson.databind.MapperFeature;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.fasterxml.jackson.databind.SerializationFeature;

public final class AgentEmployeeRequestDigest {
	private static final ObjectMapper CANONICAL = new ObjectMapper()
			.findAndRegisterModules()
			.enable(MapperFeature.SORT_PROPERTIES_ALPHABETICALLY)
			.enable(SerializationFeature.ORDER_MAP_ENTRIES_BY_KEYS)
			.disable(SerializationFeature.WRITE_DATES_AS_TIMESTAMPS);

	private AgentEmployeeRequestDigest() {
	}

	public static String sha256(AgentEmployeeQueryRequest request) {
		try {
			byte[] json = CANONICAL.writeValueAsBytes(request);
			return HexFormat.of().formatHex(MessageDigest.getInstance("SHA-256").digest(json));
		} catch (JsonProcessingException | NoSuchAlgorithmException ex) {
			throw new AgentBusinessException("AGENT_BUSINESS_INTERNAL_ERROR",
					org.springframework.http.HttpStatus.INTERNAL_SERVER_ERROR);
		}
	}

	public static String canonicalJson(AgentEmployeeQueryRequest request) {
		try {
			return new String(CANONICAL.writeValueAsBytes(request), StandardCharsets.UTF_8);
		} catch (JsonProcessingException ex) {
			throw new AgentBusinessException("AGENT_BUSINESS_INTERNAL_ERROR",
					org.springframework.http.HttpStatus.INTERNAL_SERVER_ERROR);
		}
	}
}
