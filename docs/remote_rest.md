# Cloud REST API

## Firmware

`GET https://gw-lmz.lamarzocco.io/v1/home/machines/<SN>/firmwarev2/`

```json
{
    "data": {
        "gateway_firmware": {
            "latestVersion": "v2.2-rc0",
            "md5": "",
            "update": null,
            "url_firmware": "http://firmware.lamarzocco.io/new_firmware/gateway/v2/home-gateway_v2.2-rc0.bin",
            "url_schema": "http://firmware.lamarzocco.io/new_json/gw/v2.2rc0.json",
            "version": "v2.2-rc0"
        },
        "machine_firmware": {
            "latestVersion": "1.11",
            "md5": "7928e9d27f612dd3136e6ebd3a45eb944b263bf053f6ea6dfa1140c4c45b64d3",
            "update": null,
            "url_firmware": "http://firmware.lamarzocco.io/new_firmware/machine/micra/atmega32/NewuLApp-111.bin",
            "url_schema": "http://firmware.lamarzocco.io/new_json/fw/MR/v1.11.json",
            "version": "1.11"
        }
    },
    "status": true
}
```

## Status
`GET https://gw-lmz.lamarzocco.io/v1/home/machines/<SN>/status`

```json
{
    "data": {
        "LEVEL_TANK": true,
        "MACHINE_REMOTSETS": {
            "BACKFLUSH_ENABLE": false,
            "BOILER_ENABLE": true,
            "PLUMBIN_ENABLE": false
        },
        "MACHINE_STATUS": "ON",
        "TEMP_COFFEE": 97,
        "TEMP_STEAM": 131,
        "received": "2023-01-23T11:04:46.431Z"
    },
    "status": true
}
```

## Configuration
`GET https://gw-lmz.lamarzocco.io/v1/home/machines/<SN>/configuration`

```json
  {
    "version": "v1",
    "preinfusionModesAvailable": [
        "ByDoseType"
    ],
    "machineCapabilities": [
        {
            "family": "GS3AV",
            "groupsNumber": 1,
            "coffeeBoilersNumber": 1,
            "hasCupWarmer": false,
            "steamBoilersNumber": 1,
            "teaDosesNumber": 1,
            "machineModes": [
                "BrewingMode",
                "StandBy"
            ],
            "schedulingType": "weeklyScheduling"
        }
    ],
    "machine_sn": "xxx",
    "machine_hw": "2",
    "isPlumbedIn": true,
    "isBackFlushEnabled": false,
    "standByTime": 0,
    "tankStatus": true,
    "groupCapabilities": [
        {
            "capabilities": {
                "groupType": "AV_Group",
                "groupNumber": "Group1",
                "boilerId": "CoffeeBoiler1",
                "hasScale": false,
                "hasFlowmeter": true,
                "numberOfDoses": 4
            },
            "doses": [
                {
                    "groupNumber": "Group1",
                    "doseIndex": "DoseA",
                    "doseType": "PulsesType",
                    "stopTarget": 135
                },
                {
                    "groupNumber": "Group1",
                    "doseIndex": "DoseB",
                    "doseType": "PulsesType",
                    "stopTarget": 97
                },
                {
                    "groupNumber": "Group1",
                    "doseIndex": "DoseC",
                    "doseType": "PulsesType",
                    "stopTarget": 108
                },
                {
                    "groupNumber": "Group1",
                    "doseIndex": "DoseD",
                    "doseType": "PulsesType",
                    "stopTarget": 121
                }
            ],
            "doseMode": {
                "groupNumber": "Group1",
                "brewingType": "PulsesType"
            }
        }
    ],
    "machineMode": "BrewingMode",
    "teaDoses": {
        "DoseA": {
            "doseIndex": "DoseA",
            "stopTarget": 8
        }
    },
    "boilers": [
        {
            "id": "SteamBoiler",
            "isEnabled": true,
            "target": 123.90000152587891,
            "current": 123.80000305175781
        },
        {
            "id": "CoffeeBoiler1",
            "isEnabled": true,
            "target": 95,
            "current": 96.5
        }
    ],
    "boilerTargetTemperature": {
        "SteamBoiler": 123.90000152587891,
        "CoffeeBoiler1": 95
    },
    "preinfusionMode": {
        "Group1": {
            "groupNumber": "Group1",
            "preinfusionStyle": "PreinfusionByDoseType"
        }
    },
    "preinfusionSettings": {
        "mode": "TypeB",
        "Group1": [
            {
                "groupNumber": "Group1",
                "doseType": "DoseA",
                "preWetTime": 0.5,
                "preWetHoldTime": 1
            },
            {
                "groupNumber": "Group1",
                "doseType": "DoseB",
                "preWetTime": 0.5,
                "preWetHoldTime": 1
            },
            {
                "groupNumber": "Group1",
                "doseType": "DoseC",
                "preWetTime": 3.2999999523162842,
                "preWetHoldTime": 3.2999999523162842
            },
            {
                "groupNumber": "Group1",
                "doseType": "DoseD",
                "preWetTime": 2,
                "preWetHoldTime": 2
            }
        ]
    },
    "weeklySchedulingConfig": {
        "enabled": true,
        "monday": {
            "enabled": true,
            "h_on": 6,
            "h_off": 16,
            "m_on": 0,
            "m_off": 0
        },
        "tuesday": {
            "enabled": true,
            "h_on": 6,
            "h_off": 16,
            "m_on": 0,
            "m_off": 0
        },
        "wednesday": {
            "enabled": true,
            "h_on": 6,
            "h_off": 16,
            "m_on": 0,
            "m_off": 0
        },
        "thursday": {
            "enabled": true,
            "h_on": 6,
            "h_off": 16,
            "m_on": 0,
            "m_off": 0
        },
        "friday": {
            "enabled": true,
            "h_on": 6,
            "h_off": 16,
            "m_on": 0,
            "m_off": 0
        },
        "saturday": {
            "enabled": true,
            "h_on": 6,
            "h_off": 16,
            "m_on": 0,
            "m_off": 0
        },
        "sunday": {
            "enabled": true,
            "h_on": 6,
            "h_off": 16,
            "m_on": 0,
            "m_off": 0
        }
    },
    "clock": "1901-07-08T10:29:00",
    "firmwareVersions": [
        {
            "name": "machine_firmware",
            "fw_version": "1.40"
        },
        {
            "name": "gateway_firmware",
            "fw_version": "v3.1-rc4"
        }
    ]
}
```

## Counters
`GET https://gw-lmz.lamarzocco.io/v1/home/machines/<SN>/statistics/counters`

```json
{
    "data": [
        {
            "coffeeType": 0,
            "count": 167
        },
        {
            "coffeeType": 1,
            "count": 0
        },
        {
            "coffeeType": 2,
            "count": 0
        },
        {
            "coffeeType": 3,
            "count": 0
        },
        {
            "coffeeType": 4,
            "count": 0
        },
        {
            "coffeeType": -1,
            "count": 228
        }
    ],
    "status": true
}
```

## Preinfusion Settings
`POST https://gw-lmz.lamarzocco.io/v1/home/machines/<SN>/setting-preinfusion`

```json
{
    "button": "Continuous",
    "group": "Group1",
    "holdTimeMs": 2000,
    "wetTimeMs": 0
}
```

# Enable/Disable Preinfusion
`POST https://gw-lmz.lamarzocco.io/v1/home/machines/<SN>/enable-preinfusion`

```json
{
    "mode": "Disabled" // "Enabled"
}
```

# Power
`POST https://gw-lmz.lamarzocco.io/v1/home/machines/<SN>/status`

```json
{
    "status": "ON" // "STANDBY"
}
```

# Steam
`POST https://gw-lmz.lamarzocco.io/v1/home/machines/<SN>/enable-boiler`

```json
{
    "identitfier": "SteamBoiler",
    "state": True // False
}
```

# Temperature
`GET https://gw-lmz.lamarzocco.io/v1/home/machines/<SN>/target-boiler`

```json
{
    "identifier": "<Boilername",
    "value": "<temp>"
}
```

# Backflush
`GET https://gw-lmz.lamarzocco.io/v1/home/machines/<SN>/enable-backflush`

```json
{
    "enable": True
}
```

# Plumb In
`GET https://gw-lmz.lamarzocco.io/v1/home/machines/<SN>/enable-plumbin`

```json
{
    "enable": True // False
}
```

# Set Schedule
`GET https://gw-lmz.lamarzocco.io/v1/home/machines/<SN>/scheduling`

```json
{
    "enable": True, // False
    "days": [
        {
            "day": "MONDAY",
            "enable": false,
            "off": "00:00",
            "on": "00:00"
        },
        {
            "day": "TUESDAY",
            "enable": false,
            "off": "00:00",
            "on": "00:00"
        },
        {
            "day": "WEDNESDAY",
            "enable": false,
            "off": "00:00",
            "on": "00:00"
        },
        {
            "day": "THURSDAY",
            "enable": false,
            "off": "00:00",
            "on": "00:00"
        },
        {
            "day": "FRIDAY",
            "enable": false,
            "off": "00:00",
            "on": "00:00"
        },
        {
            "day": "SATURDAY",
            "enable": false,
            "off": "00:00",
            "on": "00:00"
        },
        {
            "day": "SUNDAY",
            "enable": false,
            "off": "00:00",
            "on": "00:00"
        }
    ]
}
```

# Pico
```json
{
	"version": "v1",
	"family": "PICOG",
	"machineSn": "XXXXXXX",
	"machineHw": "1",
	"machineMode": "StandBy",
	"baristaLed": true,
	"bellOpened": false,
	"standByTime": 5,
	"selectedDose": "",
	"doses": [{
		"doseIndex": "DoseA",
		"target": 5.3
	}, {
		"doseIndex": "DoseB",
		"target": 10.3
	}],
	"firmwareVersions": [{
		"name": "machine_firmware",
		"fw_version": "1.17"
	}, {
		"name": "gateway_firmware",
		"fw_version": "v3.2-rc9"
	}]
}
```