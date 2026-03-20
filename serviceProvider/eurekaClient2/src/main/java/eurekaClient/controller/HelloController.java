package eurekaClient.controller;


import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RestController;

@RestController
public class HelloController {
	Logger log = LoggerFactory.getLogger(HelloController.class);

	@Value("${server.port}")
	private int port;

	@GetMapping("/index")
	public String index(String user) {
     		return user + "!! Hello World! from " + port;
	}
}
