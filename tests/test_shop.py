import pytest
from src.shop.database import init_db, get_product_count, get_product


def test_shop_inventory():
    init_db()
    assert get_product_count() == 2
    product = get_product(1)
    assert product is not None
    assert product["name"] == "Espresso Mug"
    assert product["price"] == 12.99
    assert product["stock"] == 50
