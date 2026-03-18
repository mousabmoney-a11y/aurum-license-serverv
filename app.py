from flask import Flask, request, jsonify
import json, datetime, os, hashlib

app = Flask(__name__)

DB_FILE = "licenses.json"
DELETED_FILE = "deleted.json"
EXPIRED_FILE = "expired.json"
LOG_FILE = "logs.json"

# ================= FILE HELPERS =================

def load(file):
    if not os.path.exists(file):
        return {}
    with open(file, "r") as f:
        return json.load(f)

def save(file, data):
    with open(file, "w") as f:
        json.dump(data, f, indent=4)

def log(action, data):
    logs = load(LOG_FILE)
    now = str(datetime.datetime.now())
    logs[now] = {"action": action, "data": data}
    save(LOG_FILE, logs)

# ================= UTILS =================

def generate_key():
    return hashlib.sha256(str(datetime.datetime.now()).encode()).hexdigest()[:20].upper()

def get_expiry(period):
    if period == "lifetime":
        return "lifetime"

    days_map = {
        "1d": 1,
        "1m": 30,
        "2m": 60,
        "3m": 90,
        "1y": 365,
        "2y": 730
    }

    if period in days_map:
        days = days_map[period]
    else:
        days = int(period)  # custom days

    return (datetime.datetime.now() + datetime.timedelta(days=days)).strftime("%Y-%m-%d")

# ================= CREATE =================

@app.route("/create", methods=["POST"])
def create():
    db = load(DB_FILE)
    data = request.json

    key = generate_key()

    db[key] = {
        "username": data.get("username", "unknown"),
        "accounts": [],
        "hwid": data.get("hwid", ""),
        "created_at": str(datetime.datetime.now()),
        "expiry": get_expiry(data.get("period", "30")),
        "status": "active"
    }

    save(DB_FILE, db)
    log("CREATE", db[key])

    return jsonify({"license": key})

# ================= VERIFY =================

@app.route("/verify", methods=["POST"])
def verify():
    db = load(DB_FILE)
    expired = load(EXPIRED_FILE)

    data = request.json

    key = data.get("license")
    account = str(data.get("account"))
    hwid = data.get("hwid")

    if key not in db:
        return jsonify({"status": "invalid"})

    lic = db[key]

    # PAUSED
    if lic["status"] == "paused":
        return jsonify({"status": "paused"})

    # HWID LOCK
    if lic["hwid"] == "":
        lic["hwid"] = hwid

    if lic["hwid"] != hwid:
        return jsonify({"status": "device_changed"})

    # ACCOUNT LIMIT (MAX 5)
    if account not in lic["accounts"]:
        if len(lic["accounts"]) >= 5:
            return jsonify({"status": "max_accounts"})
        lic["accounts"].append(account)

    # EXPIRY CHECK
    if lic["expiry"] != "lifetime":
        today = datetime.datetime.now().strftime("%Y-%m-%d")
        if today > lic["expiry"]:
            expired[key] = lic
            save(EXPIRED_FILE, expired)

            del db[key]
            save(DB_FILE, db)

            return jsonify({"status": "expired"})

    save(DB_FILE, db)
    return jsonify({"status": "valid"})

# ================= PAUSE =================

@app.route("/pause", methods=["POST"])
def pause():
    db = load(DB_FILE)
    key = request.json.get("license")

    if key in db:
        db[key]["status"] = "paused"
        save(DB_FILE, db)
        log("PAUSE", db[key])
        return jsonify({"msg": "paused"})

    return jsonify({"msg": "not found"})

# ================= UNPAUSE =================

@app.route("/unpause", methods=["POST"])
def unpause():
    db = load(DB_FILE)
    key = request.json.get("license")

    if key in db:
        db[key]["status"] = "active"
        save(DB_FILE, db)
        log("UNPAUSE", db[key])
        return jsonify({"msg": "active"})

    return jsonify({"msg": "not found"})

# ================= RENEW =================

@app.route("/renew", methods=["POST"])
def renew():
    db = load(DB_FILE)
    data = request.json

    key = data.get("license")
    period = data.get("period")

    if key in db:
        db[key]["expiry"] = get_expiry(period)
        save(DB_FILE, db)
        log("RENEW", db[key])
        return jsonify({"msg": "renewed"})

    return jsonify({"msg": "not found"})

# ================= SEARCH =================

@app.route("/search", methods=["POST"])
def search():
    db = load(DB_FILE)
    username = request.json.get("username")

    results = {}

    for k, v in db.items():
        if v["username"].lower() == username.lower():
            results[k] = v

    return jsonify(results)


# 🔥 KU DAR HALKAN
@app.route("/")
def home():
    return "Server is running ✅"


# ================= START =================

app.run(host="0.0.0.0", port=10000)

# ================= DELETE =================

@app.route("/delete", methods=["POST"])
def delete():
    db = load(DB_FILE)
    deleted = load(DELETED_FILE)

    key = request.json.get("license")

    if key in db:
        deleted[key] = db[key]
        save(DELETED_FILE, deleted)

        del db[key]
        save(DB_FILE, db)

        log("DELETE", key)
        return jsonify({"msg": "deleted"})

    return jsonify({"msg": "not found"})

# ================= GET ALL =================

@app.route("/all", methods=["GET"])
def get_all():
    return jsonify(load(DB_FILE))

# ================= HISTORY =================

@app.route("/logs", methods=["GET"])
def get_logs():
    return jsonify(load(LOG_FILE))

# ================= SEARCH =================

@app.route("/search", methods=["POST"])
def search():
    db = load(DB_FILE)
    username = request.json.get("username")

    results = {}

    for k, v in db.items():
        if v["username"].lower() == username.lower():
            results[k] = v

    return jsonify(results)

# ================= START =================

app.run(host="0.0.0.0", port=10000)
