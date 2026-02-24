#!/usr/bin/env python3
"""ECS Events -> Loki bridge.

Long-polls an SQS queue for ECS state-change events (delivered by EventBridge)
and pushes them to a local Loki instance as structured log entries.

Runs as a systemd service on the observability instance.
Usage: ecs-events-to-loki.py --queue-url <SQS_URL> [--loki-url http://localhost:3100]
"""
import argparse, json, logging, signal, time, urllib.request, urllib.error
import boto3

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s",
                    datefmt="%Y-%m-%dT%H:%M:%S")
log = logging.getLogger("ecs-events-to-loki")
RUNNING = True

def _sigterm(s, f):
    global RUNNING
    log.info("Received signal, shutting down")
    RUNNING = False
signal.signal(signal.SIGTERM, _sigterm)
signal.signal(signal.SIGINT, _sigterm)


def push_to_loki(loki_url, labels, message, timestamp_ns):
    """Push a single log entry to Loki's push API."""
    payload = {"streams": [{"stream": labels, "values": [[str(timestamp_ns), message]]}]}
    body = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(f"{loki_url}/loki/api/v1/push", data=body,
                                 headers={"Content-Type": "application/json"}, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=5) as resp:
            return resp.status in (200, 204)
    except urllib.error.URLError as e:
        log.error("Loki push failed: %s", e)
        return False


def _short_arn(arn):
    parts = arn.rsplit("/", 1)
    return parts[-1][:8] if len(parts) > 1 else arn


def format_task_state_change(detail):
    cluster = detail.get("clusterArn", "").rsplit("/", 1)[-1]
    task_id = _short_arn(detail.get("taskArn", ""))
    task_def = detail.get("taskDefinitionArn", "").rsplit("/", 1)[-1]
    last_status = detail.get("lastStatus", "?")
    desired = detail.get("desiredStatus", "?")
    stopped_reason = detail.get("stoppedReason", "")
    group = detail.get("group", "")
    service = group.split(":")[-1] if ":" in group else group
    labels = {"job": "ecs_events", "event_type": "task_state_change",
              "cluster": cluster, "service": service or "unknown"}
    parts = [f"task={task_id}", f"taskDef={task_def}", f"status={last_status}", f"desired={desired}"]
    if last_status == "STOPPED":
        for c in detail.get("containers", []):
            name, ec, reason = c.get("name", "?"), c.get("exitCode"), c.get("reason", "")
            if ec is not None or reason:
                parts.append(f"container:{name}(exit={ec},reason={reason})")
        if stopped_reason:
            parts.append(f"stoppedReason={stopped_reason}")
    return labels, " ".join(parts)


def format_service_action(detail):
    cluster = detail.get("clusterArn", "").rsplit("/", 1)[-1]
    labels = {"job": "ecs_events", "event_type": "service_action", "cluster": cluster}
    msg = f"action={detail.get('eventName', '?')}"
    if detail.get("eventMessage"):
        msg += f" {detail['eventMessage']}"
    return labels, msg


def format_deployment_state_change(detail):
    cluster = detail.get("clusterArn", "").rsplit("/", 1)[-1]
    labels = {"job": "ecs_events", "event_type": "deployment_state_change", "cluster": cluster}
    msg = f"deployment={detail.get('deploymentId', '?')} status={detail.get('status', '?')}"
    if detail.get("reason"):
        msg += f" reason={detail['reason']}"
    return labels, msg


FORMATTERS = {
    "ECS Task State Change": format_task_state_change,
    "ECS Service Action": format_service_action,
    "ECS Deployment State Change": format_deployment_state_change,
}

def process_message(body, loki_url):
    try:
        event = json.loads(body)
    except json.JSONDecodeError:
        return True
    detail_type = event.get("detail-type", "")
    detail = event.get("detail", {})
    if detail_type not in FORMATTERS:
        return True
    try:
        from datetime import datetime
        dt = datetime.fromisoformat(event.get("time", "").replace("Z", "+00:00"))
        ts_ns = int(dt.timestamp() * 1e9)
    except (ValueError, AttributeError):
        ts_ns = int(time.time() * 1e9)
    labels, message = FORMATTERS[detail_type](detail)
    for r in event.get("resources", []):
        if ":service/" in r:
            labels["service"] = r.rsplit("/", 1)[-1]
            break
    log.info("[%s] %s: %s", labels.get("service", "?"), detail_type, message[:120])
    return push_to_loki(loki_url, labels, message, ts_ns)


def main():
    p = argparse.ArgumentParser(description="ECS events -> Loki bridge")
    p.add_argument("--queue-url", required=True)
    p.add_argument("--loki-url", default="http://localhost:3100")
    p.add_argument("--region", default="us-east-1")
    args = p.parse_args()
    sqs = boto3.client("sqs", region_name=args.region)
    log.info("Starting ECS events bridge (queue=%s)", args.queue_url)
    errs = 0
    while RUNNING:
        try:
            resp = sqs.receive_message(QueueUrl=args.queue_url,
                                       MaxNumberOfMessages=10, WaitTimeSeconds=20)
            errs = 0
        except Exception as e:
            errs += 1
            time.sleep(min(errs * 5, 60))
            log.error("SQS error (backoff %ds): %s", min(errs * 5, 60), e)
            continue
        for msg in resp.get("Messages", []):
            if process_message(msg["Body"], args.loki_url):
                try:
                    sqs.delete_message(QueueUrl=args.queue_url,
                                       ReceiptHandle=msg["ReceiptHandle"])
                except Exception as e:
                    log.error("Delete failed: %s", e)

if __name__ == "__main__":
    main()
