import subprocess


def main():
    print("Running pytest after code change...")

    result = subprocess.run(
        ["pytest", "tests/", "-q"],
        capture_output=True,
        text=True
    )

    print(result.stdout)
    print(result.stderr)


if __name__ == "__main__":
    main()
