# Literal lets us say "the value must be exactly one of THESE words".
# WHY: this replaces the ALLOWED_INTENTS list and the "not in" check from Part 2.
from typing import Literal

# ValidationError is the specific error Pydantic raises for bad data.
# WHY: catching the specific error means we don't hide unrelated bugs.
import re
from pydantic import BaseModel, Field, ValidationError, field_validator


class QueryIntent(BaseModel):
    # Each quoted word is one allowed value. Any other text is rejected.
    intent: Literal[
        "dropout_rate",
        "visit_lateness",
        "ae_reporting_lag",
        "missed_visit_rate",
        "data_quality",
        "definition",
        "other",
    ]
    group_by: Literal["site", "study", "arm", "none"]
        # "str | None" means: text OR nothing at all.
    # "= None" is the default: if the field is not given, it becomes None.
    # WHY: not every question names a site, so this field must be allowed to be empty.
    site_id: str | None = None

    # "int | None" means a whole number or nothing. ge=1 and le=50 mean
    # "greater than or equal to 1" and "less than or equal to 50".
    # WHY: "top 3 sites" gives 3, but 0, -5 or 9000 make no sense.
    top_n: int | None = Field(default=None, ge=1, le=50)
        # A decorator is a line starting with @. It adds a power to the function below it.
    # @field_validator says: "run this function on site_id".
    # mode="before" means: run it BEFORE Pydantic checks the type, so we can clean first.
    @field_validator("site_id", mode="before")
    @classmethod
    def clean_site_id(cls, value):
        # Treat empty-looking answers as "no site".
        if value is None or str(value).strip().lower() in ["", "null", "none"]:
            return None

        # Tidy the text: remove spaces and make it upper case.
        cleaned = str(value).strip().upper()

        # A pattern check: the letters SITE followed by exactly 4 digits.
        # WHY: this blocks made-up codes before they reach a database query.
        if not re.fullmatch(r"SITE\d{4}", cleaned):
            raise ValueError("site_id must look like SITE0412")
        return cleaned


# Your typo again. This time it should be caught.
typo_reply = {"intent": "droupout_rate", "group_by": "site"}

try:
    QueryIntent(**typo_reply)
except ValidationError as error:
    print("Rejected:")
    print(error)

# The corrected reply should pass silently and print the object.
good_reply = {"intent": "dropout_rate", "group_by": "site"}
print(QueryIntent(**good_reply))

print(QueryIntent(intent="other", group_by="none"))
print(QueryIntent(intent="dropout_rate", group_by="site", top_n=3))
try:
    QueryIntent(intent="dropout_rate", group_by="site", top_n=0)
except ValidationError as error:
    print(error)

print(QueryIntent(intent="dropout_rate", group_by="none", site_id="site0412").site_id)
print(QueryIntent(intent="dropout_rate", group_by="none", site_id="null").site_id)
try:
    QueryIntent(intent="dropout_rate", group_by="none", site_id="SITE12")
except ValidationError as error:
    print(error)