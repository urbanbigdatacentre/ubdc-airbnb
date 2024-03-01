from datetime import datetime

import factory


class Price:
    def __init__(self, for_day: datetime.date = datetime.utcnow().date):
        self.for_day = for_day

        date = str(for_day)
        type = "demand_based_pricing"
        local_price = 21
        native_price = 21.0
        local_currency = "GBP"
        native_currency = "GBP"
        local_adjusted_price = 21
        is_price_upon_request = None
        local_price_formatted = "£21"
        native_adjusted_price = 21


class CalendarResponseFactory(factory.Factory):
    metadata: []
    calendar_months = factory.SubFactory()
