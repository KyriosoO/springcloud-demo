package com.dylan.common.security;

import java.time.Duration;
import java.util.ArrayList;
import java.util.List;

import org.springframework.boot.context.properties.ConfigurationProperties;

/**
 * 服务 token 配置属性，定义服务身份、有效期和默认权限范围。
 */
@ConfigurationProperties(prefix = "common.security.service-token")
public class ServiceTokenProperties {
	/**
	 * 是否启用服务 token 兜底签发。
	 */
	private boolean enabled = true;
	/**
	 * 当前服务身份标识，默认使用 spring.application.name。
	 */
	private String serviceId;
	/**
	 * 服务 token 有效期。
	 */
	private Duration ttl = Duration.ofSeconds(300);
	/**
	 * 服务 token 携带的权限范围。
	 */
	private List<String> scopes = new ArrayList<>();

	public boolean isEnabled() {
		return enabled;
	}

	public void setEnabled(boolean enabled) {
		this.enabled = enabled;
	}

	public String getServiceId() {
		return serviceId;
	}

	public void setServiceId(String serviceId) {
		this.serviceId = serviceId;
	}

	public Duration getTtl() {
		return ttl;
	}

	public void setTtl(Duration ttl) {
		this.ttl = ttl;
	}

	public List<String> getScopes() {
		return scopes;
	}

	public void setScopes(List<String> scopes) {
		this.scopes = scopes == null ? new ArrayList<>() : scopes;
	}
}
