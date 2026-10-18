import json

# A list of every intent our program understands.
# WHY: this is the "menu". Anything not on the menu is an error.
# Square brackets make a list: an ordered collection of values.
ALLOWED_INTENTS = [
    "dropout_rate",
    "visit_lateness",
    "ae_reporting_lag",
    "missed_visit_rate",
    "data_quality",
    "definition",
    "other",
]


# "def" defines a function: a named block of code we can run many times.
# "data" in the brackets is the input it receives when we call it.
# WHY a function: we will check many model replies, and we don't want to
# copy the same lines each time.
def check_intent(data):
    # "not in" asks: is this key absent from the dictionary?
    # WHY: data["intent"] on a missing key would crash with a KeyError.
    if "intent" not in data:
        return "missing field: intent"

    # Now we know the key exists, so looking it up is safe.
    # "not in" also works on lists: is the value absent from the menu?
    if data["intent"] not in ALLOWED_INTENTS:
        # "+" joins two pieces of text together.
        return "unknown intent: " + data["intent"]

    # If we got here, both checks passed.
    return "ok"


# Your typo from Part 1, kept on purpose so we can catch it.
reply = '{"intent": "droupout_rate", "group_by": "site"}'
data = json.loads(reply)

# Call the function and show what it says.
print(check_intent(data))