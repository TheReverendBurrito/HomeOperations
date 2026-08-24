# RC-001 Home Operations Center

RC-001 is a self-hosted Flask dashboard for network, environmental, lighting,
security-camera, and alerting operations. It supports Peplink, Home Assistant,
WLED, Ookla Speedtest, SNMP, AirNow, Windy radar, Ring entities exposed through
Home Assistant, SQLite event history, and Pushover notifications.

This repository is the sanitized public-source edition of RC-001 v3.3.1. It
contains no production credentials, device inventory, personal addresses,
private network assignments, camera entity IDs, logs, databases, or backups.

## Requirements

- Python 3.11 or newer
- Linux is recommended for the systemd installer
- Optional: Ookla Speedtest CLI and Net-SNMP command-line tools

## Local setup

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
cp .env.example .env
```

Edit `.env` with your own URLs, credentials, entity IDs, network labels, and
location. The example uses addresses from the documentation-only `192.0.2.0/24`
range; they are not expected to be reachable.

Start the dashboard after required Peplink and Home Assistant settings are set:

```bash
python app.py
```

Open `http://localhost:5050`.

## Raspberry Pi installation

On Raspberry Pi OS, extract the release and run:

```bash
sudo apt update
sudo apt install -y python3-flask python3-dotenv python3-requests curl
sudo ./install.sh
```

The installer preserves an existing `/opt/rc001/.env` and `/opt/rc001/data`,
creates timestamped rollback backups, installs the systemd services, and runs
the offline self-test. On a new installation, the first run safely stops after
creating `/opt/rc001/.env`; edit that file, then run `sudo ./install.sh` again.

## Validation

```bash
python -m compileall -q .
node --check static/rc001.js
bash -n install.sh
python validate_release.py
python validate_rc2.py
```

Live integrations require deployment-side validation against equipment you own
or are authorized to administer.

## Secrets and private data

- Never commit `.env`, databases, logs, backups, exported device registries, or
  screenshots of live dashboards.
- Use read-only SNMP credentials and restrict them to the management network.
- Rotate any credential that has previously been committed or shared publicly.
- Review `SECURITY.md` before publishing or deploying changes.

## Licensing

No open-source license has been selected for this package. See
`LICENSE-NOTICE.md` before publishing the repository.
