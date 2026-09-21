"""分页与序列化小工具"""
import time


def get_page(query_params, default_size: int = 10) -> tuple[int, int, int]:
    """返回 (page, page_size, offset)"""
    try:
        page = max(int(query_params.get("page", 1)), 1)
    except Exception:
        page = 1
    try:
        page_size = min(max(int(query_params.get("page_size", default_size)), 1), 200)
    except Exception:
        page_size = default_size
    return page, page_size, (page - 1) * page_size


def clean_row(row: dict, drop: tuple = ("password",)) -> dict:
    return {k: v for k, v in row.items() if k not in drop}


async def page_query(qs, page: int, page_size: int, offset: int, order: str = "-id"):
    total = await qs.count()
    items = await qs.offset(offset).limit(page_size).order_by(order).values()
    return total, items
