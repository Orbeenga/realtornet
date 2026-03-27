import subprocess


def main():
    subprocess.run(["black", "."], capture_output=True)


if __name__ == "__main__":
    main()
