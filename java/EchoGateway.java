import com.sun.net.httpserver.HttpExchange;
import com.sun.net.httpserver.HttpServer;

import java.io.IOException;
import java.io.OutputStream;
import java.net.InetSocketAddress;
import java.net.URI;
import java.net.http.HttpClient;
import java.net.http.HttpRequest;
import java.net.http.HttpResponse;
import java.nio.file.Files;
import java.nio.file.Path;
import java.time.Duration;
import java.util.concurrent.Executors;

/**
 * Echo Code gateway (Java 11+, no dependencies).
 * Public server on :8080 -> serves ../web and proxies /api/* to the Python core on :8000.
 * Adds CORS headers and a simple per-IP rate limit.
 * Run: java EchoGateway.java   (env: ECHO_GATEWAY_PORT, ECHO_CORE_URL, ECHO_WEB_DIR)
 */
public class EchoGateway {
    static final String CORE = System.getenv().getOrDefault("ECHO_CORE_URL", "http://127.0.0.1:8000");
    static final int PORT = Integer.parseInt(System.getenv().getOrDefault("ECHO_GATEWAY_PORT", "8080"));
    static final Path WEB = Path.of(System.getenv().getOrDefault("ECHO_WEB_DIR", "web")).toAbsolutePath().normalize();
    static final int LIMIT_PER_MIN = 60;
    static final HttpClient CLIENT = HttpClient.newBuilder().connectTimeout(Duration.ofSeconds(5)).build();
    static final java.util.concurrent.ConcurrentHashMap<String, long[]> HITS = new java.util.concurrent.ConcurrentHashMap<>();

    public static void main(String[] args) throws IOException {
        HttpServer server = HttpServer.create(new InetSocketAddress(PORT), 0);
        server.createContext("/api/", EchoGateway::proxy);
        server.createContext("/", EchoGateway::staticFile);
        server.setExecutor(Executors.newFixedThreadPool(16));
        server.start();
        System.out.println("Echo Gateway on http://127.0.0.1:" + PORT + " -> " + CORE);
    }

    static boolean allowed(String ip) {
        long minute = System.currentTimeMillis() / 60_000;
        long[] slot = HITS.compute(ip, (k, v) -> (v == null || v[0] != minute) ? new long[]{minute, 1} : new long[]{minute, v[1] + 1});
        return slot[1] <= LIMIT_PER_MIN;
    }

    static void send(HttpExchange ex, int code, String type, byte[] body) throws IOException {
        ex.getResponseHeaders().set("Content-Type", type);
        ex.getResponseHeaders().set("Access-Control-Allow-Origin", "*");
        ex.getResponseHeaders().set("Access-Control-Allow-Headers", "Content-Type");
        ex.getResponseHeaders().set("Access-Control-Allow-Methods", "GET,POST,DELETE,OPTIONS");
        ex.sendResponseHeaders(code, body.length == 0 ? -1 : body.length);
        if (body.length > 0) try (OutputStream os = ex.getResponseBody()) { os.write(body); }
        ex.close();
    }

    static void proxy(HttpExchange ex) throws IOException {
        try {
            if (ex.getRequestMethod().equals("OPTIONS")) { send(ex, 204, "text/plain", new byte[0]); return; }
            if (!allowed(ex.getRemoteAddress().getAddress().getHostAddress())) {
                send(ex, 429, "application/json", "{\"error\":\"rate limit\"}".getBytes()); return;
            }
            byte[] in = ex.getRequestBody().readAllBytes();
            HttpRequest.Builder b = HttpRequest.newBuilder(URI.create(CORE + ex.getRequestURI()))
                    .timeout(Duration.ofMinutes(5))
                    .header("Content-Type", "application/json")
                    .method(ex.getRequestMethod(), in.length == 0 ? HttpRequest.BodyPublishers.noBody() : HttpRequest.BodyPublishers.ofByteArray(in));
            HttpResponse<byte[]> r = CLIENT.send(b.build(), HttpResponse.BodyHandlers.ofByteArray());
            send(ex, r.statusCode(), "application/json; charset=utf-8", r.body());
        } catch (InterruptedException e) {
            Thread.currentThread().interrupt();
            send(ex, 500, "application/json", "{\"error\":\"interrupted\"}".getBytes());
        } catch (Exception e) {
            send(ex, 502, "application/json", "{\"error\":\"core unavailable\"}".getBytes());
        }
    }

    static void staticFile(HttpExchange ex) throws IOException {
        String p = ex.getRequestURI().getPath();
        Path f = WEB.resolve(p.equals("/") ? "index.html" : p.substring(1)).normalize();
        if (!f.startsWith(WEB) || !Files.isRegularFile(f)) { send(ex, 404, "text/plain", "not found".getBytes()); return; }
        String n = f.getFileName().toString();
        String type = n.endsWith(".html") ? "text/html; charset=utf-8" : n.endsWith(".css") ? "text/css; charset=utf-8"
                : n.endsWith(".js") ? "application/javascript; charset=utf-8" : "application/octet-stream";
        send(ex, 200, type, Files.readAllBytes(f));
    }
}
