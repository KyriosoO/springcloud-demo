package com.dylan.authCenter.service;

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

	@Override
	public UserDetails loadUserByUsername(String username) throws UsernameNotFoundException {
		if (!username.equals("admin")) {
			throw new UsernameNotFoundException("User not found");
		}
		return User.builder().username("admin").password("{noop}123456").roles("ADMIN").build();
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