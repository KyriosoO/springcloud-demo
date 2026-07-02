package com.dylan.authcenter.service;

import java.util.Arrays;
import java.util.Set;
import java.util.Map;
import java.util.concurrent.ConcurrentHashMap;
import java.util.stream.Collectors;

import org.springframework.security.core.Authentication;
import org.springframework.security.core.context.SecurityContextHolder;
import org.springframework.security.core.userdetails.User;
import org.springframework.security.core.userdetails.UserDetails;
import org.springframework.security.core.userdetails.UserDetailsService;
import org.springframework.security.core.userdetails.UsernameNotFoundException;
import org.springframework.security.oauth2.jwt.Jwt;
import org.springframework.stereotype.Service;

@Service
public class UserService implements UserDetailsService {
	String[] users = new String[] { "admin", "dylan", "viewer_t" };
	private static Map<String, String[]> userMap = new ConcurrentHashMap<String, String[]>();
	static {
		userMap.put("admin", new String[] {"ADMIN","agent:admin"});
		userMap.put("dylan", new String[] {"agent:admin"});
		userMap.put("viewer_t", new String[] {"agent:viewer"});
	}

	@Override
	public UserDetails loadUserByUsername(String userId) throws UsernameNotFoundException {
		if (userMap.containsKey(userId)) {
			return User.builder().username(userId).password("{noop}123456").roles(userMap.get(userId)).build();
		}else {
			throw new UsernameNotFoundException("User not found");
		}
	}

	public Set<String> rolesOf(String userId) {
		String[] roles = userMap.get(userId);
		if (roles == null) {
			throw new UsernameNotFoundException("User not found");
		}
		return Arrays.stream(roles).collect(Collectors.toUnmodifiableSet());
	}

	public String getCurrentUserId() {
		Authentication authentication = SecurityContextHolder.getContext().getAuthentication();
		if (authentication == null)
			return null;
		// OAuth2 用户
		if (authentication.getPrincipal() instanceof Jwt jwt) {
			// JWT claims
			return jwt.getClaimAsString("sub"); // 或 "userId" 根据你 token 定义
		}
		return null;
	}
}
