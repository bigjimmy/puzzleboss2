#!/usr/bin/env python3
"""
PuzzleBoss Email to Discord/Slack Forwarder

This script receives email via stdin (piped from /etc/aliases) and forwards
it to Discord and/or Slack channels via webhooks.

Usage in /etc/aliases:
    puzzleboss: "|/path/to/python /path/to/pbmail_inbox.py"

Configuration:
    Set DISCORD_EMAIL_WEBHOOK in the puzzleboss config table for Discord.
    Set SLACK_EMAIL_WEBHOOK in the puzzleboss config table for Slack.
    Either or both can be configured.
"""

import sys
import os
import email
from email import policy
from email.parser import BytesParser
import requests
import yaml
from datetime import datetime

# Configuration file path (only needed for API_URI)
CONFIG_FILE = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "puzzleboss.yaml"
)

# Simple logging since we may not have full pblib available in mail context
def log(level, message):
    """Simple logging to stderr for mail script."""
    timestamp = datetime.now().isoformat()
    print(
        f"[{timestamp}] [{level}] pbmail_inbox: {message}", file=sys.stderr, flush=True
    )


def load_config():
    """Load configuration from YAML file (for API_URI) and then fetch config via API."""
    try:
        with open(CONFIG_FILE, "r") as f:
            yaml_config = yaml.safe_load(f)
    except Exception as e:
        log("ERROR", f"Failed to load YAML config: {e}")
        return None

    api_uri = yaml_config.get("API_URI", "http://localhost:5000")

    try:
        response = requests.get(f"{api_uri}/config", timeout=10)
        response.raise_for_status()
        data = response.json()

        if data.get("status") != "ok":
            log("ERROR", f"Config API returned error: {data}")
            return None

        return data.get("config", {})
    except Exception as e:
        log("ERROR", f"Failed to fetch config from API: {e}")
        return None


def parse_email(raw_email):
    """Parse raw email bytes into structured data."""
    try:
        msg = BytesParser(policy=policy.default).parsebytes(raw_email)

        # Extract headers
        from_addr = msg.get("From", "Unknown")
        to_addr = msg.get("To", "Unknown")
        subject = msg.get("Subject", "(no subject)")
        date = msg.get("Date", "Unknown date")

        # Extract body - prefer plain text
        body = None
        attachments = []

        if msg.is_multipart():
            for part in msg.walk():
                content_type = part.get_content_type()
                content_disposition = str(part.get("Content-Disposition", ""))

                # Skip attachments for body extraction
                if "attachment" in content_disposition:
                    filename = part.get_filename() or "unnamed"
                    attachments.append(filename)
                    continue

                # Get plain text body
                if content_type == "text/plain" and body is None:
                    try:
                        body = part.get_content()
                    except Exception:
                        body = part.get_payload(decode=True).decode(
                            "utf-8", errors="replace"
                        )

                # Fall back to HTML if no plain text
                elif content_type == "text/html" and body is None:
                    try:
                        html_body = part.get_content()
                        # Simple HTML stripping - just get text
                        import re

                        body = re.sub(r"<[^>]+>", "", html_body)
                        body = body.strip()
                    except Exception:
                        pass
        else:
            # Single part message
            try:
                body = msg.get_content()
            except Exception:
                body = msg.get_payload(decode=True).decode("utf-8", errors="replace")

        if body is None:
            body = "(no body)"

        return {
            "from": from_addr,
            "to": to_addr,
            "subject": subject,
            "date": date,
            "body": body,
            "attachments": attachments,
        }
    except Exception as e:
        log("ERROR", f"Failed to parse email: {e}")
        return None


def truncate_text(text, max_length):
    """Truncate text to max_length, adding ellipsis if truncated."""
    if len(text) <= max_length:
        return text
    return text[: max_length - 3] + "..."


def send_to_discord(webhook_url, email_data):
    """Send parsed email to Discord webhook."""

    # Build Discord embed
    embed = {
        "title": f"📧 {truncate_text(email_data['subject'], 200)}",
        "color": 0x00D9FF,  # Cyan color
        "fields": [
            {
                "name": "From",
                "value": truncate_text(email_data["from"], 100),
                "inline": True,
            },
            {
                "name": "To",
                "value": truncate_text(email_data["to"], 100),
                "inline": True,
            },
            {"name": "Date", "value": email_data["date"], "inline": True},
        ],
        "footer": {"text": "PuzzleBoss Email Forwarder"},
        "timestamp": datetime.utcnow().isoformat(),
    }

    # Add body as description (Discord has 4096 char limit for description)
    body_text = email_data["body"].strip()
    if body_text:
        embed["description"] = truncate_text(body_text, 4000)

    # Add attachments field if any
    if email_data["attachments"]:
        attachment_list = ", ".join(email_data["attachments"][:10])  # Limit to first 10
        if len(email_data["attachments"]) > 10:
            attachment_list += f" (+{len(email_data['attachments']) - 10} more)"
        embed["fields"].append(
            {"name": "📎 Attachments", "value": attachment_list, "inline": False}
        )

    payload = {"embeds": [embed]}

    try:
        response = requests.post(webhook_url, json=payload, timeout=10)

        if response.status_code == 204:
            log("INFO", f"Email forwarded successfully: {email_data['subject']}")
            return True
        else:
            log(
                "ERROR",
                f"Discord webhook returned {response.status_code}: {response.text}",
            )
            return False

    except requests.exceptions.Timeout:
        log("ERROR", "Discord webhook request timed out")
        return False
    except Exception as e:
        log("ERROR", f"Failed to send to Discord: {e}")
        return False


def send_to_slack(webhook_url, email_data):
    """Send parsed email to Slack webhook."""

    # Build attachment text
    body_text = truncate_text(email_data["body"].strip(), 3000)

    attachment_text = ""
    if email_data["attachments"]:
        attachment_list = ", ".join(email_data["attachments"][:10])
        if len(email_data["attachments"]) > 10:
            attachment_list += f" (+{len(email_data['attachments']) - 10} more)"
        attachment_text = f"\n📎 *Attachments:* {attachment_list}"

    # Build Slack message with blocks for nice formatting
    payload = {
        "blocks": [
            {
                "type": "header",
                "text": {
                    "type": "plain_text",
                    "text": f"📧 {truncate_text(email_data['subject'], 150)}",
                    "emoji": True,
                },
            },
            {
                "type": "section",
                "fields": [
                    {
                        "type": "mrkdwn",
                        "text": f"*From:*\n{truncate_text(email_data['from'], 100)}",
                    },
                    {
                        "type": "mrkdwn",
                        "text": f"*To:*\n{truncate_text(email_data['to'], 100)}",
                    },
                ],
            },
            {
                "type": "section",
                "fields": [
                    {"type": "mrkdwn", "text": f"*Date:*\n{email_data['date']}"}
                ],
            },
            {"type": "divider"},
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": body_text if body_text else "(no body)",
                },
            },
        ]
    }

    # Add attachments section if any
    if attachment_text:
        payload["blocks"].append(
            {"type": "section", "text": {"type": "mrkdwn", "text": attachment_text}}
        )

    # Add footer
    payload["blocks"].append(
        {
            "type": "context",
            "elements": [
                {
                    "type": "mrkdwn",
                    "text": f"_PuzzleBoss Email Forwarder • {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S UTC')}_",
                }
            ],
        }
    )

    try:
        response = requests.post(webhook_url, json=payload, timeout=10)

        if response.status_code == 200:
            log(
                "INFO",
                f"Email forwarded to Slack successfully: {email_data['subject']}",
            )
            return True
        else:
            log(
                "ERROR",
                f"Slack webhook returned {response.status_code}: {response.text}",
            )
            return False

    except requests.exceptions.Timeout:
        log("ERROR", "Slack webhook request timed out")
        return False
    except Exception as e:
        log("ERROR", f"Failed to send to Slack: {e}")
        return False


def main():
    """Main entry point."""
    log("INFO", "Receiving email...")

    # Read raw email from stdin
    try:
        raw_email = sys.stdin.buffer.read()
    except Exception as e:
        log("ERROR", f"Failed to read email from stdin: {e}")
        sys.exit(1)

    if not raw_email:
        log("ERROR", "No email data received")
        sys.exit(1)

    log("INFO", f"Received {len(raw_email)} bytes")

    # Load configuration
    config = load_config()
    if config is None:
        log("ERROR", "Failed to load configuration")
        sys.exit(1)

    # Get webhook URLs
    discord_webhook = config.get("DISCORD_EMAIL_WEBHOOK", "")
    slack_webhook = config.get("SLACK_EMAIL_WEBHOOK", "")

    if not discord_webhook and not slack_webhook:
        log("ERROR", "Neither DISCORD_EMAIL_WEBHOOK nor SLACK_EMAIL_WEBHOOK configured")
        sys.exit(1)

    # Parse email
    email_data = parse_email(raw_email)
    if email_data is None:
        log("ERROR", "Failed to parse email")
        sys.exit(1)

    log(
        "INFO",
        f"Parsed email: From={email_data['from']}, Subject={email_data['subject']}",
    )

    # Track success for each destination
    any_success = False

    # Send to Discord if configured
    if discord_webhook:
        if send_to_discord(discord_webhook, email_data):
            any_success = True

    # Send to Slack if configured
    if slack_webhook:
        if send_to_slack(slack_webhook, email_data):
            any_success = True

    if any_success:
        log("INFO", "Email forwarded successfully to at least one destination")
        sys.exit(0)
    else:
        log("ERROR", "Failed to forward email to any destination")
        sys.exit(1)


if __name__ == "__main__":
    main()
