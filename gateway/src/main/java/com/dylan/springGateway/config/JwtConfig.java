//package com.dylan.springGateway.config;
//
//import javax.crypto.spec.SecretKeySpec;
//
//import org.springframework.context.annotation.Bean;
//import org.springframework.context.annotation.Configuration;
//import org.springframework.security.oauth2.jwt.NimbusReactiveJwtDecoder;
//import org.springframework.security.oauth2.jwt.ReactiveJwtDecoder;
//
//@Configuration
//public class JwtConfig {
//
//	private static final String SECRET = "my-super-secret-key-my-super-secret-key";
//
//	@Bean
//	public ReactiveJwtDecoder jwtDecoder() {
//		SecretKeySpec key = new SecretKeySpec(SECRET.getBytes(), "HmacSHA256");
//		return NimbusReactiveJwtDecoder.withSecretKey(key).build();
//	}
//}