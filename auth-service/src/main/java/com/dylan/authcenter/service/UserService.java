package com.dylan.authcenter.service;

import java.util.Set;

import org.springframework.security.core.Authentication;
import org.springframework.security.core.context.SecurityContextHolder;
import org.springframework.security.core.userdetails.User;
import org.springframework.security.core.userdetails.UserDetails;
import org.springframework.security.core.userdetails.UserDetailsService;
import org.springframework.security.core.userdetails.UsernameNotFoundException;
import org.springframework.security.oauth2.jwt.Jwt;
import org.springframework.stereotype.Service;

import com.dylan.authcenter.config.AuthRbacProperties;

@Service
public class UserService implements UserDetailsService {
	private final AuthRbacProperties rbacProperties;

	public UserService(AuthRbacProperties rbacProperties) {
		this.rbacProperties = rbacProperties;
	}

	@Override
	public UserDetails loadUserByUsername(String userId) throws UsernameNotFoundException {
		AuthRbacProperties.UserDefinition user = rbacProperties.getUsers().get(userId);
		if (user == null) {
			throw new UsernameNotFoundException("User not found");
		}
		return User.builder()
				.username(userId)
				.password(user.getPassword())
				.authorities(user.getRoles().toArray(String[]::new))
				.build();
	}

	public Set<String> rolesOf(String userId) {
		AuthRbacProperties.UserDefinition user = rbacProperties.getUsers().get(userId);
		if (user == null) {
			throw new UsernameNotFoundException("User not found");
		}
		return Set.copyOf(user.getRoles());
	}

	public String getCurrentUserId() {
		Authentication authentication = SecurityContextHolder.getContext().getAuthentication();
		if (authentication == null)
			return null;
		// OAuth2 用户
		if (authentication.getPrincipal() instanceof Jwt jwt) {
			// JWT 声明
			return jwt.getClaimAsString("sub"); // 或 "userId" 根据你 token 定义
		}
		return null;
	}
}
