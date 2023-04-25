# Cloud REST API

## Firmware

`GET https://gw.lamarzocco.io/v1/home/machines/<SN>/firmwarev2/`

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
`GET https://gw.lamarzocco.io/v1/home/machines/<SN>/status`

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
`GET https://gw.lamarzocco.io/v1/home/machines/<SN>/configuration`

```json
  {
    "data": {
        "BOILERS": [
            {
                "id": "SteamBoiler",
                "isEnabled": true,
                "target": 131
            },
            {
                "id": "CoffeeBoiler1",
                "isEnabled": true,
                "target": 94
            }
        ],
        "BOILERTARGETTEMPERATURE": {
            "CoffeeBoiler1": 94,
            "SteamBoiler": 131
        },
        "CLOCK": "2023-01-23T11:04:05",
        "FIRMWAREVERSIONS": [
            {
                "fw_version": "1.11",
		"name": "machine_firmware"
            },
            {
                "fw_version": "v2.2-rc0",
                "name": "gateway_firmware"
            }
        ],
        "GROUPCAPABILITIES": [
            {
                "capabilities": {
                    "boilerId": "CoffeeBoiler1",
                    "groupNumber": "Group1",
                    "groupType": "EP_Group",
                    "hasFlowmeter": false,
                    "hasScale": false,
                    "numberOfDoses": 0
                },
                "doseMode": {
                    "brewingType": "Time",
                    "groupNumber": "Group1"
                },
                "doses": []
            }
        ],
        "ISBACKFLUSHENABLED": false,
        "ISPLUMBEDIN": false,
        "MACHINECAPABILITIES": [
            {
                "coffeeBoilersNumber": 1,
                "family": "MICRA",
                "groupsNumber": 1,
                "hasCupWarmer": false,
		"hasWhaterProbe": false,
                "machineModes": [
                    "BrewingMode",
                    "StandBy"
                ],
                "schedulingType": "weeklyScheduling",
                "steamBoilersNumber": 1,
                "teaDosesNumber": 1
            }
        ],
        "MACHINEMODE": "BrewingMode",
        "MACHINE_SN": "#REDACTED#",
        "PREINFUSIONMODE": {
            "Group1": {
                "groupNumber": "Group1",
                "preinfusionStyle": "PreinfusionByDoseType"
            }
        },
        "PREINFUSIONMODESAVAILABLE": [
            "ByDoseType"
        ],
        "PREINFUSIONSETTINGS": {
            "Group1": [
                {
                    "doseType": "Continuous",
                    "groupNumber": "Group1",
                    "preWetHoldTime": 5,
                    "preWetTime": 5
                }
            ],
            "mode": "Disabled"
	},
        "STANDBYTIME": 30,
        "TANKSTATUS": true,
        "TEADOSES": {
            "DoseA": {
                "doseIndex": "DoseA",
                "stopTarget": 0
            }
        },
        "VERSION": "v1",
        "WEEKLYSCHEDULINGCONFIG": {
		 "enabled": false,
                "h_off": 24,
                "h_on": 24,
                "m_off": 0,
                "m_on": 0
            },
            "thursday": {
                "enabled": false,
                "h_off": 24,
                "h_on": 24,
                "m_off": 0,
                "m_on": 0
            },
            "tuesday": {
                "enabled": false,
                "h_off": 24,
                "h_on": 24,
                "m_off": 0,
                "m_on": 0
            },
            "wednesday": {
                "enabled": false,
                "h_off": 24,
                "h_on": 24,
                "m_off": 0,
                "m_on": 0
            }
        },
        "received": "2023-01-23T11:04:46.431Z"
    },
    "status": true
}
```

## Counters
`GET https://gw.lamarzocco.io/v1/home/machines/<SN>/statistics/counters`

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
`POST https://gw.lamarzocco.io/v1/home/machines/<SN>/setting-preinfusion`

```json
{
    "button": "Continuous",
    "group": "Group1",
    "holdTimeMs": 2000,
    "wetTimeMs": 0
}
```

# Enable/Disable Preinfusion
`POST https://gw.lamarzocco.io/v1/home/machines/<SN>/enable-preinfusion`

```json
{
    "mode": "Disabled" // "Enabled"
}
```

# Power
`POST https://gw.lamarzocco.io/v1/home/machines/<SN>/status`

```json
{
    "status": "ON" // "STANDBY"
}
```

# Steam
`POST https://gw.lamarzocco.io/v1/home/machines/<SN>/enable-boiler`

```json
{
    "identitfier": "SteamBoiler",
    "state": True // False
}
```

# Temperature
`GET https://gw.lamarzocco.io/v1/home/machines/<SN>/target-boiler`

```json
{
    "identifier": "<Boilername",
    "value": "<temp>"
}
```

# Backflush
`GET https://gw.lamarzocco.io/v1/home/machines/<SN>/enable-backflush`

```json
{
    "enable": True
}
```

# Plumb In
`GET https://gw.lamarzocco.io/v1/home/machines/<SN>/enable-plumbin`

```json
{
    "enable": True // False
}
```

# Temperature
`GET https://gw.lamarzocco.io/v1/home/machines/<SN>/scheduling`

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