from flask import Flask, request, jsonify
import json, datetime, hashlib, os

app = Flask(__name__)

DB_FILE = "licenses.json"

def load_db():
    if not os.path.exists(DB_FILE):
        return {}
    with open(DB_FILE, "r") as f:
        return json.load(f)

def save_db(data):
    with open(DB_FILE, "w") as f:
        json.dump(data, f, indent=4)

def generate_key(account, hwid):
    raw = f"{account}-{hwid}-{datetime.datetime.now()}"
    return hashlib.sha256(raw.encode()).hexdigest()[:20].upper()

@app.route("/create", methods=["POST"])
def create():
    data = request.json
    db = load_db()

    account = data["account"]
    hwid = data["hwid"]
    period = data["period"]

    expiry = (datetime.datetime.now() + datetime.timedelta(days=period)).strftime("%Y-%m-%d")

    key = generate_key(account, hwid)

    db[key] = {
        "account": account,
        "hwid": hwid,
        "expiry": expiry,
        "status": "active"
    }

    save_db(db)

    return jsonify({"license": key})

@app.route("/verify", methods=["POST"])
def verify():
    data = request.json
    db = load_db()

    key = data["license"]
    account = str(data["account"])
    hwid = data["hwid"]

    if key not in db:
        return jsonify({"status": "invalid"})

    lic = db[key]

    if lic["account"] != account:
        return jsonify({"status": "invalid_account"})

    if lic["hwid"] != hwid:
        return jsonify({"status": "invalid_hwid"})

    if lic["status"] != "active":
        return jsonify({"status": "blocked"})

    if datetime.datetime.now().strftime("%Y-%m-%d") > lic["expiry"]:
        return jsonify({"status": "expired"})

    return jsonify({"status": "valid"})

app.run(host="0.0.0.0", port=10000)
