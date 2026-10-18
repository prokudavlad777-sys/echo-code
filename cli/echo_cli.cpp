// Echo Code terminal client (C++17, POSIX sockets, no dependencies).
// Build (Linux/macOS): g++ -std=c++17 -O2 -o echo_cli echo_cli.cpp
// Build (Windows/MinGW): g++ -std=c++17 -O2 -static -o echo_cli.exe echo_cli.cpp -lws2_32
// Usage: ./echo_cli [host] [port]   (defaults: 127.0.0.1 8000; Java gateway: port 8080)
#ifdef _WIN32
#include <winsock2.h>
#include <ws2tcpip.h>
#include <windows.h>
typedef int ssize_t_;
#define CLOSESOCK closesocket
#else
#include <arpa/inet.h>
#include <netdb.h>
#include <sys/socket.h>
#include <unistd.h>
typedef ssize_t ssize_t_;
#define CLOSESOCK close
#endif
#include <cstdio>
#include <cstdlib>

#include <iostream>
#include <sstream>
#include <string>

static std::string json_escape(const std::string& s) {
    std::ostringstream o;
    for (unsigned char c : s) {
        switch (c) {
            case '"': o << "\\\""; break;
            case '\\': o << "\\\\"; break;
            case '\n': o << "\\n"; break;
            case '\r': o << "\\r"; break;
            case '\t': o << "\\t"; break;
            default:
                if (c < 0x20) { char b[8]; snprintf(b, sizeof b, "\\u%04x", c); o << b; }
                else o << c;
        }
    }
    return o.str();
}

static void append_utf8(std::string& out, unsigned cp) {
    if (cp < 0x80) out += (char)cp;
    else if (cp < 0x800) { out += (char)(0xC0 | (cp >> 6)); out += (char)(0x80 | (cp & 0x3F)); }
    else { out += (char)(0xE0 | (cp >> 12)); out += (char)(0x80 | ((cp >> 6) & 0x3F)); out += (char)(0x80 | (cp & 0x3F)); }
}

// Extract a string value for "key" from a flat JSON object.
static std::string json_string(const std::string& js, const std::string& key) {
    size_t p = js.find("\"" + key + "\"");
    if (p == std::string::npos) return "";
    p = js.find('"', js.find(':', p));
    if (p == std::string::npos) return "";
    std::string out;
    for (size_t i = p + 1; i < js.size(); ++i) {
        char c = js[i];
        if (c == '"') break;
        if (c == '\\' && i + 1 < js.size()) {
            char n = js[++i];
            switch (n) {
                case 'n': out += '\n'; break;
                case 't': out += '\t'; break;
                case 'r': out += '\r'; break;
                case 'u': if (i + 4 < js.size()) { append_utf8(out, std::stoul(js.substr(i + 1, 4), nullptr, 16)); i += 4; } break;
                default: out += n;
            }
        } else out += c;
    }
    return out;
}

static long json_int(const std::string& js, const std::string& key) {
    size_t p = js.find("\"" + key + "\"");
    if (p == std::string::npos) return -1;
    p = js.find(':', p);
    return p == std::string::npos ? -1 : std::strtol(js.c_str() + p + 1, nullptr, 10);
}

static std::string http(const std::string& host, const std::string& port, const std::string& method,
                        const std::string& path, const std::string& body) {
    addrinfo hints{}, *res = nullptr;
    hints.ai_socktype = SOCK_STREAM;
    if (getaddrinfo(host.c_str(), port.c_str(), &hints, &res) != 0) return "";
    auto fd = socket(res->ai_family, res->ai_socktype, res->ai_protocol);
    if ((long long)fd < 0 || connect(fd, res->ai_addr, (int)res->ai_addrlen) != 0) { freeaddrinfo(res); if ((long long)fd >= 0) CLOSESOCK(fd); return ""; }
    freeaddrinfo(res);
    std::ostringstream req;
    req << method << " " << path << " HTTP/1.1\r\nHost: " << host << "\r\nConnection: close\r\n"
        << "Content-Type: application/json\r\nContent-Length: " << body.size() << "\r\n\r\n" << body;
    std::string data = req.str();
    for (size_t sent = 0; sent < data.size();) {
        ssize_t_ n = send(fd, data.data() + sent, (int)(data.size() - sent), 0);
        if (n <= 0) break;
        sent += (size_t)n;
    }
    std::string resp;
    char buf[4096];
    ssize_t_ n;
    while ((n = recv(fd, buf, (int)sizeof buf, 0)) > 0) resp.append(buf, (size_t)n);
    CLOSESOCK(fd);
    size_t split = resp.find("\r\n\r\n");
    std::string payload = split == std::string::npos ? "" : resp.substr(split + 4);
    // Handle chunked transfer encoding (used by some gateways).
    if (resp.find("chunked") != std::string::npos && resp.find("chunked") < split) {
        std::string dec;
        size_t i = 0;
        while (i < payload.size()) {
            size_t e = payload.find("\r\n", i);
            if (e == std::string::npos) break;
            size_t len = std::stoul(payload.substr(i, e - i), nullptr, 16);
            if (len == 0) break;
            dec += payload.substr(e + 2, len);
            i = e + 2 + len + 2;
        }
        payload = dec;
    }
    return payload;
}

int main(int argc, char** argv) {
#ifdef _WIN32
    WSADATA wsa;
    if (WSAStartup(MAKEWORD(2, 2), &wsa) != 0) { std::cerr << "WSAStartup failed\n"; return 1; }
    SetConsoleOutputCP(CP_UTF8);
    SetConsoleCP(CP_UTF8);
#endif
    std::string host = argc > 1 ? argv[1] : "127.0.0.1";
    std::string port = argc > 2 ? argv[2] : "8000";
    std::string health = http(host, port, "GET", "/api/health", "");
    if (health.empty()) { std::cerr << "Cannot reach Echo Code at " << host << ":" << port << "\n"; return 1; }
    std::cout << "◈ Echo Code | model: " << json_string(health, "model") << " | /new, /quit\n";
    long chat = json_int(http(host, port, "POST", "/api/chats", "{}"), "id");
    std::string line;
    while (std::cout << "\nyou> " && std::getline(std::cin, line)) {
        if (line == "/quit") break;
        if (line == "/new") { chat = json_int(http(host, port, "POST", "/api/chats", "{}"), "id"); std::cout << "new chat " << chat << "\n"; continue; }
        if (line.empty()) continue;
        std::string r = http(host, port, "POST", "/api/chats/" + std::to_string(chat) + "/messages",
                             "{\"content\":\"" + json_escape(line) + "\"}");
        std::string reply = json_string(r, "reply");
        std::cout << "\necho> " << (reply.empty() ? "(no reply) " + r : reply) << "\n";
    }
    return 0;
}
