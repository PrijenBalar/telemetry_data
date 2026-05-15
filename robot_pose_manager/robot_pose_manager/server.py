import json
from http.server import HTTPServer, BaseHTTPRequestHandler
from pathlib import Path
import urllib.request
import urllib.parse

BASE_DIR  = Path(__file__).parent
TASKS_DIR = BASE_DIR / "tasks"
TASKS_DIR.mkdir(exist_ok=True)
HTML_FILE = BASE_DIR / "index.html"

HOST, PORT  = "0.0.0.0", 5050
ROBOT_IP    = "192.168.4.1"


# ── DATA HELPERS ──────────────────────────────────────────────────────────────

def task_file(task: str) -> Path:
    safe = "".join(c for c in task if c.isalnum() or c in "_-")
    return TASKS_DIR / f"{safe}.json"


def load(task: str) -> dict:
    f = task_file(task)
    if not f.exists():
        f.write_text(json.dumps({"positions": {}}, indent=2))
    data = json.loads(f.read_text())
    if "positions" not in data:
        data["positions"] = {}
    return data


def save(task: str, data: dict):
    task_file(task).write_text(json.dumps(data, indent=2))


def next_id(data: dict) -> str:
    i = 1
    while str(i) in data["positions"]:
        i += 1
    return str(i)


def parse_qs(path: str) -> dict:
    if "?" not in path:
        return {}
    return dict(urllib.parse.parse_qsl(path.split("?", 1)[1]))


def path_base(path: str) -> str:
    return path.split("?")[0]


# ── HANDLER ───────────────────────────────────────────────────────────────────

class Handler(BaseHTTPRequestHandler):

    def log_message(self, *_):
        pass

    def _cors(self):
        self.send_header("Access-Control-Allow-Origin",  "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, PUT, DELETE, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")

    def _json(self, code: int, data):
        body = json.dumps(data).encode()
        self.send_response(code)
        self._cors()
        self.send_header("Content-Type",   "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _html(self):
        body = HTML_FILE.read_bytes()
        self.send_response(200)
        self._cors()
        self.send_header("Content-Type",   "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _body(self) -> dict:
        n = int(self.headers.get("Content-Length", 0))
        if n == 0:
            return {}
        return json.loads(self.rfile.read(n))

    def _forward(self, path: str):
        try:
            url = f"http://{ROBOT_IP}{path}"
            print("Forward →", url)
            req = urllib.request.Request(url, method="POST")
            with urllib.request.urlopen(req, timeout=3) as r:
                body = r.read()
            self.send_response(200)
            self._cors()
            self.end_headers()
            self.wfile.write(body)
        except Exception as e:
            print("Forward error:", e)
            self._json(500, {"error": str(e)})

    # ── OPTIONS ──

    def do_OPTIONS(self):
        self.send_response(204)
        self._cors()
        self.end_headers()

    # ── GET ──

    def do_GET(self):
        base = path_base(self.path)
        qs   = parse_qs(self.path)

        if base in ("/", "/index.html"):
            return self._html()

        # GET /tasks  →  list all task names
        if base == "/tasks":
            tasks = [f.stem for f in sorted(TASKS_DIR.glob("*.json"))]
            return self._json(200, {"tasks": tasks})

        # GET /positions?task=<name>
        if base == "/positions":
            task = qs.get("task", "task1")
            return self._json(200, load(task))

        # GET /export?task=<name>  →  download JSON file
        if base == "/export":
            task = qs.get("task", "task1")
            f = task_file(task)
            if not f.exists():
                return self._json(404, {"error": "not found"})
            body = f.read_bytes()
            self.send_response(200)
            self._cors()
            self.send_header("Content-Type",        "application/json")
            self.send_header("Content-Disposition", f'attachment; filename="{task}.json"')
            self.send_header("Content-Length",      str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return

        self._json(404, {"error": "not found"})

    # ── POST ──

    def do_POST(self):
        base = path_base(self.path)
        qs   = parse_qs(self.path)

        # Forward stepper / gripper commands to the robot
        if base.startswith("/stepper") or base.startswith("/gripper"):
            return self._forward(self.path)

        #    /tasks  →  create task (just touching the file is enough)
        if base == "/tasks":
            body = self._body()
            name = body.get("name", "").strip()
            if not name:
                return self._json(400, {"error": "name required"})
            f = task_file(name)
            if not f.exists():
                f.write_text(json.dumps({"positions": {}}, indent=2))
            return self._json(201, {"name": name})

        # POST /positions?task=<name>
        if base == "/positions":
            task = qs.get("task", "task1")
            body = self._body()
            data = load(task)
            pid  = next_id(data)
            # data["positions"][pid] = body
            data["positions"][pid] = {
            "joints": body.get("joints", {}),
            "gripper": body.get("gripper", "open")
            }
            save(task, data)
            return self._json(201, {"id": pid})

        self._json(404, {"error": "not found"})

    # ── PUT ──

    def do_PUT(self):
        base = path_base(self.path)
        qs   = parse_qs(self.path)

        if not base.startswith("/positions/"):
            return self._json(404, {"error": "not found"})

        pid  = base.split("/positions/")[1]
        task = qs.get("task", "task1")
        body = self._body()
        data = load(task)

        if pid not in data["positions"]:
            return self._json(404, {"error": "not found"})

        # data["positions"][pid] = body
        data["positions"][pid] = {
            "joints": body.get("joints", {}),
            "gripper": body.get("gripper", "open")
        }
        save(task, data)
        self._json(200, {"id": pid})

    # ── DELETE ──

    def do_DELETE(self):
        base = path_base(self.path)
        qs   = parse_qs(self.path)

        # DELETE /tasks/<name>
        if base.startswith("/tasks/"):
            name = base.split("/tasks/")[1]
            f = task_file(name)
            if f.exists():
                f.unlink()
            return self._json(200, {"deleted": name})

        # DELETE /positions/<id>?task=<name>
        if base.startswith("/positions/"):
            pid  = base.split("/positions/")[1]
            task = qs.get("task", "task1")
            data = load(task)
            if pid in data["positions"]:
                del data["positions"][pid]
                save(task, data)
            return self._json(200, {"deleted": pid})

        self._json(404, {"error": "not found"})


# ── ENTRY POINT ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    server = HTTPServer((HOST, PORT), Handler)
    print(f"Running at http://127.0.0.1:{PORT}")
    server.serve_forever()
