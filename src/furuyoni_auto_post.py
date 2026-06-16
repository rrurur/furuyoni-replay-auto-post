import datetime as dt
import hashlib
import json
import os
import re
import signal
import struct
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path


APP_NAME = "FuruyoniReplayAutoPost"
STARTUP_NAME = "Furuyoni Replay Auto Post.lnk"
GAME_DIR_NAME = "Furuyoni Digital Demo"
FIREBASE_API_KEY = "AIzaSyABKEbvIc5hSJzKrCSjAzFIhns5o_HhSkg"
FIREBASE_PROJECT_ID = "furuyoni-diary-1918f"
CURRENT_SEASON = "再演"

CHAR_ID_TO_NAME = {
    1: "yurina",
    2: "saine",
    3: "himika",
    4: "tokoyo",
    5: "oboro",
    6: "yukihi_a",
    7: "shinra",
    8: "hagane",
    9: "chikage",
    10: "kururu",
    11: "thallya",
    12: "raira",
    13: "utsuro",
    14: "honoka",
    15: "korunu",
    16: "yatsuha",
    17: "hatsumi",
    18: "mizuki",
    19: "megumi",
    20: "kanawe",
    21: "kamuwi",
    22: "renri",
    23: "akina",
    24: "shisui",
    25: "misora",
    26: "innealra_nornir_1",
}

TAROT_NAMES = [
    "yurina", "yurina_a1", "yurina_a2",
    "saine", "saine_a1", "saine_a2",
    "himika", "himika_a1",
    "tokoyo", "tokoyo_a1", "tokoyo_a2",
    "oboro", "oboro_a1", "oboro_a2",
    "yukihi_a", "yukihi_a1",
    "shinra", "shinra_a1",
    "hagane", "hagane_a1",
    "chikage", "chikage_a1",
    "kururu", "kururu_a1", "kururu_a2",
    "thallya", "thallya_a1",
    "raira", "raira_a1",
    "utsuro", "utsuro_a1",
    "honoka", "honoka_a1",
    "korunu",
    "yatsuha", "yatsuha_a1", "yatsuha_aa1",
    "hatsumi", "hatsumi_a1",
    "mizuki",
    "megumi",
    "kanawe",
    "kamuwi",
    "renri", "renri_a1",
    "akina",
    "shisui",
    "misora",
    "innealra_nornir_1", "innealra_nornir_2", "innealra_nornir_3",
    "korunu_a1", "megumi_a1",
]
TAROT_INDEX_BY_NAME = {name: index for index, name in enumerate(TAROT_NAMES)}


def app_dir():
    base = os.environ.get("APPDATA") or str(Path.home())
    path = Path(base) / APP_NAME
    path.mkdir(parents=True, exist_ok=True)
    return path


APP_DIR = app_dir()
CONFIG_FILE = APP_DIR / "config.json"
STATE_FILE = APP_DIR / "state.json"
LOG_FILE = APP_DIR / "log.jsonl"
PID_FILE = APP_DIR / "watcher.pid"


def log_event(row):
    row = {"at": dt.datetime.now(dt.timezone.utc).isoformat(), **row}
    with LOG_FILE.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(row, ensure_ascii=False) + "\n")


def load_json(path, default):
    try:
        if path.exists():
            return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        pass
    return default


def save_json(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")


def exe_command(watch=False):
    if getattr(sys, "frozen", False):
        command = [sys.executable]
    else:
        command = [sys.executable, str(Path(__file__).resolve())]
    if watch:
        command.append("--watch")
    return command


def exe_path_for_shortcut():
    if getattr(sys, "frozen", False):
        return sys.executable, "--watch"
    return sys.executable, f'"{Path(__file__).resolve()}" --watch'


def startup_link_path():
    return Path(os.environ["APPDATA"]) / "Microsoft" / "Windows" / "Start Menu" / "Programs" / "Startup" / STARTUP_NAME


def install_startup():
    target, arguments = exe_path_for_shortcut()
    link = startup_link_path()
    command = (
        "$w=New-Object -ComObject WScript.Shell; "
        f"$s=$w.CreateShortcut('{str(link)}'); "
        f"$s.TargetPath='{target}'; "
        f"$s.Arguments='{arguments}'; "
        f"$s.WorkingDirectory='{str(Path(target).parent)}'; "
        "$s.WindowStyle=7; "
        "$s.Save()"
    )
    subprocess.run(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", command], check=False)


def uninstall_startup():
    try:
        startup_link_path().unlink(missing_ok=True)
    except Exception:
        pass


def watcher_pid():
    try:
        if PID_FILE.exists():
            return int(PID_FILE.read_text(encoding="utf-8").strip())
    except Exception:
        pass
    return None


def is_process_running(pid):
    if not pid:
        return False
    try:
        os.kill(pid, 0)
        return True
    except Exception:
        return False


def stop_watcher():
    pid = watcher_pid()
    if pid and pid != os.getpid():
        try:
            os.kill(pid, signal.SIGTERM)
            time.sleep(0.5)
        except Exception:
            pass
    PID_FILE.unlink(missing_ok=True)


def enabled():
    return startup_link_path().exists() or is_process_running(watcher_pid())


def start_watcher():
    if is_process_running(watcher_pid()):
        return
    command = exe_command(watch=True)
    flags = 0
    if os.name == "nt":
        flags = getattr(subprocess, "CREATE_NO_WINDOW", 0) | getattr(subprocess, "DETACHED_PROCESS", 0)
    subprocess.Popen(command, creationflags=flags, close_fds=True)


def steam_roots():
    roots = []
    for env_name in ("ProgramFiles(x86)", "ProgramFiles"):
        base = os.environ.get(env_name)
        if base:
            roots.append(Path(base) / "Steam")
    config = load_json(CONFIG_FILE, {})
    if config.get("steam_root"):
        roots.insert(0, Path(config["steam_root"]))
    result = []
    seen = set()
    for root in roots:
        key = str(root).lower()
        if key not in seen:
            result.append(root)
            seen.add(key)
    return result


def parse_steam_libraries(steam_root):
    roots = [steam_root]
    vdf = steam_root / "steamapps" / "libraryfolders.vdf"
    try:
        text = vdf.read_text(encoding="utf-8", errors="ignore")
        for match in re.finditer(r'"path"\s+"([^"]+)"', text):
            roots.append(Path(match.group(1).replace("\\\\", "\\")))
    except Exception:
        pass
    result = []
    seen = set()
    for root in roots:
        key = str(root).lower()
        if key not in seen:
            result.append(root)
            seen.add(key)
    return result


def find_replay_dir():
    config = load_json(CONFIG_FILE, {})
    saved = config.get("replay_dir")
    if saved and Path(saved).exists():
        return Path(saved)

    for steam_root in steam_roots():
        for library in parse_steam_libraries(steam_root):
            candidate = library / "steamapps" / "common" / GAME_DIR_NAME / "replay"
            if candidate.exists():
                config["replay_dir"] = str(candidate)
                config["steam_root"] = str(steam_root)
                save_json(CONFIG_FILE, config)
                return candidate
    return None


def ask_replay_dir():
    replay_dir = find_replay_dir()
    if replay_dir:
        return replay_dir
    print("replayフォルダが見つかりません。")
    raw = input("replayフォルダのパスを入力してください: ").strip().strip('"')
    path = Path(raw)
    if not path.exists():
        raise RuntimeError("replayフォルダが見つかりませんでした。")
    config = load_json(CONFIG_FILE, {})
    config["replay_dir"] = str(path)
    save_json(CONFIG_FILE, config)
    return path


class MsgpackReader:
    def __init__(self, data):
        self.data = data
        self.index = 0

    def read(self, size):
        chunk = self.data[self.index:self.index + size]
        if len(chunk) != size:
            raise ValueError("unexpected end of msgpack data")
        self.index += size
        return chunk

    def unpack(self):
        code = self.read(1)[0]
        if code <= 0x7f:
            return code
        if code >= 0xe0:
            return code - 256
        if 0xa0 <= code <= 0xbf:
            return self.read(code & 0x1f).decode("utf-8", "replace")
        if 0x90 <= code <= 0x9f:
            return [self.unpack() for _ in range(code & 0x0f)]
        if 0x80 <= code <= 0x8f:
            return {self.unpack(): self.unpack() for _ in range(code & 0x0f)}
        if code == 0xc0:
            return None
        if code == 0xc2:
            return False
        if code == 0xc3:
            return True
        if code == 0xcc:
            return self.read(1)[0]
        if code == 0xcd:
            return struct.unpack(">H", self.read(2))[0]
        if code == 0xce:
            return struct.unpack(">I", self.read(4))[0]
        if code == 0xcf:
            return struct.unpack(">Q", self.read(8))[0]
        if code == 0xd0:
            return struct.unpack(">b", self.read(1))[0]
        if code == 0xd1:
            return struct.unpack(">h", self.read(2))[0]
        if code == 0xd2:
            return struct.unpack(">i", self.read(4))[0]
        if code == 0xd3:
            return struct.unpack(">q", self.read(8))[0]
        if code == 0xca:
            return struct.unpack(">f", self.read(4))[0]
        if code == 0xcb:
            return struct.unpack(">d", self.read(8))[0]
        if code == 0xd9:
            return self.read(self.read(1)[0]).decode("utf-8", "replace")
        if code == 0xda:
            return self.read(struct.unpack(">H", self.read(2))[0]).decode("utf-8", "replace")
        if code == 0xdb:
            return self.read(struct.unpack(">I", self.read(4))[0]).decode("utf-8", "replace")
        if code == 0xdc:
            return [self.unpack() for _ in range(struct.unpack(">H", self.read(2))[0])]
        if code == 0xdd:
            return [self.unpack() for _ in range(struct.unpack(">I", self.read(4))[0])]
        if code == 0xde:
            return {self.unpack(): self.unpack() for _ in range(struct.unpack(">H", self.read(2))[0])}
        if code == 0xdf:
            return {self.unpack(): self.unpack() for _ in range(struct.unpack(">I", self.read(4))[0])}
        if code in (0xc4, 0xc5, 0xc6):
            if code == 0xc4:
                size = self.read(1)[0]
            elif code == 0xc5:
                size = struct.unpack(">H", self.read(2))[0]
            else:
                size = struct.unpack(">I", self.read(4))[0]
            return self.read(size)
        raise ValueError(f"unsupported msgpack code 0x{code:02x}")


def parse_reply(path):
    raw = path.read_bytes()
    reader = MsgpackReader(raw)
    data = reader.unpack()
    if reader.index != len(raw):
        raise ValueError("unread trailing bytes")
    return data, hashlib.sha256(raw).hexdigest()


def player_name(data):
    local_id = data.get("LocalPlayerId")
    players = data.get("PlayersMeta") or {}
    name = str(players.get(local_id) or players.get(str(local_id)) or "Player").strip()
    return name or "Player"


def post_name(data):
    return f"{player_name(data).strip().lstrip('@')}(steam)"


def result_type_id(data):
    if data.get("IsDraw") or data.get("IsInterrupted"):
        return 2
    if data.get("Result") is True:
        return 0
    if data.get("Result") is False:
        return 1
    return 2


def card_code_to_path(code):
    if not code:
        return ""
    code = str(code)
    if code.startswith("re_"):
        code = "na_" + code[3:]
    return f"images/{code}.png"


def first_game_state(data):
    for record in data.get("Records") or []:
        if isinstance(record, dict) and isinstance(record.get("GameState"), dict):
            return record["GameState"]
    return None


def replay_card_path(all_cards, card_id, fallback_card_text_id=None):
    code = all_cards.get(card_id) or all_cards.get(str(card_id))
    if not code and fallback_card_text_id is not None:
        code = all_cards.get(fallback_card_text_id) or all_cards.get(str(fallback_card_text_id))
    return card_code_to_path(code)


def initial_deck_paths(data):
    local_id = data.get("LocalPlayerId")
    init = data.get("InitData") or {}
    all_cards = init.get("AllCardsData") or {}
    normal_zones = set()
    special_zones = set()
    for zone in init.get("CardZones") or []:
        if zone.get("PlayerId") != local_id:
            continue
        if zone.get("Type") == 257:
            normal_zones.add(zone.get("ID"))
        elif zone.get("Type") == 261:
            special_zones.add(zone.get("ID"))

    game_state = first_game_state(data)
    if not game_state:
        return []

    normals = []
    specials = []
    for card in game_state.get("CardsStatus") or []:
        if card.get("OwnerId") != local_id:
            continue
        path = replay_card_path(all_cards, card.get("ID"), card.get("CardTextId"))
        if not path:
            continue
        if card.get("Zone") in normal_zones and card.get("Type") == 1:
            normals.append(path)
        elif card.get("Zone") in special_zones and card.get("Type") == 2:
            specials.append(path)
    return normals[:7] + specials[:3]


def compact_record(data, source_path, file_hash):
    deck_paths = initial_deck_paths(data)
    init = data.get("InitData") or {}
    if len(deck_paths) < 10:
        all_cards = init.get("AllCardsData") or {}
        deck_paths = [replay_card_path(all_cards, card_id) for card_id in (init.get("SelectedCards") or [])[:10]]

    card_paths = deck_paths[:10]
    while len(card_paths) < 10:
        card_paths.append("")

    my_names = [CHAR_ID_TO_NAME.get(int(cid), str(cid)) for cid in (data.get("CharaIds") or [])[:3]]
    opp_names = [CHAR_ID_TO_NAME.get(int(cid), str(cid)) for cid in (data.get("OpponentCharaIds") or [])[:3]]
    my_indexes = [TAROT_INDEX_BY_NAME[name] for name in my_names if name in TAROT_INDEX_BY_NAME]
    opp_indexes = [TAROT_INDEX_BY_NAME[name] for name in opp_names if name in TAROT_INDEX_BY_NAME]
    timestamp_sec = int(data.get("Time") or time.time())

    return {
        "matchType": 0,
        "resultType": result_type_id(data),
        "season": CURRENT_SEASON,
        "deckName": "",
        "memo": "",
        "myTarotIdx": my_indexes,
        "oppTarotIdx": opp_indexes,
        "myTarotNames": my_names,
        "oppTarotNames": opp_names,
        "cardIds": [-1] * 10,
        "cardPaths": card_paths,
        "createdAtMs": timestamp_sec * 1000,
        "updatedAtMs": int(time.time() * 1000),
        "likeCount": 0,
        "_local": {
            "sourceFile": str(source_path),
            "sourceName": Path(source_path).name,
            "sha256": file_hash,
            "steamName": player_name(data),
            "displayHandle": post_name(data),
            "playedAtJst": dt.datetime.fromtimestamp(timestamp_sec, dt.timezone(dt.timedelta(hours=9))).isoformat(),
        }
    }


def firestore_value(value):
    if value is None:
        return {"nullValue": None}
    if isinstance(value, bool):
        return {"booleanValue": value}
    if isinstance(value, int):
        return {"integerValue": str(value)}
    if isinstance(value, float):
        return {"doubleValue": value}
    if isinstance(value, str):
        return {"stringValue": value}
    if isinstance(value, list):
        return {"arrayValue": {"values": [firestore_value(v) for v in value]}}
    if isinstance(value, dict):
        return {"mapValue": {"fields": {str(k): firestore_value(v) for k, v in value.items()}}}
    return {"stringValue": str(value)}


def firestore_doc(fields):
    return {"fields": {key: firestore_value(value) for key, value in fields.items()}}


def request_json(url, payload, token=None, method="POST"):
    data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    request = urllib.request.Request(url, data=data, method=method)
    request.add_header("Content-Type", "application/json")
    if token:
        request.add_header("Authorization", f"Bearer {token}")
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as error:
        body = error.read().decode("utf-8", "replace")
        raise RuntimeError(f"HTTP {error.code}: {body}") from error


def firebase_auth(state):
    auth = state.get("auth") or {}
    if auth.get("refreshToken") and auth.get("localId"):
        refreshed = request_json(
            f"https://securetoken.googleapis.com/v1/token?key={FIREBASE_API_KEY}",
            {"grant_type": "refresh_token", "refresh_token": auth["refreshToken"]},
        )
        state["auth"] = {
            "idToken": refreshed["id_token"],
            "localId": refreshed["user_id"],
            "refreshToken": refreshed.get("refresh_token", auth["refreshToken"]),
        }
        save_json(STATE_FILE, state)
        return state["auth"]

    auth = request_json(
        f"https://identitytoolkit.googleapis.com/v1/accounts:signUp?key={FIREBASE_API_KEY}",
        {"returnSecureToken": True},
    )
    state["auth"] = {
        "idToken": auth["idToken"],
        "localId": auth["localId"],
        "refreshToken": auth.get("refreshToken", ""),
    }
    save_json(STATE_FILE, state)
    return state["auth"]


def post_to_firestore(record, state):
    auth = firebase_auth(state)
    uid = auth["localId"]
    token = auth["idToken"]
    now = dt.datetime.now(dt.timezone.utc).isoformat().replace("+00:00", "Z")
    public_record = {key: value for key, value in record.items() if key != "_local"}
    public_record.update({"ownerUid": uid, "createdAt": now, "updatedAt": now})

    fields = {}
    for key, value in public_record.items():
        if key in ("createdAt", "updatedAt"):
            fields[key] = {"timestampValue": value}
        else:
            fields[key] = firestore_value(value)

    base = f"https://firestore.googleapis.com/v1/projects/{FIREBASE_PROJECT_ID}/databases/(default)/documents"
    handle = record["_local"]["displayHandle"]
    request_json(f"{base}/profiles/{uid}", firestore_doc({"handle": handle}), token=token, method="PATCH")
    request_json(f"{base}/users/{uid}", firestore_doc({"handle": handle, "updatedAt": now}), token=token, method="PATCH")
    return request_json(f"{base}/decks", {"fields": fields}, token=token)


def wait_until_stable(path):
    last_size = -1
    for _ in range(4):
        size = path.stat().st_size
        if size == last_size:
            return True
        last_size = size
        time.sleep(1)
    return path.stat().st_size == last_size


def process_file(path):
    data, file_hash = parse_reply(path)
    state = load_json(STATE_FILE, {"posted": {}, "known": [], "auth": None})
    if file_hash in state.get("posted", {}):
        return
    record = compact_record(data, path, file_hash)
    response = post_to_firestore(record, state)
    document = response.get("name", "")
    state.setdefault("posted", {})[file_hash] = {
        "sourceName": path.name,
        "postedAt": dt.datetime.now(dt.timezone.utc).isoformat(),
        "document": document,
        "summary": record["_local"],
    }
    save_json(STATE_FILE, state)
    log_event({"status": "posted", "document": document, **record["_local"]})


def watch_loop():
    replay_dir = find_replay_dir()
    if not replay_dir:
        log_event({"status": "error", "error": "replay folder not found"})
        return
    PID_FILE.write_text(str(os.getpid()), encoding="utf-8")
    state = load_json(STATE_FILE, {"posted": {}, "known": [], "auth": None})
    known = set(state.get("known") or [])
    current = {str(path) for path in replay_dir.glob("*.reply")}
    if not known:
        state["known"] = sorted(current)
        save_json(STATE_FILE, state)
        known = current
    log_event({"status": "watching", "replayDir": str(replay_dir)})
    try:
        while True:
            state = load_json(STATE_FILE, {"posted": {}, "known": [], "auth": None})
            known = set(state.get("known") or [])
            for path in sorted(replay_dir.glob("*.reply"), key=lambda p: p.stat().st_mtime):
                key = str(path)
                if key in known:
                    continue
                try:
                    if wait_until_stable(path):
                        process_file(path)
                    known.add(key)
                    state["known"] = sorted(known)
                    save_json(STATE_FILE, state)
                except Exception as exc:
                    log_event({"status": "error", "sourceFile": key, "error": str(exc)})
            time.sleep(5)
    finally:
        PID_FILE.unlink(missing_ok=True)


def enable_auto_post():
    replay_dir = ask_replay_dir()
    install_startup()
    start_watcher()
    print("自動投稿を有効化しました。")
    print(f"監視フォルダ: {replay_dir}")


def disable_auto_post():
    stop_watcher()
    uninstall_startup()
    print("自動投稿を無効化しました。")


def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8")

    if "--watch" in sys.argv:
        watch_loop()
        return

    if enabled():
        answer = input("自動投稿は有効です。無効化しますか？ (Y/N) ").strip().lower()
        if answer == "y":
            disable_auto_post()
        else:
            print("終了します。")
    else:
        enable_auto_post()
    input("Enterで閉じます。")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        log_event({"status": "fatal", "error": str(exc)})
        print(f"エラー: {exc}")
        input("Enterで閉じます。")
