# Websocket APIs

## Inititate connection

```
ws://IP:8081/api/v1/streaming -H "Authorization: Bearer <Token>"
```

# Messages
## Statistics
```json
[
    {
        "MachineStatistics": "{\"groups\":[{\"doses\":[{\"DoseA\":343},{\"DoseB\":0},{\"DoseC\":0},{\"DoseD\":0},{\"ContinuousDose\":0}],\"clean\":0,\"ev_activations\":1012,\"ev_ontime\":11849}],\"tot_doses\":343,\"boilers\":[{\"rsteam_ontime\":25},{\"rcoffee_ontime\":37}],\"tea\":{\"count\":0,\"ev_activation\":0,\"ev_ontime\":0},\"pump_ontime\":11660,\"machine_ontime\":2522,\"refill_ontime\":473,\"count_liter\":0}"
    }
]
```

## SystemInfo
```json
{
    "SystemInfo": "{\"network_interfaces\":[{\"name\":\"wlan0\",\"address\":\"192.168.x.x\",\"mac\":\"<MAC>\",\"auth\":\"WPA2_WPA3_PSK\",\"channel\":11,\"rssi\":-61}],\"system_ram\":[{\"name\":\"internal\",\"free\":48671,\"allocated\":244116},{\"name\":\"external\",\"free\":4046327,\"allocated\":380152}],\"cpu\":{\"cpu0\":14,\"cpu1\":11},\"connections\":{\"ws\":21,\"ble\":17,\"mqtt\":10,\"wifi\":3},\"up_time\":228801,\"curr_time\":\"2023-07-10 06:03:50\",\"boot_reason\":\"ESP_RST_POWERON\",\"boot_count\":0,\"timezone\":2,\"fs\":{\"total\":4096000,\"used\":16384,\"files\":[{\"path\":\"/storage/auth\",\"size\":175},{\"path\":\"/storage/cert.crt\",\"size\":1224},{\"path\":\"/storage/log.txt\",\"size\":0},{\"path\":\"/storage/private.key\",\"size\":1675}]}}"
}
```

## Brewing Snapshot
```json
[
    {
        "BrewingSnapshotGroup1": "{\"groupConfiguration\":{\"groupNumber\":\"Group1\",\"capabilities\":{\"groupType\":\"AV_Group\",\"boilerId\":\"CoffeeBoiler1\",\"boilerTemperature\":47,\"hasScale\":false,\"hasFlowmeter\":true},\"dose\":{\"doseIndex\":\"DoseA\",\"stopTarget\":0,\"doseType\":\"PulsesType\"},\"doseMode\":{\"brewingType\":\"PulsesType\"}},\"flushInfo\":{\"doseIndex\":\"DoseA\",\"stopReason\":\"Manual\",\"time\":6.7829999923706055,\"stopType\":\"Volumetric\",\"volume\":0}}"
    },
    {
        "FlushStoppedGroup1DoseIndex": "DoseA"
    },
    {
        "FlushStoppedGroup1Time": 6.783
    },
    {
        "FlushStoppedGroup1Volume": 0
    }
]
```

## Brewing Update
```json
[
    {
        "BrewingUpdateGroup1Time": 6.188
    },
    {
        "BrewingUpdateGroup1Ev": true
    },
    {
        "BrewingUpdateGroup1Volume": 0
    }
]
```

## Brewing stopped
```json
[{'BrewingStartedGroup1StopType': 'Volume'}, {'BrewingStartedGroup1DoseIndex': 'DoseA'}, {'BrewingStartedGroup1VolumeTarget': 0}]
```

## Wake up
```json
[
    {
        "WakeUp": "manual"
    }
]
```

## Sleep 
```json
[
    {
        "Sleep": "command"
    }
]
```