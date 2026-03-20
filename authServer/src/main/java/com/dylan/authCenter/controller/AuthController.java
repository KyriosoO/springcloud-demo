package com.dylan.authCenter.controller;

import java.time.Duration;

import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.http.HttpHeaders;
import org.springframework.http.ResponseCookie;
import org.springframework.http.ResponseEntity;
import org.springframework.security.core.Authentication;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RestController;

import com.dylan.authCenter.model.LoginRequest;
import com.dylan.authCenter.service.JwtService;

import jakarta.servlet.http.HttpServletResponse;

@RestController
public class AuthController {

	@Autowired
	private JwtService jwtService;

	@PostMapping("/login")
	public ResponseEntity<?> login(@RequestBody LoginRequest request, HttpServletResponse response) {
		String token = jwtService.generateToken(request.getUsername());
		ResponseCookie cookie = ResponseCookie.from("AUTH_TOKEN", token).httpOnly(true).secure(false) // 本地开发
				.path("/").maxAge(Duration.ofHours(1)).sameSite("Lax").build();
		response.addHeader(HttpHeaders.SET_COOKIE, cookie.toString());
		return ResponseEntity.ok().build();
	}

	@GetMapping("/public/test")
	public String test() {
		return "ok";
	}

	@GetMapping("/my")
	public String hello(Authentication authentication) {
		return "Hello " + authentication.getName();
	}
}