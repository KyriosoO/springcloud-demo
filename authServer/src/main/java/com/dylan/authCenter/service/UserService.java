package com.dylan.authCenter.service;

import org.springframework.security.core.userdetails.User;
import org.springframework.security.core.userdetails.UserDetails;
import org.springframework.security.core.userdetails.UserDetailsService;
import org.springframework.security.core.userdetails.UsernameNotFoundException;
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
}