# GoIP Inbound SMS Gateway

Receives inbound SMS messages from a GoIP GSM gateway via SMTP (port 25) and forwards them to the FreePBX SMS connector webhook.

## Requirements

- Python 3.10+
- Root access (port 25 requires it)
- Network access to `pbx.yourdomain.com`

## Files

| File | Purpose |
|---|---|
| `goip_sms_in.py` | Main service script |
| `requirements.txt` | Python dependencies |
| `goip-sms-in.service` | systemd unit file |
| `install.sh` | Installation script |

## Installation


**1. Run the installer (as root):**
```bash
sudo bash install.sh
```

The installer will:
- Copy files to `/opt/goip-sms/`
- Install Python dependencies
- Register and start the systemd service

## Manual installation (step by step)

```bash
# Copy files
sudo mkdir -p /opt/goip-sms
sudo cp goip_sms_in.py requirements.txt /opt/goip-sms/

# Install dependencies
sudo pip3 install -r /opt/goip-sms/requirements.txt

# Install systemd service
sudo cp goip-sms-in.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now goip-sms-in
```

## Managing the service

```bash
sudo systemctl status goip-sms-in     # check status
sudo systemctl restart goip-sms-in    # restart
sudo systemctl stop goip-sms-in       # stop
sudo journalctl -u goip-sms-in -f     # follow logs
```

Syslog messages are written under the identity `SMS_INBOUND` to `LOG_LOCAL0`:
```bash
grep SMS_INBOUND /var/log/syslog
```

## GoIP device configuration

In the GoIP web interface, configure the SMS email delivery:
- **SMTP server:** IP of this machine
- **SMTP port:** 25
- **Recipient:** `DID@pbx.yourdomain.com`

## Channel to DID mapping

GoIP reports the SIM slot number, not the phone number. The mapping is defined in `.env` XXXXXXX
| Channel ts the 
|---|---|
| 1 | XXXXXXX27929 |
| 2 | XXXXXXX36056 |
| 3 | XXXXXXX54887 |
| 4 | XXXXXXX36058 |
| 5 | XXXXXXX94729 |
| 6 | XXXXXXX55708 |
| 7 | XXXXXXX54476 |
| 8 | XXXXXXX55419 |

To change the mapping, edit the `DIDS` dict at the `.env` and restart the service.
