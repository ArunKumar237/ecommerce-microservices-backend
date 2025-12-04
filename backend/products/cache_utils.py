from django_redis import get_redis_connection

def clear_product_caches():
    conn = get_redis_connection("default")
    # delete keys matching product_detail:*
    keys = conn.keys("product_detail:*")
    if keys:
        conn.delete(*keys)
    # delete Django per-view cache keys (if you used cache_page)
    cache_keys = conn.keys("views.decorators.cache*")
    if cache_keys:
        conn.delete(*cache_keys)
