# URLs
TOKEN_URL = "https://cms.lamarzocco.io/oauth/v2/token"
CUSTOMER_URL = "https://cms.lamarzocco.io/api/customer"
GW_MACHINE_BASE_URL = "https://gw.lamarzocco.io/v1/home/machines"


# Key Names for Dictionaries
KEY = "key"
SERIAL_NUMBER = "serial_number"
MACHINE_NAME = "machine_name"
MODEL_NAME = "model_name"
STEAM_BOILER_NAME = "SteamBoiler"
COFFEE_BOILER_NAME = "CoffeeBoiler1"
BOILER_TARGET_TEMP = "boilerTargetTemperature"
BOILERS = "boilers"
PLUMBED_IN = "isPlumbedIn"
WEEKLY_SCHEDULING_CONFIG = "weeklySchedulingConfig"


# helper functions
# convert schedule return format to API expected input format
def convert_schedule(schedule):
    days = ["monday", "tuesday", "wednesday", "thursay", "friday", "saturday", "sunday"]
    schedule_conv = []
    for day in days: 
        d = schedule[day]
        schedule_conv.append({
            "day": str.upper(day),
            "enabled": d["enabled"],
            "on" : d["h_on"] + ":" + d["m_on"].zfill(2),
            "off": d["h_off"] + ":" + d["m_off"].zfill(2)
        })

        