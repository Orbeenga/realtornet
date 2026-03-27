import sys, json


def main():
    data = json.load(sys.stdin)

    tool_input = data.get("tool_input", {})
    path = tool_input.get("file_path") or tool_input.get("path") or ""

    if ".env" in path:
        print("Access to .env files is blocked for security reasons.", file=sys.stderr)
        sys.exit(2)


if __name__ == "__main__":
    main()
