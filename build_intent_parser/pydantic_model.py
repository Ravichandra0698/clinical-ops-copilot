# "pydantic" is a library, installed with FastAPI, that checks data.
# BaseModel is the starting point for describing what valid data looks like.
import json

from pydantic import BaseModel


# A "class" is a blueprint. This one is a blueprint for "a valid intent".
# Putting (BaseModel) after the name gives our class Pydantic's checking powers.
# WHY: we describe the shape ONCE here, and every use of it is checked for us.
class QueryIntent(BaseModel):
    # Each line is "field name: type".
    # "str" means this field must be text. This is called a type hint.
    intent: str
    group_by: str


# Create one object from the blueprint, filling in each field.
# WHY: this is the "good" case. Pydantic accepts it silently.
good = QueryIntent(intent="dropout_rate", group_by="site")

# Printing shows the whole object. A dot reads one field, like data["intent"] did.
print(good)
print(good.intent)

try:
    broken = QueryIntent(intent="dropout_rate")
except Exception as error:

    print("Pydantic says:")
    print(error)


reply = '{"intent": "droupout_rate", "group_by": "site"}'
data = json.loads(reply)

# "**data" unpacks the dictionary into named fields. It is the same as writing
# QueryIntent(intent="droupout_rate", group_by="site").
checked = QueryIntent(**data)
print(checked)