# JET Cloud API notes

Reverse-engineered from the JET Cloud iOS app (version 1.260828.2, October 2026) by watching its traffic. Not an official API: anything here can change.

## Basics

- Base URL: `https://server-jy.ai-ec.cloud:8443`
- Every response looks like `{"result": 0, "msg": "...", "obj": ...}`. `result: 0` means success.
- `result: 10000` (`"Please login."`) means the token is missing or expired.
- `result: 1` on login carries a readable reason, e.g. `"password is incorrect."` or `"Email does not exist."`.

### Headers

| Header | Value | Notes |
|---|---|---|
| `InterfaceType` | `2` | |
| `projectType` | `10` | Probably identifies the white-label app. |
| `appVersion` | `1.260828.2` | |
| `Accept-Language` | `en-US` | Controls the language of messages **and of data labels** (`deviceInfoMap`, `displayMap`). |
| `token` | JWT from login | Required on everything except login. |

The `JSESSIONID` cookie the app sends is not needed.

## Login

`POST /user/login` (JSON)

```json
{
  "email": "user@example.com",
  "password": "<md5 hex of the password>",
  "phoneOs": "2",
  "phoneModel": "homeassistant",
  "appVersion": "1.260828.2"
}
```

- The password is an **unsalted MD5** hex digest.
- `appVersion` in the body is required (`"APP Version can not be null."`).
- The response has `obj.token`, a JWT valid for 24 hours.

## Plants

`POST /plant/getPlantPage` (JSON) `{"pageNow": 1, "pageSize": 20}`

`obj.dataList[]` contains, among others: `id`, `plantName`, `deviceSnList`, `pvPower` (W), `todayEnergy` and `totalEnergy` (kWh), `totalRevenue`, `incomeUnitText`, `timeZone`.

## Devices of a plant

`POST /device/getDevicePage` (JSON)

```json
{"pageNow": 1, "pageSize": 20, "map": {"searchField": "", "type": 1, "plantId": 12345, "statusType": -1}}
```

`obj.dataList[]` contains `deviceSn`, `deviceName`, `deviceType` (needed for the detail call), `deviceStatus` (1 = online), `todayEnergy` and `totalEnergy` (kWh, 3 decimals), `power`, `wifiSignal`, `updateTime`, `updateFreq`.

## Device detail (live readings)

`POST /device/getDeviceBySn` (form-encoded) `deviceType=57&sn=<serial>&time=YYYY-MM-DD`

- `obj.displayMap`: flat map of label → value string with unit, e.g. `"PV1 Power": "80.0W"`, `"Voltage": "234.1V"`, `"Real-time Power Generation": "1.234kWH"`.
- `obj.deviceInfoMap`: the same values grouped by section (`Grid Information`, `PV Information`, `Fault information`, `Basic Information`).
- `obj.chartMap`: 5-minute series for the given day (288 points), one per label.
- `obj.deviceDetailInfoVo`: battery data (`soc`, `batTotalCapacity`, `batRemainingCapacity`).
- `obj.devicePowerWorkModeText`: e.g. `"Charging"`.

Labels seen with `Accept-Language: en-US`:

| Label | Example |
|---|---|
| `Power` | `150.0W` (AC output) |
| `Voltage`, `Current`, `AC Frequency` | `234.1V`, `0.64A`, `50.01Hz` |
| `Temperature 1` | `21.2℃` |
| `Real-time Power Generation` | `1.234kWH` (today) |
| `PV1 Power`, `PV1 Voltage`, `PV1 Current` (and `PV2 …`) | `80.0W`, `31.9V`, `2.70A` |
| `Fault Indicator 1`, `Fault Indicator 2` | `Normal` |
| `Collector Version`, `Monitoring Software Version Number`, `Monitoring Hardware Version Number` | |

## Other endpoints the app calls

Not used by the integration: `/energy/getHomeControlSn/{plantId}` (home screen summary), `/device/getDeviceCount`, `/msg/getMsgCount`, `/home/getHomeNotice`, `/weather/getWeatherInfo`, `/device/getDeviceImageMap`, `/dict/getSystemParam`, `/upgrade/getDeviceUpgrades`.
