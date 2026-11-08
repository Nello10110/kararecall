# Use KaraRecall from an assistant

[🇫🇷 Français](../MCP.md) · [🇬🇧 English](mcp.md)

The MCP adapter runs on the assistant's machine and reads KaraRecall's authenticated web API. It exposes five bounded, read-only tools: `search`, `get_tool`, `get_source`, `get_evidence` and `get_context`. Results retain `BOOKMARK_ID#EVIDENCE_ID`, original URLs and available page/timestamp information.

## Setup

On the assistant's machine, clone the repository and use Python 3.10 or newer:

```sh
python3 -m venv .venv-mcp
.venv-mcp/bin/python -m pip install -r requirements/mcp.txt
```

Create a private root `.env.mcp`, with `chmod 600 .env.mcp`:

```dotenv
KARARECALL_URL=https://kararecall.example.net
KARARECALL_USERNAME=admin
KARARECALL_PASSWORD=REPLACE_WITH_YOUR_WEB_PASSWORD
```

Use the NAS URL reachable from the assistant machine. For a same-machine trial, `http://127.0.0.1:8765` is supported. Authentication uses the web account.

In a client supporting local MCP servers, select **stdio**, set the command to the absolute `.venv-mcp/bin/python` path, and pass the absolute path to `scripts/assistant_mcp.py` as its argument. This wrapper resolves the repository package from any working directory. The client starts the process and communicates through stdin/stdout. [SDK transport reference](https://py.sdk.modelcontextprotocol.io/run/).

Alternatively, build the adapter image:

```sh
docker build --target mcp -t kararecall-mcp:local .
```

Use `docker` as the client command with arguments `run --rm -i --env-file /absolute/path/.env.mcp kararecall-mcp:local`. The configured NAS URL must be reachable from that container; its `127.0.0.1` is the adapter container itself.

## Access and validation

The adapter sends only GET requests and refuses redirects. It has no tools for import, editing or program execution. Evidence/context responses are bounded and paginated. A remote-only MCP client would need an additional authenticated Streamable HTTP service; this is not provided by the current stdio adapter.

Ask an assistant to recover a tool from its purpose, cite the original passage, fetch exact evidence and answer a question absent from the library. It should preserve attribution and abstain when information is missing. Integration tests cover stdio, authenticated reading, timestamped citations, bounded output and absent data on fictional content. Actual natural-language/voice client behavior still requires a real pilot.
