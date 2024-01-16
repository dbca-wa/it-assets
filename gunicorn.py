# Gunicorn configuration settings.
import multiprocessing

bind = ":8080"
# Don't start too many workers:
workers = min(multiprocessing.cpu_count(), 4)
# Give workers an expiry:
max_requests = 2048
max_requests_jitter = 256
preload_app = True
# Set longer timeout for workers
timeout = 180
# Disable access logging.
accesslog = None
