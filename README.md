# JET Cloud for Home Assistant (unofficial)

Brings the data from the **JET Cloud** app (by Shenzhen Energy Control Cloud Technology) into Home Assistant: total output, the power, voltage and current of every PV input (panel), grid readings and energy totals.

> This project is not affiliated with, endorsed by or supported by the makers of JET Cloud. It uses the same cloud API as the app, which can change without notice.

## What you get

For each **plant** (installation):

| Sensor | Unit |
|---|---|
| Power | W |
| Energy today | kWh |
| Total energy | kWh |

For each **inverter**:

| Sensor | Unit | Notes |
|---|---|---|
| Output power | W | AC power to the grid/home |
| PV1 power, PV2 power, … | W | one per PV input the inverter reports |
| PV1 voltage, PV1 current, … | V, A | |
| Grid voltage, grid current, grid frequency | V, A, Hz | |
| Temperature | °C | |
| Energy today, total energy | kWh | work with the Energy dashboard |
| Battery | % | only when the device reports a battery |
| Work mode | | diagnostic |
| Wi-Fi signal | dBm | diagnostic, disabled by default |

The cloud refreshes its data every 1 to 5 minutes; the integration polls every 2 minutes.

## Installation

### HACS

1. HACS → ⋮ → **Custom repositories** → add `https://github.com/jnnck/ha-jet-cloud` as an *Integration*.
2. Install **JET Cloud (unofficial)** and restart Home Assistant.

### Manual

Copy `custom_components/jet_cloud` into the `custom_components` folder of your Home Assistant configuration and restart.

## Setup

**Settings → Devices & services → Add integration → JET Cloud (unofficial)**, then log in with your JET Cloud email and password.

Your password is never stored: the integration keeps only the MD5 hash, which is what the app sends too. Note that the JET Cloud server accepts that hash as a login, so treat your Home Assistant backups as sensitive.

**Other apps on the same platform:** the API looks like a white-label platform. If your app talks to the same kind of API under another name, the *Server* and *Project type* fields let you point the integration at it. Please open an issue with your app name if that works for you.

## Troubleshooting

- Download the diagnostics (device page → ⋮ → *Download diagnostics*). Email, serial numbers, IDs and names are removed.
- Enable debug logging:

  ```yaml
  logger:
    logs:
      custom_components.jet_cloud: debug
  ```

## How it works

See [API.md](API.md) for the endpoints this integration uses.

## Development

```bash
uv venv --python 3.13
uv pip install pytest-homeassistant-custom-component aioresponses
.venv/bin/python -m pytest
```

Test fixtures in `tests/fixtures` are shaped like real responses but contain only made-up values. Never commit real responses, tokens, serial numbers or addresses.

## License

MIT
