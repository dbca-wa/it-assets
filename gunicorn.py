# Gunicorn configuration settings.

bind = ":8080"
workers = 4
worker_connections = 1000  # Max connections per worker
max_requests = 2048  # Max no of requests a worker will process before restarting
max_requests_jitter = 256  # Max jitter added to the max_requests setting
preload_app = True
keepalive = 5  # Max seconds to wait for requests on a Keep-Alive connection
timeout = 60  # Worker timeout
# Disable access logging.
accesslog = None
control_socket_disable = True
worker_tmp_dir = "/dev/shm"
