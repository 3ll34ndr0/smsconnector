#!/usr/bin/env python3

import sys
import email
import re
import os
import json
import base64
import asyncio
import aiohttp
import syslog
import urllib.request
import aiosmtpd.controller
from dotenv import load_dotenv

syslog.openlog(ident="SMS_INBOUND", facility=syslog.LOG_LOCAL0)

# Load variables from .env file
load_dotenv()

# Retrieve the string and parse it into a dictionary
dids_raw = os.getenv("DIDS")
DIDS = json.loads(dids_raw) if dids_raw else {}
WEBHOOK_URL = os.getenv("WEBHOOK_URL")
MAIL_DOMAIN = os.getenv("MAIL_DOMAIN")
def get_public_ip() -> str:
    """Fetch public IP at startup; fall back to all-interfaces if unreachable."""
    try:
        with urllib.request.urlopen('https://api.ipify.org', timeout=10) as r:
            ip = r.read().decode()
        syslog.syslog(syslog.LOG_INFO, f"Public IP: {ip}")
        return ip
    except Exception as exc:
        syslog.syslog(syslog.LOG_WARNING, f"Could not fetch public IP ({exc}), binding to 0.0.0.0")
        return '0.0.0.0'


class WebhookSender:
    def __init__(self):
        self.dids = DIDS

    async def hit_webhook(self, to: str, text: str, from_tel: str) -> bool:
        """
        POST inbound SMS data to the FreePBX SMS connector.
        Returns True on success, False otherwise.
        """
        payload = {'to': to, 'text': text, 'from': from_tel}
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(WEBHOOK_URL, data=payload, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                    body = await resp.json(content_type=None)
                    syslog.syslog(syslog.LOG_INFO, f"Webhook response {resp.status}: {body}")

                    # The FreePBX SMS connector returns HTTP 202 on success.
                    if resp.status == 202:
                        return True

                    # Fallback: some versions return {"202": true} in the body.
                    if isinstance(body, dict) and body.get("202"):
                        return True

                    syslog.syslog(syslog.LOG_WARNING, f"Webhook unexpected response {resp.status}: {body}")
                    return False

        except aiohttp.ClientError as exc:
            syslog.syslog(syslog.LOG_ERR, f"Webhook connection error: {exc}")
            return False
        except Exception as exc:
            syslog.syslog(syslog.LOG_ERR, f"Webhook unexpected error: {exc}")
            return False

    async def goip_data_send(self, data: dict):
        if "error" in data:
            msg = "Error processing incoming message"
            syslog.syslog(syslog.LOG_ERR, msg)
            return

        did = self.dids.get(data.get("channel"))
        if did is None:
            syslog.syslog(syslog.LOG_ERR, f"Unknown GoIP channel: {data.get('channel')}")
            return

        success = await self.hit_webhook(did, data.get("text", ""), data.get("sender", ""))
        if not success:
            syslog.syslog(syslog.LOG_ERR,
                          f"Failed to deliver SMS from {data.get('sender')} on channel {data.get('channel')}")


class GOIPSMTPHandler:
    # GoIP email body format: SN:<serial> Channel:<n> <YYYY-MM-DD HH:MM:SS>,<sender>,<text>
    _regexp = re.compile(
        r"SN:(?P<sn>.+)\s+Channel:(?P<channel>[0-9]+)\s+(?P<time>[0-9\-:\s]+),(?P<sender>.+?),(?P<text>.*)"
    )

    def __init__(self):
        self.sender = WebhookSender()

    async def handle_RCPT(self, server, session, envelope, address, rcpt_options):
        if not address.endswith(f"{MAIL_DOMAIN}"):
            syslog.syslog(syslog.LOG_INFO, f"Rejected relay to: {address}")
            return '550 not relaying to that domain'
        envelope.rcpt_tos.append(address)
        return '250 OK'

    async def handle_DATA(self, server, session, envelope):
        syslog.syslog(syslog.LOG_INFO, f"Received GoIP SMS for {envelope.rcpt_tos}")
        try:
            msg = email.message_from_bytes(envelope.content)
            payload = msg.get_payload()

            # Payload may already be a string or still base64-encoded bytes.
            if isinstance(payload, str):
                try:
                    text = base64.b64decode(payload).decode('utf-8')
                except Exception:
                    text = payload
            else:
                text = payload.decode('utf-8')

            syslog.syslog(syslog.LOG_INFO, f"Decoded SMS body: {text}")

            match = self._regexp.match(text.strip())
            data = match.groupdict() if match else {"error": True}
            asyncio.create_task(self.sender.goip_data_send(data))

        except UnicodeDecodeError as exc:
            syslog.syslog(syslog.LOG_ERR, f"Unicode decode error: {exc}")
        except AttributeError as exc:
            syslog.syslog(syslog.LOG_ERR, f"Parse error (regex no match?): {exc}")
        except Exception as exc:
            syslog.syslog(syslog.LOG_ERR, f"Unexpected error in handle_DATA: {exc}")

        return '250 OK'


async def main():
    pid = os.getpid()
    with open('/tmp/goip_sms_in.pid', 'w', encoding='utf-8') as f:
        f.write(str(pid))

    my_ip = get_public_ip()

    handler = GOIPSMTPHandler()
    # GoIP only supports port 25 for SMTP delivery.
    controller = aiosmtpd.controller.Controller(handler, hostname=my_ip, port=25)
    controller.start()

    syslog.syslog(syslog.LOG_INFO, f"SMS inbound service started — PID {pid}, listening on {my_ip}:25")
    print(f"Starting service with PID: {pid}, listening on {my_ip}:25")

    try:
        await asyncio.Event().wait()  # run forever
    finally:
        controller.stop()
        syslog.syslog(syslog.LOG_INFO, "SMS inbound service stopped")


if __name__ == '__main__':
    asyncio.run(main())
