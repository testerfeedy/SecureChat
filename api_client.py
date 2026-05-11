"""
HTTP + WebSocket клиент для SecureChat API
"""

import json
import threading
import time
from typing import Callable, Optional
import requests
import websocket


class SecureChatAPI:
    """REST API клиент"""

    def __init__(self, base_url: str):
        self.base_url = base_url.rstrip("/")
        self.token: Optional[str] = None
        self.user: Optional[dict] = None
        self.session = requests.Session()
        self.session.timeout = 10

    def _headers(self) -> dict:
        h = {"Content-Type": "application/json"}
        if self.token:
            h["Authorization"] = f"Bearer {self.token}"
        return h

    def _request(self, method: str, path: str, **kwargs) -> dict:
        url = f"{self.base_url}{path}"
        resp = self.session.request(method, url, headers=self._headers(), **kwargs)
        if not resp.ok:
            try:
                detail = resp.json().get("detail", resp.text)
            except Exception:
                detail = resp.text
            raise APIError(f"HTTP {resp.status_code}: {detail}")
        return resp.json()

    # Auth
    def register(self, email: str, username: str, password: str) -> dict:
        data = self._request("POST", "/auth/register", json={
            "email": email, "username": username, "password": password
        })
        self.token = data["token"]
        self.user = data["user"]
        return data

    def login(self, email: str, password: str) -> dict:
        data = self._request("POST", "/auth/login", json={"email": email, "password": password})
        self.token = data["token"]
        self.user = data["user"]
        return data

    def me(self) -> dict:
        return self._request("GET", "/auth/me")

    # Users
    def get_users(self) -> list:
        return self._request("GET", "/users")

    def upload_public_key(self, user_id: str, public_key: str):
        self._request("POST", f"/users/{user_id}/public-key", json={"public_key": public_key})

    def get_public_key(self, user_id: str) -> str:
        return self._request("GET", f"/users/{user_id}/public-key")["public_key"]

    # Rooms
    def get_rooms(self) -> list:
        return self._request("GET", "/rooms")

    def create_room(self, name: str, description: str = "", is_private: bool = False) -> dict:
        return self._request("POST", "/rooms", json={
            "name": name, "description": description, "is_private": is_private
        })

    def join_room(self, room_id: str):
        self._request("POST", f"/rooms/{room_id}/join")

    def open_dm(self, user_id: str) -> dict:
        return self._request("POST", f"/dm/{user_id}")

    # Messages
    def get_messages(self, room_id: str, limit: int = 50) -> list:
        return self._request("GET", f"/rooms/{room_id}/messages", params={"limit": limit})

    def health(self) -> dict:
        return self._request("GET", "/health")


class APIError(Exception):
    pass


class SecureChatWS:
    """WebSocket клиент для real-time сообщений"""

    def __init__(self, base_url: str, token: str, room_id: str,
                 on_message: Callable, on_error: Callable = None,
                 on_close: Callable = None):
        self.token = token
        self.room_id = room_id
        self.on_message_cb = on_message
        self.on_error_cb = on_error or (lambda e: print(f"WS Error: {e}"))
        self.on_close_cb = on_close or (lambda: None)

        ws_url = base_url.replace("https://", "wss://").replace("http://", "ws://")
        self.ws_url = f"{ws_url}/ws/{room_id}"
        self.ws: Optional[websocket.WebSocketApp] = None
        self._thread: Optional[threading.Thread] = None
        self._connected = False
        self._reconnect = True
        self._reconnect_delay = 2

    def connect(self):
        self._reconnect = True
        self._start()

    def _start(self):
        self.ws = websocket.WebSocketApp(
            self.ws_url,
            on_open=self._on_open,
            on_message=self._on_message,
            on_error=self._on_error,
            on_close=self._on_close,
        )
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def _run(self):
        while self._reconnect:
            try:
                self.ws.run_forever(ping_interval=30, ping_timeout=10)
            except Exception as e:
                self.on_error_cb(str(e))
            if self._reconnect:
                time.sleep(self._reconnect_delay)
                self._reconnect_delay = min(self._reconnect_delay * 2, 30)

    def _on_open(self, ws):
        self._connected = True
        self._reconnect_delay = 2
        # Authenticate
        ws.send(json.dumps({"type": "auth", "token": self.token}))

    def _on_message(self, ws, raw):
        try:
            data = json.loads(raw)
            self.on_message_cb(data)
        except Exception as e:
            print(f"Parse error: {e}")

    def _on_error(self, ws, error):
        self._connected = False
        self.on_error_cb(str(error))

    def _on_close(self, ws, code, msg):
        self._connected = False
        self.on_close_cb()

    def send_message(self, content: str, encrypted: bool = False):
        if self.ws and self._connected:
            self.ws.send(json.dumps({
                "type": "message",
                "content": content,
                "encrypted": encrypted,
            }))

    def send_typing(self):
        if self.ws and self._connected:
            self.ws.send(json.dumps({"type": "typing"}))

    def disconnect(self):
        self._reconnect = False
        if self.ws:
            self.ws.close()
