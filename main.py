import sqlite3
import threading
import time
from datetime import datetime

from kivy.app import App
from kivy.clock import Clock
from kivy.core.window import Window
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.label import Label
from kivy.uix.textinput import TextInput
from kivy.uix.spinner import Spinner
from kivy.uix.scrollview import ScrollView
from kivy.uix.screenmanager import ScreenManager, Screen

try:
    from jnius import autoclass
    from android.permissions import request_permissions, Permission
    ON_ANDROID = True
except ImportError:
    ON_ANDROID = False


DB_NAME = "resqmesh.db"
APP_UUID_STRING = "8ce255c0-200a-11e0-ac64-0800200c9a66"
MAX_SEND_RETRIES = 3
RETRY_DELAY_SECONDS = 2

# ---- Theme (matches the app icon) ----
TEAL_DARK = (0.051, 0.369, 0.349, 1)
TEAL = (0.043, 0.42, 0.40, 1)
RED_ORANGE = (0.886, 0.298, 0.2, 1)
GRAY_BLUE = (0.38, 0.44, 0.49, 1)
LIGHT_BG = (0.95, 0.96, 0.97, 1)
DARK_TEXT = (0.12, 0.15, 0.18, 1)
WHITE = (1, 1, 1, 1)


def styled_button(text, bg=TEAL, fg=WHITE, **kwargs):
    return Button(
        text=text,
        background_normal="",
        background_down="",
        background_color=bg,
        color=fg,
        **kwargs
    )


def scroll_wrap(screen, spacing=12, padding=20):
    """Creates a ScrollView + inner top-anchored BoxLayout, attaches it to
    the screen, and returns the inner layout to add widgets into."""
    scroll = ScrollView(size_hint=(1, 1), do_scroll_x=False)
    content = BoxLayout(orientation="vertical", size_hint_y=None, spacing=spacing, padding=padding)
    content.bind(minimum_height=content.setter("height"))
    scroll.add_widget(content)
    screen.add_widget(scroll)
    return content


def init_db():
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS sos_messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            emergency_type TEXT,
            message TEXT,
            location TEXT,
            timestamp TEXT,
            status TEXT DEFAULT 'stored'
        )
    """)
    conn.commit()
    conn.close()


def save_sos(emergency_type, message, location):
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO sos_messages (emergency_type, message, location, timestamp) VALUES (?, ?, ?, ?)",
        (emergency_type, message, location, datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    )
    conn.commit()
    conn.close()


def get_all_sos():
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute("SELECT emergency_type, message, location, timestamp, status FROM sos_messages ORDER BY id DESC")
    rows = cur.fetchall()
    conn.close()
    return rows


def get_pending_sos():
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute("""
        SELECT id, emergency_type, message, location, timestamp, status
        FROM sos_messages WHERE status != 'delivered'
        ORDER BY id DESC
    """)
    rows = cur.fetchall()
    conn.close()
    return rows


def get_stored_only_sos():
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute("""
        SELECT id, emergency_type, message, location, timestamp
        FROM sos_messages WHERE status = 'stored'
        ORDER BY id ASC
    """)
    rows = cur.fetchall()
    conn.close()
    return rows


def update_status(sos_id, new_status):
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute("UPDATE sos_messages SET status = ? WHERE id = ?", (new_status, sos_id))
    conn.commit()
    conn.close()


class MenuScreen(Screen):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        layout = scroll_wrap(self)

        layout.add_widget(Label(
            text="ResQMesh\nOffline Disaster Communication",
            font_size=24,
            halign="center",
            color=DARK_TEXT,
            size_hint_y=None,
            height=90
        ))

        btn_sos = styled_button("Send SOS", bg=RED_ORANGE, font_size=20, size_hint_y=None, height=54)
        btn_sos.bind(on_press=self.go_to_sos)
        layout.add_widget(btn_sos)

        btn_view = styled_button("My SOS Messages", font_size=20, size_hint_y=None, height=54)
        btn_view.bind(on_press=self.go_to_messages)
        layout.add_widget(btn_view)

        btn_volunteer = styled_button("Volunteer: Relay Messages", font_size=20, size_hint_y=None, height=54)
        btn_volunteer.bind(on_press=self.go_to_volunteer)
        layout.add_widget(btn_volunteer)

        btn_bt_test = styled_button("Check Bluetooth Status", bg=GRAY_BLUE, font_size=20, size_hint_y=None, height=54)
        btn_bt_test.bind(on_press=self.go_to_bt_test)
        layout.add_widget(btn_bt_test)

        btn_bt_scan = styled_button("Find Nearby Phones", bg=GRAY_BLUE, font_size=20, size_hint_y=None, height=54)
        btn_bt_scan.bind(on_press=self.go_to_bt_scan)
        layout.add_widget(btn_bt_scan)

        btn_bt_transfer = styled_button("Send / Receive via Bluetooth", font_size=20, size_hint_y=None, height=54)
        btn_bt_transfer.bind(on_press=self.go_to_bt_transfer)
        layout.add_widget(btn_bt_transfer)

        btn_exit = styled_button("Exit App", bg=GRAY_BLUE, font_size=20, size_hint_y=None, height=54)
        btn_exit.bind(on_press=lambda x: App.get_running_app().stop())
        layout.add_widget(btn_exit)

    def go_to_sos(self, instance):
        self.manager.current = "sos"

    def go_to_messages(self, instance):
        self.manager.get_screen("messages").refresh()
        self.manager.current = "messages"

    def go_to_volunteer(self, instance):
        self.manager.get_screen("volunteer").refresh()
        self.manager.current = "volunteer"

    def go_to_bt_test(self, instance):
        self.manager.current = "bt_test"

    def go_to_bt_scan(self, instance):
        self.manager.current = "bt_scan"

    def go_to_bt_transfer(self, instance):
        self.manager.current = "bt_transfer"


class SOSScreen(Screen):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.layout = scroll_wrap(self)

        self.layout.add_widget(Label(
            text="Send SOS",
            font_size=22,
            size_hint_y=None,
            height=40,
            color=DARK_TEXT
        ))

        self.layout.add_widget(Label(text="Emergency Type", size_hint_y=None, height=25, color=DARK_TEXT))
        self.emergency_type = Spinner(
            text="Medical",
            values=("Medical", "Flood", "Fire", "Building Collapse", "Other"),
            size_hint_y=None,
            height=44
        )
        self.layout.add_widget(self.emergency_type)

        self.layout.add_widget(Label(text="Message", size_hint_y=None, height=25, color=DARK_TEXT))
        self.message_input = TextInput(multiline=True, size_hint_y=None, height=100)
        self.layout.add_widget(self.message_input)

        self.layout.add_widget(Label(text="Location", size_hint_y=None, height=25, color=DARK_TEXT))
        self.location_input = TextInput(
            multiline=False,
            hint_text="e.g. Near XYZ bridge",
            size_hint_y=None,
            height=44
        )
        self.layout.add_widget(self.location_input)

        self.status_label = Label(text="", size_hint_y=None, height=30, color=DARK_TEXT)
        self.layout.add_widget(self.status_label)

        btn_row = BoxLayout(size_hint_y=None, height=54, spacing=10)

        btn_save = styled_button("Save SOS Message", bg=RED_ORANGE)
        btn_save.bind(on_press=self.save_and_return)
        btn_row.add_widget(btn_save)

        btn_back = styled_button("Cancel", bg=GRAY_BLUE)
        btn_back.bind(on_press=self.go_back)
        btn_row.add_widget(btn_back)

        self.layout.add_widget(btn_row)

    def save_and_return(self, instance):
        etype = self.emergency_type.text
        message = self.message_input.text.strip()
        location = self.location_input.text.strip()

        if not message or not location:
            self.status_label.text = "Please fill in message and location."
            return

        save_sos(etype, message, location)

        self.message_input.text = ""
        self.location_input.text = ""
        self.status_label.text = "SOS saved locally."

    def go_back(self, instance):
        self.status_label.text = ""
        self.manager.current = "menu"


class MessagesScreen(Screen):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.layout = scroll_wrap(self)

    def refresh(self):
        self.layout.clear_widgets()
        self.layout.add_widget(Label(
            text="My SOS Messages",
            font_size=22,
            size_hint_y=None,
            height=40,
            color=DARK_TEXT
        ))

        rows = get_all_sos()

        if not rows:
            self.layout.add_widget(Label(text="No messages stored yet.", size_hint_y=None, height=40, color=DARK_TEXT))
        else:
            for etype, message, location, timestamp, status in rows:
                text = f"[{timestamp}] {etype} @ {location}\n{message}\nStatus: {status}"
                self.layout.add_widget(Label(
                    text=text, size_hint_y=None, height=90, color=DARK_TEXT,
                    halign="left", valign="top"
                ))

        btn_back = styled_button("Back to Menu", bg=GRAY_BLUE, size_hint_y=None, height=54)
        btn_back.bind(on_press=self.go_back)
        self.layout.add_widget(btn_back)

    def go_back(self, instance):
        self.manager.current = "menu"


class VolunteerScreen(Screen):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.layout = scroll_wrap(self)

    def refresh(self):
        self.layout.clear_widgets()
        self.layout.add_widget(Label(
            text="Volunteer: Relay Messages\nPending SOS messages to relay",
            font_size=22,
            size_hint_y=None,
            height=60,
            halign="center",
            color=DARK_TEXT
        ))

        rows = get_pending_sos()

        if not rows:
            self.layout.add_widget(Label(text="No pending SOS messages.", size_hint_y=None, height=40, color=DARK_TEXT))
        else:
            for sos_id, etype, message, location, timestamp, status in rows:
                row = BoxLayout(size_hint_y=None, height=90, spacing=10)

                info = Label(
                    text=f"[{timestamp}] {etype} @ {location}\n{message}\nStatus: {status}",
                    halign="left",
                    color=DARK_TEXT
                )
                row.add_widget(info)

                if status == "stored":
                    btn = styled_button("Mark Forwarded", bg=TEAL, size_hint_x=0.4)
                    btn.bind(on_press=lambda x, sid=sos_id: self.mark_forwarded(sid))
                elif status == "forwarded":
                    btn = styled_button("Mark Delivered", bg=TEAL_DARK, size_hint_x=0.4)
                    btn.bind(on_press=lambda x, sid=sos_id: self.mark_delivered(sid))
                else:
                    btn = Label(text="", size_hint_x=0.4)

                row.add_widget(btn)
                self.layout.add_widget(row)

        btn_back = styled_button("Back to Menu", bg=GRAY_BLUE, size_hint_y=None, height=54)
        btn_back.bind(on_press=self.go_back)
        self.layout.add_widget(btn_back)

    def mark_forwarded(self, sos_id):
        update_status(sos_id, "forwarded")
        self.refresh()

    def mark_delivered(self, sos_id):
        update_status(sos_id, "delivered")
        self.refresh()

    def go_back(self, instance):
        self.manager.current = "menu"


class BluetoothTestScreen(Screen):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.layout = scroll_wrap(self)

    def on_enter(self):
        self.run_test()

    def run_test(self):
        self.layout.clear_widgets()
        self.layout.add_widget(Label(
            text="Check Bluetooth Status",
            font_size=22,
            size_hint_y=None,
            height=40,
            color=DARK_TEXT
        ))

        result_label = Label(text="Checking...", halign="left", valign="top", color=DARK_TEXT,
                              size_hint_y=None, height=200)
        result_label.bind(size=result_label.setter("text_size"))
        self.layout.add_widget(result_label)

        if not ON_ANDROID:
            result_label.text = "Bluetooth test only works on Android (not on desktop)."
        else:
            try:
                BluetoothAdapter = autoclass('android.bluetooth.BluetoothAdapter')
                adapter = BluetoothAdapter.getDefaultAdapter()

                if adapter is None:
                    result_label.text = "This device does not support Bluetooth."
                else:
                    enabled = adapter.isEnabled()
                    lines = [f"Bluetooth adapter found.", f"Enabled: {enabled}", ""]

                    if enabled:
                        paired = adapter.getBondedDevices().toArray()
                        lines.append(f"Paired devices: {len(paired)}")
                        for device in paired:
                            name = device.getName()
                            address = device.getAddress()
                            lines.append(f"  - {name} ({address})")
                    else:
                        lines.append("Turn on Bluetooth in Android settings and reopen this screen.")

                    result_label.text = "\n".join(lines)

            except Exception as e:
                result_label.text = f"Error: {e}"

        btn_back = styled_button("Back to Menu", bg=GRAY_BLUE, size_hint_y=None, height=54)
        btn_back.bind(on_press=self.go_back)
        self.layout.add_widget(btn_back)

    def go_back(self, instance):
        self.manager.current = "menu"


class BluetoothScanScreen(Screen):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.layout = scroll_wrap(self)
        self.receiver = None
        self.finish_receiver = None
        self.found_devices = {}
        self.result_label = None
        self.adapter = None

    def on_enter(self):
        self.start_scan()

    def on_leave(self):
        self.stop_scan()

    def start_scan(self):
        self.layout.clear_widgets()
        self.layout.add_widget(Label(
            text="Find Nearby Phones",
            font_size=22,
            size_hint_y=None,
            height=40,
            color=DARK_TEXT
        ))

        self.result_label = Label(text="Starting scan...", halign="left", valign="top", color=DARK_TEXT,
                                   size_hint_y=None, height=200)
        self.result_label.bind(size=self.result_label.setter("text_size"))
        self.layout.add_widget(self.result_label)

        btn_back = styled_button("Stop Scan & Back", bg=GRAY_BLUE, size_hint_y=None, height=54)
        btn_back.bind(on_press=self.go_back)
        self.layout.add_widget(btn_back)

        if not ON_ANDROID:
            self.result_label.text = "Scanning only works on Android."
            return

        try:
            from android.broadcast import BroadcastReceiver
            BluetoothAdapter = autoclass('android.bluetooth.BluetoothAdapter')
            self.adapter = BluetoothAdapter.getDefaultAdapter()

            if self.adapter is None:
                self.result_label.text = "No Bluetooth adapter found."
                return

            self.found_devices = {}

            self.receiver = BroadcastReceiver(
                self.on_device_found,
                actions=["android.bluetooth.device.action.FOUND"]
            )
            self.receiver.start()

            self.finish_receiver = BroadcastReceiver(
                self.on_discovery_finished,
                actions=["android.bluetooth.adapter.action.DISCOVERY_FINISHED"]
            )
            self.finish_receiver.start()

            if self.adapter.isDiscovering():
                self.adapter.cancelDiscovery()
            started = self.adapter.startDiscovery()

            if started:
                self.result_label.text = "Scanning... (this runs for about 12 seconds)"
            else:
                self.result_label.text = (
                    "startDiscovery() returned False.\n"
                    "This usually means a permission was denied.\n"
                    "Check Android Settings > Apps > ResQMesh > Permissions,\n"
                    "and make sure Nearby Devices / Location is allowed."
                )

        except Exception as e:
            self.result_label.text = f"Error starting scan: {e}"

    def on_device_found(self, context, intent):
        BluetoothDevice = autoclass('android.bluetooth.BluetoothDevice')
        device = intent.getParcelableExtra(BluetoothDevice.EXTRA_DEVICE)
        name = device.getName()
        address = device.getAddress()

        if address not in self.found_devices:
            self.found_devices[address] = name or "Unknown device"
            self.refresh_list()

    def on_discovery_finished(self, context, intent):
        lines = [f"Scan complete. Found {len(self.found_devices)} device(s):", ""]
        for address, name in self.found_devices.items():
            lines.append(f"  - {name} ({address})")
        if not self.found_devices:
            lines.append("(none found nearby)")
        self.result_label.text = "\n".join(lines)

    def refresh_list(self):
        lines = [f"Found {len(self.found_devices)} device(s) so far:", ""]
        for address, name in self.found_devices.items():
            lines.append(f"  - {name} ({address})")
        self.result_label.text = "\n".join(lines)

    def stop_scan(self):
        if ON_ANDROID:
            try:
                if self.adapter and self.adapter.isDiscovering():
                    self.adapter.cancelDiscovery()
                if self.receiver:
                    self.receiver.stop()
                    self.receiver = None
                if self.finish_receiver:
                    self.finish_receiver.stop()
                    self.finish_receiver = None
            except Exception:
                pass

    def go_back(self, instance):
        self.stop_scan()
        self.manager.current = "menu"


class BluetoothTransferScreen(Screen):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.layout = scroll_wrap(self)
        self.status_label = None
        self.server_thread = None
        self.listening = False

    def on_enter(self):
        self.build_ui()

    def on_leave(self):
        self.listening = False

    def build_ui(self):
        self.layout.clear_widgets()
        self.layout.add_widget(Label(
            text="Send / Receive via Bluetooth",
            font_size=22,
            size_hint_y=None,
            height=40,
            color=DARK_TEXT
        ))

        btn_listen = styled_button("Start Listening for Messages", size_hint_y=None, height=54)
        btn_listen.bind(on_press=self.start_listening)
        self.layout.add_widget(btn_listen)

        self.layout.add_widget(Label(
            text="Send all stored SOS messages to a paired phone:",
            size_hint_y=None,
            height=30,
            color=DARK_TEXT
        ))

        if ON_ANDROID:
            try:
                BluetoothAdapter = autoclass('android.bluetooth.BluetoothAdapter')
                adapter = BluetoothAdapter.getDefaultAdapter()
                paired = adapter.getBondedDevices().toArray() if adapter else []

                if not paired:
                    self.layout.add_widget(Label(text="No paired devices found.", size_hint_y=None, height=40, color=DARK_TEXT))
                else:
                    for device in paired:
                        name = device.getName() or "Unknown"
                        row = BoxLayout(size_hint_y=None, height=54, spacing=10)
                        row.add_widget(Label(text=name, color=DARK_TEXT))
                        btn_send = styled_button("Send All Stored", bg=RED_ORANGE, size_hint_x=0.5)
                        btn_send.bind(on_press=lambda x, d=device: self.send_to_device(d))
                        row.add_widget(btn_send)
                        self.layout.add_widget(row)
            except Exception as e:
                self.layout.add_widget(Label(text=f"Error listing devices: {e}", size_hint_y=None, height=40, color=DARK_TEXT))
        else:
            self.layout.add_widget(Label(text="Only works on Android.", size_hint_y=None, height=40, color=DARK_TEXT))

        self.status_label = Label(text="", halign="left", valign="top", color=DARK_TEXT,
                                   size_hint_y=None, height=140)
        self.status_label.bind(size=self.status_label.setter("text_size"))
        self.layout.add_widget(self.status_label)

        btn_back = styled_button("Back to Menu", bg=GRAY_BLUE, size_hint_y=None, height=54)
        btn_back.bind(on_press=self.go_back)
        self.layout.add_widget(btn_back)

    def set_status(self, text):
        Clock.schedule_once(lambda dt: setattr(self.status_label, "text", text))

    def start_listening(self, instance):
        if self.listening:
            self.set_status("Already listening.")
            return

        if not ON_ANDROID:
            self.set_status("Listening only works on Android.")
            return

        self.listening = True
        self.set_status("Listening for incoming connection...")

        def server_loop():
            try:
                UUID = autoclass('java.util.UUID')
                BluetoothAdapter = autoclass('android.bluetooth.BluetoothAdapter')
                adapter = BluetoothAdapter.getDefaultAdapter()
                app_uuid = UUID.fromString(APP_UUID_STRING)

                server_socket = adapter.listenUsingInsecureRfcommWithServiceRecord("ResQMesh", app_uuid)
                self.set_status("Waiting for a device to connect...")

                socket = server_socket.accept()
                self.set_status("Connected. Receiving data...")

                BufferedReader = autoclass('java.io.BufferedReader')
                InputStreamReader = autoclass('java.io.InputStreamReader')
                reader = BufferedReader(InputStreamReader(socket.getInputStream()))

                received_count = 0
                while True:
                    line = reader.readLine()
                    if line is None:
                        break

                    parts = line.split("|", 3)
                    if len(parts) == 4:
                        etype, message, location, timestamp = parts
                        save_sos(etype, f"{message} (received via Bluetooth)", location)
                        received_count += 1
                        self.set_status(f"Receiving... {received_count} message(s) so far")
                    else:
                        self.set_status(f"Received malformed line, skipping: {line}")

                socket.close()
                server_socket.close()

                if received_count > 0:
                    self.set_status(f"Done. Received {received_count} message(s) total.")
                else:
                    self.set_status("Connection closed with no messages received.")

            except Exception as e:
                self.set_status(f"Listening error: {e}")
            finally:
                self.listening = False

        self.server_thread = threading.Thread(target=server_loop, daemon=True)
        self.server_thread.start()

    def send_to_device(self, device):
        stored = get_stored_only_sos()
        if not stored:
            self.set_status("No stored SOS messages to send.")
            return

        self.set_status(f"Connecting to {device.getName()}...")

        def client_thread():
            attempt = 0
            last_error = None

            while attempt < MAX_SEND_RETRIES:
                attempt += 1
                try:
                    UUID = autoclass('java.util.UUID')
                    BluetoothAdapter = autoclass('android.bluetooth.BluetoothAdapter')
                    app_uuid = UUID.fromString(APP_UUID_STRING)

                    BluetoothAdapter.getDefaultAdapter().cancelDiscovery()

                    if attempt > 1:
                        self.set_status(f"Retry attempt {attempt}/{MAX_SEND_RETRIES}...")

                    socket = device.createInsecureRfcommSocketToServiceRecord(app_uuid)
                    socket.connect()

                    output_stream = socket.getOutputStream()
                    sent_ids = []

                    for sos_id, etype, message, location, timestamp in stored:
                        payload = f"{etype}|{message}|{location}|{timestamp}\n"
                        output_stream.write(payload.encode("utf-8"))
                        output_stream.flush()
                        sent_ids.append(sos_id)

                    socket.close()

                    for sos_id in sent_ids:
                        update_status(sos_id, "forwarded")

                    self.set_status(
                        f"Sent {len(sent_ids)} message(s) successfully"
                        + (f" (attempt {attempt})" if attempt > 1 else "") + "."
                    )
                    return

                except Exception as e:
                    last_error = e
                    if attempt < MAX_SEND_RETRIES:
                        self.set_status(
                            f"Attempt {attempt}/{MAX_SEND_RETRIES} failed: {e}\n"
                            f"Retrying in {RETRY_DELAY_SECONDS}s..."
                        )
                        time.sleep(RETRY_DELAY_SECONDS)
                    else:
                        self.set_status(
                            f"All {MAX_SEND_RETRIES} attempts failed.\n"
                            f"Last error: {last_error}\n"
                            "Make sure the other device is on the Bluetooth screen "
                            "with 'Start Listening' active."
                        )

        threading.Thread(target=client_thread, daemon=True).start()

    def go_back(self, instance):
        self.listening = False
        self.manager.current = "menu"


class ResQMeshApp(App):
    def build(self):
        self.title = "ResQMesh"
        Window.clearcolor = LIGHT_BG

        if ON_ANDROID:
            request_permissions([
                Permission.BLUETOOTH,
                Permission.BLUETOOTH_ADMIN,
                Permission.BLUETOOTH_CONNECT,
                Permission.BLUETOOTH_SCAN,
                Permission.ACCESS_FINE_LOCATION,
            ])

        init_db()

        sm = ScreenManager()
        sm.add_widget(MenuScreen(name="menu"))
        sm.add_widget(SOSScreen(name="sos"))
        sm.add_widget(MessagesScreen(name="messages"))
        sm.add_widget(VolunteerScreen(name="volunteer"))
        sm.add_widget(BluetoothTestScreen(name="bt_test"))
        sm.add_widget(BluetoothScanScreen(name="bt_scan"))
        sm.add_widget(BluetoothTransferScreen(name="bt_transfer"))
        return sm


if __name__ == "__main__":
    ResQMeshApp().run()
