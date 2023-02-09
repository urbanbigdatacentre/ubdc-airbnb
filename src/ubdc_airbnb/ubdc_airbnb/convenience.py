from urllib.parse import parse_qsl, urlsplit


def query_params_from_url(url: str, strict_parsing=False) -> dict:
    # strict_parsing = Raise an error if there's parsing error

    url_elements = urlsplit(url)
    parsed_query = parse_qsl(url_elements.query, keep_blank_values=True)

    return dict(parsed_query)
