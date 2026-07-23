package com.dylan.esquery.service;

import java.util.List;

import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;

import com.dylan.esquery.config.EsQueryProperties;

import static org.assertj.core.api.Assertions.assertThatThrownBy;

class RebuildSourceUrlPolicyTest {

	private RebuildSourceUrlPolicy policy;

	@BeforeEach
	void setUp() {
		EsQueryProperties properties = new EsQueryProperties();
		properties.setRebuildSourceAllowedHosts(List.of("employee-service"));
		policy = new RebuildSourceUrlPolicy(properties);
	}

	@Test
	void acceptsConfiguredHttpHost() {
		policy.validate("http://employee-service/employees/es/source");
	}

	@Test
	void rejectsUnconfiguredHost() {
		assertThatThrownBy(() -> policy.validate("http://127.0.0.1/internal"))
				.isInstanceOf(IllegalArgumentException.class)
				.hasMessageContaining("host is not allowed");
	}

	@Test
	void rejectsReservedCursorParameter() {
		assertThatThrownBy(() -> policy.validate("http://employee-service/source?cursor=caller"))
				.isInstanceOf(IllegalArgumentException.class)
				.hasMessageContaining("reserved parameter");
	}
}
