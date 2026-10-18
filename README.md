# ◈ Echo Code

A self-hostable coding assistant. Python core + ~1.5B-parameter model, web UI, terminal client, system watchdog, Java gateway, SQL chat storage.

| Part | Language | Path |
|---|---|---|
| AI core, REST API | Python | `echo_code/` |
| Model (1.5B params) | Python (Hugging Face) | `echo_code/model.py` |
| Chat & info storage | SQL (SQLite) | `sql/schema.sql`, `echo_code/db.py` |
| Web interface | JavaScript + CSS | `web/` |
| Terminal interface | C++ | `cli/echo_cli.cpp` |
| System component (health, RAM check) | Rust | `rust/` |
| Server gateway (proxy, static, rate limit) | Java 11+ | `java/EchoGateway.java` |

## Quick start (demo mode, zero dependencies)

```bash
./run.sh                 # http://127.0.0.1:8000
./run.sh gateway         # also Java gateway on http://127.0.0.1:8080
python3 -m unittest discover -s tests -v
```

## Real 1.5B model

"1.5B" means 1.5 billion parameters (~3 GB in bf16, ~6 GB in fp32). Default: `Qwen/Qwen2.5-Coder-1.5B-Instruct`
(check its license before commercial use). Training a model from scratch is not part of this repo.

```bash
pip install -r requirements.txt
ECHO_BACKEND=transformers ./run.sh
# another model:  ECHO_MODEL=<hf-id>
```

## Other components

```bash
g++ -std=c++17 -O2 -o echo_cli cli/echo_cli.cpp && ./echo_cli 127.0.0.1 8000
cd rust && cargo build --release && ./target/release/echo-guard status
java java/EchoGateway.java
```

## Windows .exe

Automatic: push a tag (`git tag v1.0.0 && git push --tags`) or run **Build Windows EXE** in the Actions tab. It produces
`echo-code.exe`, `echo-cli.exe`, `echo-guard.exe` and the `EchoGateway` app (artifact `echo-code-windows`, plus a GitHub Release on tags).

Manual (Windows):

```bash
pip install pyinstaller
pyinstaller --onefile --name echo-code --add-data "web;web" --add-data "sql;sql" run_echo.py
g++ -std=c++17 -O2 -static -o echo-cli.exe cli/echo_cli.cpp -lws2_32
cargo build --release --manifest-path rust/Cargo.toml
```

The exe runs in demo mode; for the real 1.5B model run the Python version with `ECHO_BACKEND=transformers`
(bundling torch would make the exe several GB).

## API

`GET /api/health` · `GET/POST /api/chats` · `GET/DELETE /api/chats/{id}` · `POST /api/chats/{id}/messages` `{"content": "..."}`

## Environment

`ECHO_HOST`, `ECHO_PORT` (8000), `ECHO_DB`, `ECHO_BACKEND` (`demo`|`transformers`), `ECHO_MODEL`, `ECHO_GATEWAY_PORT` (8080), `ECHO_CORE_URL`.

The API has no authentication: keep it on localhost or put it behind a reverse proxy with auth before exposing it.
