"""Print a canned advisory receipt; no scientific or model execution."""
import json
from context_contract import accept_recommendation
from fixtures import fixture_triplet

source, context, advice = fixture_triplet()
print(json.dumps({"scope": "Artificial, canned engineering example only",
                  "receipt": accept_recommendation(context, advice, source)}, indent=2))
