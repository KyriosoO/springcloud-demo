//package eurekaClient.config;
//
//import javax.crypto.spec.SecretKeySpec;
//
//import org.springframework.context.annotation.Bean;
//import org.springframework.context.annotation.Configuration;
//import org.springframework.security.oauth2.jwt.JwtDecoder;
//import org.springframework.security.oauth2.jwt.JwtEncoder;
//import org.springframework.security.oauth2.jwt.NimbusJwtDecoder;
//import org.springframework.security.oauth2.jwt.NimbusJwtEncoder;
//
//import com.nimbusds.jose.jwk.source.ImmutableSecret;
//
//@Configuration
//public class JwtConfig {
//
//	private static final String SECRET = "my-super-secret-key-my-super-secret-key";
//
//	@Bean
//	public JwtDecoder jwtDecoder() {
//		SecretKeySpec key = new SecretKeySpec(SECRET.getBytes(), "HmacSHA256");
//		return NimbusJwtDecoder.withSecretKey(key).build();
//	}
//
//	@Bean
//	public JwtEncoder jwtEncoder() {
//		SecretKeySpec key = new SecretKeySpec(SECRET.getBytes(), "HmacSHA256");
//		return new NimbusJwtEncoder(new ImmutableSecret<>(key));
//	}
//}