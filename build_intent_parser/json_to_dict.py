import json

reply = '{"intent":"droupout_rate", "group_by":"site"}'

print(type(reply))

data = json.loads(reply)
print(type(data))
print(data["intent"])
