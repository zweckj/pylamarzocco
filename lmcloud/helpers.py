'''
helper functions
'''

def schedule_out_to_in(schedule):
    """ convert schedule return format to API expected input format """
    days = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]
    schedule_conv = []
    for day in days: 

        # requests wants 00:00, response gives 24:00
        h_on = "00" if schedule[day]["h_on"] == 24 else str(schedule[day]["h_on"]).zfill(2)
        h_off = "00" if schedule[day]["h_off"] == 24 else str(schedule[day]["h_off"]).zfill(2)

        hh_mm_on = h_on + ":" + str(schedule[day]["m_on"]).zfill(2)
        hh_mm_off = h_off + ":" + str(schedule[day]["m_off"]).zfill(2)

        schedule_conv.append({
            "day": str.upper(day),
            "enable": schedule[day]["enabled"],
            "on" : hh_mm_on,
            "off": hh_mm_off
        })
    return schedule_conv

def schedule_in_to_out(enable, schedule):
    """ convert API input format to API output format"""
    out = {"enabled": enable}
    for day in schedule:
        out[day["day"].lower()] = {
            "enabled": day["enable"],
            "h_on": 24 if day["on"].split(':')[0] == "00" else int(day["on"].split(':')[0]),
            "h_off": 24 if day["off"].split(':')[0] == "00" else int(day["off"].split(':')[0]),
            "m_on": int(day["on"].split(':')[1]),
            "m_off": int(day["off"].split(':')[1])
        }
    return out

def schedule_out_to_hass(config) -> dict:
    """ API output schedule (config obj) to hass config """
    parsed = {}
    weeklySchedulingConfig = config.get("weeklySchedulingConfig", {})
    for key in weeklySchedulingConfig.keys():
        if key == "enabled":
            parsed["global_auto"] = "Enabled" if weeklySchedulingConfig[key] else "Disabled"
        else:
            day_short = key[0:3]
            config_day = weeklySchedulingConfig.get(key, {})
            enabled   = "Enabled" if config_day.get("enabled", False) else "Disabled"
            h_on      = config_day.get("h_on", 0)
            h_off     = config_day.get("h_off", 0)
            m_on      = config_day.get("m_on", 0)
            m_off     = config_day.get("m_off", 0)
            parsed[f"{day_short}_auto"] =       enabled
            parsed[f"{day_short}_on_min"] =     m_on
            parsed[f"{day_short}_off_min"] =    m_off
            parsed[f"{day_short}_on_hour"] =    h_on
            parsed[f"{day_short}_off_hour"] =    h_off
            parsed[f"{day_short}_on_time"] =    str(h_on) + ":" + str(m_on).zfill(2)
            parsed[f"{day_short}_off_time"] =   str(h_off) + ":" + str(m_off).zfill(2)

    return parsed

def parse_preinfusion_settings(config) -> dict:
    parsed = {}
    i = 1
    preinfusion_settings = config.get("preinfusionSettings", {})
    mode = preinfusion_settings.get("mode", "Disabled")
    for group in preinfusion_settings.get("Group1", {}):
        if mode == "Disabled":
            parsed[f"preinfusion_k{i}"] = 0
            parsed[f"prebrewing_ton_k{i}"] = 0
            parsed[f"prebrewing_toff_k{i}"] = 0
        elif mode == "Enabled":
            parsed[f"prebrewing_ton_k{i}"] = group.get("preWetTime", 0)
            parsed[f"prebrewing_toff_k{i}"] = group.get("preWetHoldTime", 0)
            parsed[f"preinfusion_k{i}"] = 0
        elif mode == "TypeB":
            parsed[f"prebrewing_ton_k{i}"] = 0
            parsed[f"prebrewing_toff_k{i}"] = 0
            parsed[f"preinfusion_k{i}"] = group.get("preWetHoldTime", 0)
        i += 1
    return parsed

def parse_doses(config) -> dict:
    parsed = {}
    i = 1
    groupCapabilities = config.get("groupCapabilities", [])
    if len(groupCapabilities) == 0:
        return parsed
    
    for dose in groupCapabilities[0].get("doses", []):
        parsed[f"dose_k{i}"] = dose.get("stopTarget", 0)
        i += 1
    parsed["dose_hot_water"] = config.get("teaDoses", {}).get("DoseA", {}).get("stopTarget", 0)
    return parsed

def parse_statistics(statistics) -> dict:
    parsed = {}

    if len(statistics) == 0:
        return parsed
    
    parsed["total_flushing"] = statistics[-1].get("count", 0)
    i = 1
    coffee_sum = 0
    for stat in statistics:
        coffeeType = stat["coffeeType"]
        count = stat["count"]
        if coffeeType >= 0 and coffeeType < 4:
            parsed[f"drinks_k{coffeeType + 1}"] = count
            coffee_sum += count
        elif coffeeType == 4:
            parsed["continuous"] = count
            coffee_sum += count
        elif coffeeType == -1:
            parsed["total_flushing"] = count
    parsed["total_coffee"] = coffee_sum
    return parsed

