
APP_VERSION = "1.0"

from flask import Flask, render_template, request, redirect, url_for, session, jsonify
import random
import string
import pyautogui as pg
import ctypes
import socket
import threading
import customtkinter as ctk
from PIL import Image, ImageTk
import qrcode
import time
import uuid
import os

# Global state - PERFECT session tracking
app_state = {
    'mode': 'single',
    'current_users': {},  # {session_token: client_ip}
    'current_password': None,
    'hide_qr_single': False,
    'allowed_session_token': None  # Single mode: only this token allowed
}

app = Flask(__name__, template_folder="templates")
app.secret_key = os.environ.get("SECRET_KEY", "dev_key")
app.config['PERMANENT_SESSION_LIFETIME'] = 60*60*24

@app.before_request
def mobile_only():
    ua = request.headers.get('User-Agent', '').lower()
    if not any(x in ua for x in ['mobile', 'android', 'iphone', 'ipad', 'tablet']):
        return '<h1 style="text-align:center;padding:100px;color:#fff;background:#17181D;">📱 Use Phone/Tablet Only</h1>', 403

def get_ip():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("10.255.255.255", 1))
        ip = s.getsockname()[0]
    except:
        ip = "127.0.0.1"
    finally:
        s.close()
    return ip.strip()


def generate_random_password(n=20):
    password = ""
    for i in range(n):
        password += random.choice(string.ascii_letters + string.digits)
    return password

def create_qr_image(url):
    qr = qrcode.QRCode(version=3, error_correction=qrcode.constants.ERROR_CORRECT_L, box_size=10, border=4)
    qr.add_data(url)
    qr.make(fit=True)
    return qr.make_image(fill_color="black", back_color="white")

def is_session_allowed():
    """Check if this session is allowed in current mode"""
    if app_state['mode'] == 'multi':
        return True
    token = session.get('session_token')
    allowed = app_state.get('allowed_session_token')
    return token == allowed

class HostUI(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title(f"Screen Remote - Host v{APP_VERSION}")
        self.geometry("500x700")
        self.resizable(False, False)
        self.mode_switch_var = ctk.BooleanVar(value=False)
        self.password_label_var = ctk.StringVar(value="Scan QR to login")
        self.setup_ui()
        self.update_qr()
        self.update_status()
    
    def setup_ui(self):
        # Title
        title = ctk.CTkLabel(self, text=f"🎮 Screen Remote Host v{APP_VERSION}", font=ctk.CTkFont(size=28, weight="bold"))
        title.pack(pady=20)
        
        # Mode switch
        mode_frame = ctk.CTkFrame(self, fg_color="transparent")
        mode_frame.pack(pady=10)
        ctk.CTkLabel(mode_frame, text="Mode:", font=ctk.CTkFont(size=16)).pack(side="left", padx=10)
        self.mode_switch = ctk.CTkSwitch(mode_frame, text="Multi-User", 
                                       variable=self.mode_switch_var,
                                       command=self.on_mode_switch,
                                       font=ctk.CTkFont(size=16))
        self.mode_switch.pack(side="left", padx=10)
        
        # Status
        self.status_label = ctk.CTkLabel(self, text="Single User Mode | 0 users", 
                                       font=ctk.CTkFont(size=14))
        self.status_label.pack(pady=10)
        
        # QR Frame
        self.qr_frame = ctk.CTkFrame(self)
        self.qr_frame.pack(pady=20, padx=40, fill="both", expand=True)
        self.qr_label = ctk.CTkLabel(self.qr_frame, text="")
        self.qr_label.pack(expand=True)
        self.password_label = ctk.CTkLabel(self.qr_frame, textvariable=self.password_label_var, 
                                         font=ctk.CTkFont(size=16))
        self.password_label.pack(pady=10)
        
        # Buttons
        btn_frame = ctk.CTkFrame(self, fg_color="transparent")
        btn_frame.pack(pady=20)
        self.regenerate_btn = ctk.CTkButton(btn_frame, text="🔄 Regenerate QR", 
                                          command=self.regenerate_qr,
                                          font=ctk.CTkFont(size=16), height=40)
        self.regenerate_btn.pack(pady=5)
    
    def on_mode_switch(self):
        global app_state
        old_mode = app_state['mode']
        app_state['mode'] = 'multi' if self.mode_switch_var.get() else 'single'
        print(f"🔄 Mode: {old_mode} → {app_state['mode']}")
        
        if app_state['mode'] == 'single' and old_mode == 'multi':
            # Multi → Single: Keep FIRST user only
            if app_state['current_users']:
                first_token = next(iter(app_state['current_users']))
                app_state['current_users'] = {first_token: app_state['current_users'][first_token]}
                app_state['allowed_session_token'] = first_token
                print(f"✅ Single mode: Keeping {first_token}")
            else:
                app_state['allowed_session_token'] = None
                
        elif app_state['mode'] == 'multi' and old_mode == 'single':
            # Single → Multi: Allow everyone, show QR
            app_state['allowed_session_token'] = None
            app_state['hide_qr_single'] = False
            self.update_qr()
            print("✅ Multi mode: All users allowed, QR refreshed")
        
        self.update_status()
    
    def regenerate_qr(self):
        global app_state
        print("🔄 Regenerating QR...")
        app_state['current_users'].clear()
        app_state['allowed_session_token'] = None
        app_state['hide_qr_single'] = False
        self.update_qr()
    
    def update_qr(self):
        global app_state
        app_state['current_password'] = generate_random_password()
        url = f"http://{get_ip()}:5000/login?password={app_state['current_password']}"
        self.password_label_var.set("📱 Scan QR to login")
        
        qr_img = create_qr_image(url)
        self.tk_img = ImageTk.PhotoImage(qr_img)
        self.qr_label.configure(image=self.tk_img)
        print("✅ QR Updated")
    
    def update_status(self):
        global app_state
        user_count = len(app_state['current_users'])
        mode_text = "Multi-User" if app_state['mode'] == 'multi' else "Single-User"
        self.status_label.configure(text=f"{mode_text} Mode | {user_count} users")
        
        # Button states
        if app_state['mode'] == 'multi':
            self.regenerate_btn.configure(state="disabled")
        else:
            self.regenerate_btn.configure(state="normal")
        
        # QR visibility
        show_qr = (app_state['mode'] == 'multi') or (app_state['mode'] == 'single' and not app_state['hide_qr_single'])
        if show_qr:
            self.password_label_var.set("📱 Scan QR to login")
        else:
            self.qr_label.configure(image="")
            self.password_label_var.set("✅ 1 user connected")
        
        self.after(1000, self.update_status)

def get_foreground_window():
    window = ctypes.create_string_buffer(250)
    window_handle = ctypes.windll.user32.GetForegroundWindow()
    ctypes.windll.user32.GetWindowTextA(window_handle, window, 250)
    return window.value.decode('utf-8').lower()

def change_is_vlc():
    return 'vlc media player' in get_foreground_window()

@app.route('/')
def index():
    if not session.get('logged_in') or not is_session_allowed():
        session.clear()  # FORCE logout invalid sessions
        return redirect(url_for('login'))
    return render_template('controller.html', is_vlc=change_is_vlc())

@app.route('/login', methods=['GET', 'POST'])
def login():
    global app_state
    
    if request.method == 'GET':
        url_password = request.args.get('password')
        if url_password == app_state['current_password']:
            client_ip = request.remote_addr or get_ip()
            session_token = str(uuid.uuid4())  # Unique token per login
            
            # Single mode: Block if someone else is connected
            if app_state['mode'] == 'single' and app_state['allowed_session_token'] and len(app_state['current_users']) >= 1:
                return "❌ Single user mode - disconnect other device first", 403
            
            # Login success
            session['logged_in'] = True
            session['session_token'] = session_token
            session.permanent = True
            app_state['current_users'][session_token] = client_ip
            
            # Single mode: This becomes the allowed user
            if app_state['mode'] == 'single':
                app_state['allowed_session_token'] = session_token
                app_state['hide_qr_single'] = True
            
            print(f"✅ LOGIN: {client_ip} (Token: {session_token[:8]}) | Total: {len(app_state['current_users'])}")
            return redirect(url_for('index'))
    
    return render_template('login.html')

@app.route('/command', methods=['POST'])
def command():
    if not session.get('logged_in') or not is_session_allowed():
        session.clear()  # FORCE logout
        return '', 401
    
    data = request.get_json()
    command = data.get('command')
    value = data.get('value')
    token = session.get('session_token', 'unknown')[:8]
    print(f"🎮 {command} from {token} ({request.remote_addr})")
    
    # PyAutoGUI Commands
    print(command)
    if command == 'playpause': pg.hotkey('playpause')
    elif command == 'mute':
        if value:
            pg.press('volumemute')
        else:
            pg.hotkey('volumeup')
            pg.hotkey('volumedown')
    elif command == 'volume_up': pg.hotkey('volumeup')
    elif command == 'close_tab': pg.hotkey('ctrl', 'w')
    elif command == 'volume_down': pg.hotkey('volumedown')
    elif command == 'fullscreen': pg.hotkey('f')
    elif command == 'forward': pg.hotkey('right')
    elif command == 'backward': pg.hotkey('left')
    elif command == 'reload': pg.hotkey('f5')
    elif command == 'escape': pg.hotkey('escape')
    elif command == 'audio_track': 
        if change_is_vlc():
            pg.hotkey('b')
    elif command == 'speed_minus': 
        if change_is_vlc():
            pg.hotkey('[')
        else:
            pg.hotkey('shift', '<')
    elif command == 'speed_plus':
        if change_is_vlc():
            pg.hotkey(']')
        else:
            pg.hotkey('shift', '>')
    elif command == 'subtitle':
        if change_is_vlc():
            pg.hotkey('v')
        else:
            pg.hotkey('c')
    elif command == 'center_click':
        width, height = pg.size()
        pg.moveTo(width // 2, height // 2)
        pg.click()
        pg.move(width // 2, 0)
    elif command == 'num' and not change_is_vlc():
        pg.hotkey(str(value))
    elif command == 'previous':
        if change_is_vlc():
            pg.hotkey('p')
        else:
            pg.hotkey('shift', 'p')
    elif command == 'next':
        if change_is_vlc():
            pg.hotkey('n')
        else:
            pg.hotkey('shift', 'n')

    return jsonify({'status': 'ok'})

def run_flask():
    app.run(host='0.0.0.0', port=5000, debug=False, use_reloader=False)

if __name__ == '__main__':
    app_state['current_password'] = generate_random_password()
    print(f"🚀 Screen Remote - QR Desktop Media Controller v{APP_VERSION}")
    print(f"🌐 Web: http://{get_ip()}:5000")
    print("📱 Scan QR from Host window to login")
    print("-" * 50)
    
    # Start Flask server
    flask_thread = threading.Thread(target=run_flask, daemon=True)
    flask_thread.start()
    time.sleep(1.5)
    
    # Start Host UI
    host_ui = HostUI()
    host_ui.mainloop()