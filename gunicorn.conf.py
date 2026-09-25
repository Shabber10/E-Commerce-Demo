import os
import multiprocessing

# Bind to 0.0.0.0 and PORT assigned by Render (defaults to 10000 on Render)
port = os.environ.get("PORT", "10000")
bind = f"0.0.0.0:{port}"

# Concurrency & Worker Threads
# Free-tier Render web services have 512MB RAM; 2 workers with 2 threads prevent OOM
workers = int(os.environ.get("WEB_CONCURRENCY", "2"))
threads = int(os.environ.get("PYTHON_MAX_THREADS", "2"))
worker_class = "gthread"

# Timeouts
timeout = int(os.environ.get("GUNICORN_TIMEOUT", "120"))
keepalive = int(os.environ.get("GUNICORN_KEEPALIVE", "5"))

# Log output directed to stdout / stderr for Render real-time logs
accesslog = "-"
errorlog = "-"
loglevel = os.environ.get("LOG_LEVEL", "info")

# Process name
proc_name = "smartcart_ecommerce"
