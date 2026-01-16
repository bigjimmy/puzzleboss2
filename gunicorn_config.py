"""
Gunicorn configuration for Puzzleboss API with Prometheus multiprocess metrics.

Usage:
    gunicorn -c gunicorn_config.py wsgi:app

Or with custom settings:
    gunicorn -c gunicorn_config.py -w 16 -b 0.0.0.0:5000 wsgi:app
"""

import os

# Prometheus multiprocess directory - MUST be set BEFORE importing prometheus_client
prometheus_multiproc_dir = os.environ.get("prometheus_multiproc_dir")
if not prometheus_multiproc_dir:
    if os.path.exists("/dev/shm"):
        prometheus_multiproc_dir = "/dev/shm/puzzleboss_prometheus"
    else:
        prometheus_multiproc_dir = "/tmp/puzzleboss_prometheus"
    os.environ["prometheus_multiproc_dir"] = prometheus_multiproc_dir

# Import prometheus_client at module level to avoid signal handler reentrancy issues
# Must be imported AFTER prometheus_multiproc_dir is set
# If not available, child_exit will gracefully handle it
try:
    from prometheus_client import multiprocess
    PROMETHEUS_AVAILABLE = True
except ImportError:
    PROMETHEUS_AVAILABLE = False
    multiprocess = None

# Server socket
bind = "0.0.0.0:5000"
workers = 4


def on_starting(server):
    """Called just before the master process is initialized.
    Clean up any stale prometheus metric files from previous runs.
    """
    if os.path.exists(prometheus_multiproc_dir):
        # Remove all files in the directory, including corrupted/empty ones
        for filename in os.listdir(prometheus_multiproc_dir):
            filepath = os.path.join(prometheus_multiproc_dir, filename)
            try:
                # Remove file even if it's empty or corrupted
                if os.path.isfile(filepath):
                    os.unlink(filepath)
            except Exception as e:
                print(f"Warning: Could not remove {filepath}: {e}")
        print(f"Cleaned prometheus multiproc dir: {prometheus_multiproc_dir}")
    else:
        os.makedirs(prometheus_multiproc_dir, exist_ok=True)
        print(f"Created prometheus multiproc dir: {prometheus_multiproc_dir}")


def child_exit(server, worker):
    """Called when a worker exits.
    Clean up the worker's prometheus metric files.
    """
    if PROMETHEUS_AVAILABLE and multiprocess:
        try:
            multiprocess.mark_process_dead(worker.pid)
        except Exception as e:
            # Don't let prometheus cleanup failures crash gunicorn
            print(f"Warning: Failed to mark prometheus process {worker.pid} as dead: {e}")
