DEFAULT_CATEGORY = "Другое"
KEYWORDS = {
    "Еда": ("кафе", "ресторан", "обед", "продукт", "магазин", "кофе", "еда"),
    "Транспорт": ("такси", "бензин", "автобус", "транспорт", "заправка"),
    "Дом": ("аренда", "квартира", "коммунал", "интернет"),
    "Здоровье": ("аптека", "врач", "лекарств"),
    "Покупки": ("одежд", "покупк", "маркетплейс"),
}

def categorize(description: str) -> str:
    text = description.lower()
    return next((category for category, words in KEYWORDS.items() if any(word in text for word in words)), DEFAULT_CATEGORY)
