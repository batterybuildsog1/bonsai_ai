from __future__ import annotations

import argparse

import uvicorn


def main() -> None:
    parser = argparse.ArgumentParser(prog="bonsai-ai-bridge")
    subparsers = parser.add_subparsers(dest="command", required=True)

    serve = subparsers.add_parser("serve", help="Start the local HTTP bridge")
    serve.add_argument("--host", default="127.0.0.1")
    serve.add_argument("--port", type=int, default=8765)

    args = parser.parse_args()
    if args.command == "serve":
        uvicorn.run("bonsai_ai_bridge.server:app", host=args.host, port=args.port, reload=False)


if __name__ == "__main__":
    main()
