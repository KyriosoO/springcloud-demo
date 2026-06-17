package com.dylan.authcenter.controller;

import java.time.Duration;

import org.springframework.http.HttpHeaders;
import org.springframework.http.ResponseCookie;
import org.springframework.http.ResponseEntity;
import org.springframework.security.authentication.AuthenticationManager;
import org.springframework.security.authentication.UsernamePasswordAuthenticationToken;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RestController;

import com.dylan.authcenter.model.LoginRequest;
import com.dylan.authcenter.service.JwtService;
import com.dylan.authcenter.service.UserService;

import jakarta.servlet.http.HttpServletResponse;

@RestController
public class AuthController {

	private final JwtService jwtService;
	private final UserService userService;
	private final AuthenticationManager authenticationManager;

	public AuthController(JwtService jwtService, UserService userService, AuthenticationManager authenticationManager) {
		this.jwtService = jwtService;
		this.userService = userService;
		this.authenticationManager = authenticationManager;
	}

	@PostMapping("/login")
	public ResponseEntity<?> login(@RequestBody LoginRequest request, HttpServletResponse response) {
//		authenticationManager.authenticate(
//				new UsernamePasswordAuthenticationToken(request.getUserId(), request.getPassword()));
		String token = jwtService.generateToken(request.getUserId());
		ResponseCookie cookie = ResponseCookie.from("AUTH_TOKEN", token).httpOnly(true).secure(false) // 本地开发
				.path("/").maxAge(Duration.ofHours(1)).sameSite("Lax").build();
		response.addHeader(HttpHeaders.SET_COOKIE, cookie.toString());
		return ResponseEntity.ok().build();
	}

	@GetMapping("/public/test")
	public String test() {
		return "ok";
	}

	@GetMapping("/as/getUserId")
	public String getUserId() {
		return userService.getCurrentUserId();
	}

	@GetMapping("/as/my")
	public String hello() {
		return "Hello " + userService.getCurrentUserId();
	}
}
