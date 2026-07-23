package com.dylan.agent.employee;

import static org.assertj.core.api.Assertions.assertThat;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.post;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.web.servlet.AutoConfigureMockMvc;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.context.ApplicationContext;
import org.springframework.test.web.servlet.MockMvc;

@SpringBootTest(
		webEnvironment = SpringBootTest.WebEnvironment.MOCK,
		properties = {
				"eureka.client.enabled=false",
				"spring.cloud.config.enabled=false",
				"agent.employee.adapter.enabled=true",
				"agent.employee.adapter.single-tenant-ref=tenant-main",
				"common.security.secrets.allow-config-values=true",
				"common.security.secrets.source-order[0]=config",
				"common.security.secrets.jwt.active-key-id=ACTIVE",
				"common.security.secrets.jwt.keys.ACTIVE.value=AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA=",
				"common.security.secrets.agent-service-jwt.active-key-id=ACTIVE",
				"common.security.secrets.agent-service-jwt.previous-key-ids[0]=PREVIOUS",
				"common.security.secrets.agent-service-jwt.keys.ACTIVE.value=BBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBB=",
				"common.security.secrets.agent-service-jwt.keys.PREVIOUS.value=CCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCC="
		})
@AutoConfigureMockMvc
class AgentEmployeeAdapterSpringContextTest {

	@Autowired
	private ApplicationContext context;

	@Autowired
	private MockMvc mockMvc;

	@Test
	void wiresBothSecurityChains() {
		assertThat(context.containsBean("agentEmployeeFilterChain")).isTrue();
		assertThat(context.containsBean("denyUnmatchedRequests")).isTrue();
	}

	@Test
	void failsClosedForMissingDelegatedTokenAndUnmatchedEndpoint() throws Exception {
		mockMvc.perform(post("/internal/agent/employee/query")
						.contentType("application/json")
						.content("{}"))
				.andExpect(status().isUnauthorized());
		mockMvc.perform(get("/actuator/health"))
				.andExpect(status().isForbidden());
	}
}
