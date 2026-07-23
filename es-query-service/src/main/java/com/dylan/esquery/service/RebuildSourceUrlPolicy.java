package com.dylan.esquery.service;

import java.net.URI;
import java.net.URISyntaxException;
import java.net.URLDecoder;
import java.nio.charset.StandardCharsets;
import java.util.List;
import java.util.Set;

import org.springframework.stereotype.Component;

import com.dylan.esquery.config.EsQueryProperties;

/**
 * 校验索引重建数据源地址，避免重建任务访问未授权地址。
 */
@Component
public class RebuildSourceUrlPolicy {

	private static final Set<String> RESERVED_QUERY_PARAMETERS = Set.of("batchsize", "cursor", "since");

	private final EsQueryProperties properties;

	public RebuildSourceUrlPolicy(EsQueryProperties properties) {
		this.properties = properties;
	}

	public void validate(String sourceUrl) {
		if (sourceUrl == null || sourceUrl.isBlank()) {
			throw new IllegalArgumentException("sourceUrl must not be blank");
		}
		URI uri = parse(sourceUrl);
		String scheme = uri.getScheme();
		if (!"http".equalsIgnoreCase(scheme) && !"https".equalsIgnoreCase(scheme)) {
			throw new IllegalArgumentException("sourceUrl scheme must be http or https");
		}
		if (uri.getUserInfo() != null && !uri.getUserInfo().isBlank()) {
			throw new IllegalArgumentException("sourceUrl userInfo is not allowed");
		}
		String host = uri.getHost();
		if (host == null || host.isBlank()) {
			throw new IllegalArgumentException("sourceUrl host must not be blank");
		}
		List<String> allowedHosts = properties.getRebuildSourceAllowedHosts();
		if (allowedHosts == null || allowedHosts.isEmpty()) {
			throw new IllegalStateException("es.query.rebuild-source-allowed-hosts must not be empty");
		}
		String normalizedHost = host.trim().toLowerCase();
		if (!allowedHosts.contains(normalizedHost)) {
			throw new IllegalArgumentException("sourceUrl host is not allowed: " + normalizedHost);
		}
		validateReservedQueryParameters(uri.getRawQuery());
	}

	private URI parse(String sourceUrl) {
		try {
			return new URI(sourceUrl);
		} catch (URISyntaxException ex) {
			throw new IllegalArgumentException("sourceUrl must be a valid URI", ex);
		}
	}

	private void validateReservedQueryParameters(String rawQuery) {
		if (rawQuery == null || rawQuery.isBlank()) {
			return;
		}
		for (String pair : rawQuery.split("&")) {
			String rawName = pair.split("=", 2)[0];
			String name = URLDecoder.decode(rawName, StandardCharsets.UTF_8).toLowerCase();
			if (RESERVED_QUERY_PARAMETERS.contains(name)) {
				throw new IllegalArgumentException("sourceUrl must not contain reserved parameter: " + name);
			}
		}
	}
}
