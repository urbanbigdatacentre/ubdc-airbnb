from jsonpath_ng import parse


# noinspection PyPep8Naming
class airbnb_response_parser:
    __profile_pics_parser__ = parse(
        r"$.user.[picture_url,picture_url_large,picture_url,thumbnail_url]"
    )
    __listings_count__ = parse(r"$..listings_count")

    @classmethod
    def profile_pics(cls, response):
        return [match.value for match in cls.__profile_pics_parser__.find(response)]

    @classmethod
    def listing_count(cls, response):
        matches = set(match.value for match in cls.__listings_count__.find(response))
        if len(matches) != 1:
            raise Exception("multiple listing_count values.. hmm?")
        return matches.pop()
