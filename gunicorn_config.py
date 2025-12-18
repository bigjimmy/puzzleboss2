"""
Gunicorn configuration for Puzzleboss API with Prometheus multiprocess metrics.

Usage:
    gunicorn -c gunicorn_config.py wsgi:app

Or with custom settings:
    gunicorn -c gunicorn_config.py -w 16 -b 0.0.0.0:5000 wsgi:app
"""

import os
import shutil

# Prometheus multiprocess directory
prometheus_multiproc_dir = os.environ.get('prometheus_multiproc_dir')
if not prometheus_multiproc_dir:
    if os.path.exists('/dev/shm'):
        prometheus_multiproc_dir = '/dev/shm/puzzleboss_prometheus'
    else:
        prometheus_multiproc_dir = '/tmp/puzzleboss_prometheus'
    os.environ['prometheus_multiproc_dir'] = prometheus_multiproc_dir


def on_starting(server):
    """Called just before the master process is initialized.
    Clean up any stale prometheus metric files from previous runs.
    """
    if os.path.exists(prometheus_multiproc_dir):
        # Remove all files in the directory
        for filename in os.listdir(prometheus_multiproc_dir):
            filepath = os.path.join(prometheus_multiproc_dir, filename)
            try:
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
    from prometheus_client import multiprocess
    multiprocess.mark_process_dead(worker.pid)

