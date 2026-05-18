from extract import extract_uid


def main() -> None:
    html = (
        '<script>self.__pace_f.push([1,"{\\\\\\"from_uid\\\\\\":33230788575605404,'
        '\\\\\\"to_uid\\\\\\":4356697517726384,\\\\\\"to_mid\\\\\\":4356697517726384}"]);'
        "</script>"
    )
    print(extract_uid(html))


if __name__ == "__main__":
    main()

