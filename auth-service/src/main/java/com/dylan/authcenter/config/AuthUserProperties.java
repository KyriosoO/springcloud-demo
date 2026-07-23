package com.dylan.authcenter.config;

import java.util.LinkedHashMap;
import java.util.LinkedHashSet;
import java.util.Map;
import java.util.Set;

import org.springframework.beans.factory.InitializingBean;
import org.springframework.boot.context.properties.ConfigurationProperties;
import org.springframework.stereotype.Component;

/**
 * auth-service 的本地用户配置。
 */
@Component
@ConfigurationProperties(prefix = "auth")
public class AuthUserProperties implements InitializingBean {

	private Map<String, UserDefinition> users = new LinkedHashMap<>();

	public Map<String, UserDefinition> getUsers() {
		return users;
	}

	public void setUsers(Map<String, UserDefinition> users) {
		this.users = users == null ? new LinkedHashMap<>() : new LinkedHashMap<>(users);
	}

	@Override
	public void afterPropertiesSet() {
		if (users.isEmpty()) {
			throw new IllegalStateException("auth.users must not be empty");
		}
		users.forEach((userId, user) -> {
			if (userId == null || userId.isBlank()) {
				throw new IllegalStateException("auth.users key must not be blank");
			}
			if (user == null || user.password == null || user.password.isBlank()) {
				throw new IllegalStateException("auth.users." + userId + ".password must not be blank");
			}
			if (user.roles.isEmpty()) {
				throw new IllegalStateException("auth.users." + userId + ".roles must not be empty");
			}
			if (user.roles.stream().anyMatch(role -> role == null || role.isBlank())) {
				throw new IllegalStateException("auth.users." + userId + ".roles must not contain blank values");
			}
		});
	}

	public static class UserDefinition {
		private String password;
		private Set<String> roles = new LinkedHashSet<>();

		public String getPassword() {
			return password;
		}

		public void setPassword(String password) {
			this.password = password;
		}

		public Set<String> getRoles() {
			return roles;
		}

		public void setRoles(Set<String> roles) {
			this.roles = roles == null ? new LinkedHashSet<>() : new LinkedHashSet<>(roles);
		}
	}
}
