'''
helper functions
'''

# convert schedule return format to API expected input format
def convert_schedule(schedule):
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
            "enabled": schedule[day]["enabled"],
            "on" : hh_mm_on,
            "off": hh_mm_off
        })
    return schedule_conv