package com.dylan.agent.employee.config;

import java.net.URI;

import jakarta.annotation.PostConstruct;

import org.springframework.boot.context.properties.ConfigurationProperties;

@ConfigurationProperties(prefix = "agent.employee.adapter")
public class AgentEmployeeAdapterProperties {
	private boolean enabled;
	private String singleTenantRef;
	private String delegatedAudience = "agent-employee-adapter";
	private URI employeeSearchUrl = URI.create("http://127.0.0.1:9210/employees/es/search");

	public boolean isEnabled() { return enabled; }
	public void setEnabled(boolean enabled) { this.enabled = enabled; }
	public String getSingleTenantRef() { return singleTenantRef; }
	public void setSingleTenantRef(String singleTenantRef) { this.singleTenantRef = singleTenantRef; }
	public String getDelegatedAudience() { return delegatedAudience; }
	public void setDelegatedAudience(String delegatedAudience) { this.delegatedAudience = delegatedAudience; }
	public URI getEmployeeSearchUrl() { return employeeSearchUrl; }
	public void setEmployeeSearchUrl(URI employeeSearchUrl) { this.employeeSearchUrl = employeeSearchUrl; }

	@PostConstruct
	public void validate() {
		if (enabled && (singleTenantRef == null || singleTenantRef.isBlank()
				|| delegatedAudience == null || delegatedAudience.isBlank()
				|| employeeSearchUrl == null || employeeSearchUrl.getHost() == null
				|| (!"http".equals(employeeSearchUrl.getScheme()) && !"https".equals(employeeSearchUrl.getScheme())))) {
			throw new IllegalStateException("Employee Adapter requires tenant, audience and Employee Search URL");
		}
	}
}
