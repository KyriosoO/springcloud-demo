package eurekaClient.controller;

import org.springframework.beans.factory.annotation.Value;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RestController;

@RestController
public class HelloController {
	@Value("${server.port}")
	private int port;

	@GetMapping("/index")
	public String index(String user) {
		return user + "!! Hello World! from " + port;
	}
}
