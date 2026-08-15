from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

BRAWL_PASS_PRICES = {
    "brawl_pass": (2500, 3400),
    "brawl_pass_plus": (3400, 4800),
}


def is_brawl_pass(product: str) -> bool:
    return product in {"Brawl Pass", "Brawl Pass+"}


def pass_type(product: str) -> str:
    return "brawl_pass" if product == "Brawl Pass" else "brawl_pass_plus"


def price_keyboard(uid: int, product: str):
    low, high = BRAWL_PASS_PRICES[pass_type(product)]
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text=f"💰 {low:,} ֏".replace(",", " "), callback_data=f"passprice:{uid}:{low}"),
        InlineKeyboardButton(text=f"💰 {high:,} ֏".replace(",", " "), callback_data=f"passprice:{uid}:{high}"),
    ]])
