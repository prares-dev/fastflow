from .parser import Parser


def main() -> None:
    parser = Parser()
    parser.start_parsing()

if __name__ == "__main__":
    main()