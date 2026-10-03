from flask import request

DEFAULT_PER_PAGE = 20
MAX_PER_PAGE = 50
MAX_LIMIT_WITHOUT_PAGINATION = 100

def paginate_query(query, default_per_page=DEFAULT_PER_PAGE, max_per_page=MAX_PER_PAGE):
    """
    Si el request tiene ?page, devuelve dict paginado:
    {items, total, page, per_page, pages, truncated}
    Si no tiene ?page y el total <= MAX_LIMIT, devuelve lista (compatibilidad).
    Si supera el límite, devuelve dict paginado page=1 con truncated=True
    para no perder registros en silencio.
    """
    page = request.args.get("page", type=int)
    per_page = request.args.get("per_page", type=int)
    if page is None:
        total = query.count()
        if total <= MAX_LIMIT_WITHOUT_PAGINATION:
            items = query.limit(MAX_LIMIT_WITHOUT_PAGINATION).all()
            return items, False
        items = query.limit(MAX_LIMIT_WITHOUT_PAGINATION).all()
        pages = (total + MAX_LIMIT_WITHOUT_PAGINATION - 1) // MAX_LIMIT_WITHOUT_PAGINATION if total else 1
        return {
            "items": items,
            "total": total,
            "page": 1,
            "per_page": MAX_LIMIT_WITHOUT_PAGINATION,
            "pages": pages,
            "truncated": True,
        }, True
    # Con paginación
    if per_page is None:
        per_page = default_per_page
    per_page = max(1, min(per_page, max_per_page))
    page = max(1, page)
    total = query.count()
    items = query.offset((page - 1) * per_page).limit(per_page).all()
    pages = (total + per_page - 1) // per_page if total else 1
    return {
        "items": items,
        "total": total,
        "page": page,
        "per_page": per_page,
        "pages": pages,
        "truncated": False,
    }, True
