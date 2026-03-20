package authCenter;

import java.io.IOException;
import java.net.URI;
import java.net.http.HttpClient;
import java.net.http.HttpRequest;
import java.net.http.HttpResponse;

public class Test {
	static String token = "eyJhbGciOiJIUzI1NiJ9.eyJleHAiOjE3NzMzNjk1NTYsInN1YiI6ImFkbWluIiwiaWF0IjoxNzczMzY1OTU2fQ.WsP9peQN-5AUwS2IxDPmYPpAXf-FGhn47RxHdrwpv8I";

	public static void main(String[] args) throws IOException, InterruptedException {
		Test.docheck();
	}

	public static void login() throws IOException, InterruptedException {
		HttpClient client = HttpClient.newHttpClient();
		String json = """
				{
				  "username":"admin",
				  "password":"123456"
				}
				""";

		HttpRequest request = HttpRequest.newBuilder().uri(URI.create("http://localhost:8888/login"))
				.header("Content-Type", "application/json").POST(HttpRequest.BodyPublishers.ofString(json)).build();
		HttpResponse<String> response = client.send(request, HttpResponse.BodyHandlers.ofString());
		System.out.println("Login response: " + response.body());
	}

	public static void doRequest() throws IOException, InterruptedException {
		HttpClient client = HttpClient.newHttpClient();
		HttpRequest request = HttpRequest.newBuilder().uri(URI.create("http://localhost:8888/test?user=admin"))
				.header("Authorization", "Bearer " + token).GET().build();
		HttpResponse<String> response = client.send(request, HttpResponse.BodyHandlers.ofString());
		System.out.println("Login response: " + response.toString());
		System.out.println("Login response: " + response.body());
	}

	public static void docheck() throws IOException, InterruptedException {
		HttpClient client = HttpClient.newHttpClient();
		HttpRequest request = HttpRequest.newBuilder().uri(URI.create("http://localhost:8888/api"))
				.header("Authorization", "Bearer " + token).GET().build();
		HttpResponse<String> response = client.send(request, HttpResponse.BodyHandlers.ofString());
		System.out.println("Login response: " + response.toString());
		System.out.println("Login response: " + response.body());
	}
}
