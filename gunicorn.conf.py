# gunicorn.conf.py
workers = 4  # Adjust based on your CPU cores
threads = 2
bind = '0.0.0.0:5000'
worker_class = 'gthread'

def post_fork(server, worker):
    """
    Called in the worker process after it has been forked.
    This is the perfect place to initialize process-specific resources.
    """
    from renderer import initialize_playwright_pool
    initialize_playwright_pool()
