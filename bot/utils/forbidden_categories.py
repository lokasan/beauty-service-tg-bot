"""
Модуль проверки запрещенных категорий услуг по странам
"""
import logging

logger = logging.getLogger(__name__)

# Справочник запрещенных категорий (можно расширять по странам)
FORBIDDEN_CATEGORIES = {
    "RU": [
        "азартные игры",
        "казино",
        "ставки",
        "букмекер",
        "наркотики",
        "наркотические вещества",
        "наркотическое средство",
        "психотропные вещества",
        "оружие",
        "оружие огнестрельное",
        "взрывчатые вещества",
        "проституция",
        "интимные услуги",
        "эскорт",
    ],
    "US": [
        "gambling",
        "casino",
        "betting",
        "drugs",
        "narcotics",
        "weapons",
        "firearms",
        "explosives",
        "prostitution",
        "escort services",
    ],
    "ALL": [
        # Общие запрещенные слова для всех стран
    ]
}

FORBIDDEN_KEYWORDS = [
    # Общие запрещенные слова (приведены к нижнему регистру для проверки)
    word for country_words in FORBIDDEN_CATEGORIES.values() 
    for word in country_words
]


def normalize_text(text: str) -> str:
    """Приведение текста к нижнему регистру и удаление лишних символов"""
    return text.lower().strip()


def contains_forbidden_category(text: str, country_code: str = "RU") -> bool:
    """
    Проверка наличия запрещенных категорий в тексте
    
    Args:
        text: Текст для проверки
        country_code: Код страны (по умолчанию RU)
    
    Returns:
        True если найдена запрещенная категория, False иначе
    """
    normalized_text = normalize_text(text)
    
    # Проверка по категориям страны
    country_forbidden = FORBIDDEN_CATEGORIES.get(country_code, [])
    for forbidden_word in country_forbidden:
        if normalize_text(forbidden_word) in normalized_text:
            logger.warning(f"Обнаружена запрещенная категория '{forbidden_word}' в тексте")
            return True
    
    # Проверка общих запрещенных категорий
    for forbidden_word in FORBIDDEN_CATEGORIES.get("ALL", []):
        if normalize_text(forbidden_word) in normalized_text:
            logger.warning(f"Обнаружена запрещенная категория '{forbidden_word}' в тексте")
            return True
    
    return False


def validate_service_name(name: str, description: str = "", country_code: str = "RU") -> tuple[bool, str]:
    """
    Валидация названия и описания услуги
    
    Returns:
        (is_valid, error_message)
    """
    if contains_forbidden_category(name, country_code):
        return False, "Название услуги содержит запрещенную категорию"
    
    if description and contains_forbidden_category(description, country_code):
        return False, "Описание услуги содержит запрещенную категорию"
    
    return True, ""


def add_forbidden_category(category: str, country_code: str = "ALL"):
    """
    Добавление запрещенной категории (для расширения функционала)
    """
    if country_code not in FORBIDDEN_CATEGORIES:
        FORBIDDEN_CATEGORIES[country_code] = []
    
    if category not in FORBIDDEN_CATEGORIES[country_code]:
        FORBIDDEN_CATEGORIES[country_code].append(category)
        logger.info(f"Добавлена запрещенная категория '{category}' для страны '{country_code}'")


