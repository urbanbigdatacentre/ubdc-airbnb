from typing import Any, Iterator

from jsonpath_ng import parse


# noinspection PyPep8Naming
class airbnb_response_parser:
    __primary_host__ = parse(r"$..primary_host")
    __additional_hosts__ = parse(r"$..additional_hosts")
    __user_object__ = parse(r"$..user")
    __profile_pics_parser__ = parse(r"$.user.[picture_url,picture_url_large,picture_url,thumbnail_url]")
    __listings_count__ = parse(r"$..listings_count")
    __price_histogram__ = parse(r"$..price_histogram.histogram")
    __has_next_page__ = parse(r"$..pagination_metadata.has_next_page")

    @staticmethod
    def generic(pattern: str, target: dict) -> Iterator[Any]:
        parser = parse(pattern)
        matches = parser.find(target)
        for match in matches:
            yield match.value

    @classmethod
    def get_user_objects_from_search(cls, response: dict) -> list[dict]:
        matches = cls.__user_object__.find(response)
        return [m.value for m in matches]

    @classmethod
    def has_next_page(cls, response: dict) -> bool:
        matches = cls.__has_next_page__.find(response)
        if len(matches) == 0:
            raise Exception("No has_next_page found in response")
        return matches[0].value

    @classmethod
    def price_histogram_sum(cls, response: dict):
        matches = cls.__price_histogram__.find(response)
        first = matches[0]

        return sum([int(e) for e in first.value])

    @classmethod
    def profile_pics(cls, response):
        return [match.value for match in cls.__profile_pics_parser__.find(response)]

    @classmethod
    def listing_count(cls, response):
        matches = set(match.value for match in cls.__listings_count__.find(response))
        if len(matches) != 1:
            raise Exception("multiple listing_count values.. hmm?")
        return matches.pop()
