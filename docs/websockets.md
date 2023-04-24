# Websocket APIs

## Inititate connection

```
ws://IP:8081/api/v1/streaming -H "Authorization: Bearer <Token>"
```

## Brewing Time

```json
[
    {
        "name": "BrewingStartedGroup1StopType",
        "value": "Continuous"
    },
    {
        "name": "BrewingStartedGroup1DoseIndex",
        "value": "ContinuousDose"
    }
]
```


```json
[
    {
        "name": "BrewingUpdateGroup1Time",
        "value": 0.10000000149011612
    }
]
```

```json
[
    {
        "name": "BrewingUpdateGroup1Time",
        "value": 0.20000000298023224
    }
]
```

```json
[
    {
        "name": "BrewingUpdateGroup1Time",
        "value": 0.300000011920929
    }
]
```

```json
[
    {
        "name": "BrewingSnapshotGroup1",
        "value": "{\"groupConfiguration\":{\"groupNumber\":\"Group1\",\"capabilities\":{\"groupType\":\"AV_Group\",\"boilerId\":\"CoffeeBoiler1\",\"boilerTemperature\":60,\"hasScale\":false,\"hasFlowmeter\":false},\"dose\":{\"doseIndex\":\"ContinuousDose\",\"stopTarget\":0},\"doseMode\":{}},\"flushInfo\":{\"doseIndex\":\"ContinuousDose\",\"stopReason\":\"Manual\",\"time\":5.4000000953674316,\"volume\":0}}"
    },
    {
        "name": "FlushStoppedGroup1DoseIndex",
        "value": "ContinuousDose"
    },
    {
        "name": "FlushStoppedGroup1Time",
        "value": 5.4000000953674316
    }
]
```

## Steam Boiler Temp
```json
{
    "name": "CoffeeBoiler1UpdateTemperature",
    "value": 76
}
```

## Coffee Boiler Temp
```json
{
    "name": "SteamBoilerUpdateTemperature",
    "value": 97
}
```