import os
import re
import sys
import time
import socket
import shutil
import signal
import atexit
import ctypes
import webbrowser
import subprocess
from urllib.parse import urlparse

import requests

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
TOOLS_DIR = os.path.join(BASE_DIR, "tools")
LOCAL_CLOUDFLARED = os.path.join(TOOLS_DIR, "cloudflared.exe")
CLOUDFLARED_URL = "https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-windows-amd64.exe"

STREAMLIT_EXE = os.path.join(BASE_DIR, "venv", "Scripts", "streamlit.exe")
STREAMLIT_PORT = 8501
LOCAL_APP_URL = f"http://127.0.0.1:{STREAMLIT_PORT}"
OLLAMA_URL = "http://localhost:11434"
TRYCLOUDFLARE_REGEX = re.compile(r"https://[a-zA-Z0-9-]+\.trycloudflare\.com")

_MANAGED_PROCS: list[tuple[str, subprocess.Popen]] = []
_CLEANED_UP = False

# Đảm bảo console Windows in tiếng Việt ổn định
for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, "reconfigure"):
        try:
            _stream.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass


def _kill_proc_tree(proc: subprocess.Popen) -> None:
    """Dừng sạch tiến trình và toàn bộ tiến trình con trên Windows."""
    if proc is None or proc.poll() is not None:
        return
    try:
        if os.name == "nt":
            subprocess.run(
                ["taskkill", "/F", "/T", "/PID", str(proc.pid)],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                check=False,
            )
        else:
            proc.terminate()
            proc.wait(timeout=5)
    except Exception:
        try:
            proc.kill()
        except Exception:
            pass


def cleanup_processes() -> None:
    """Giải phóng sạch cloudflared và streamlit khi đóng cửa sổ terminal hoặc nhấn Ctrl+C."""
    global _CLEANED_UP
    if _CLEANED_UP:
        return
    _CLEANED_UP = True
    print("\n[DỌN DẸP] Đang tắt Cloudflare Tunnel và Streamlit để giải phóng RAM...", flush=True)
    for name, proc in reversed(_MANAGED_PROCS):
        if proc.poll() is None:
            print(f"   -> Đang dừng {name} (PID {proc.pid})...", flush=True)
            _kill_proc_tree(proc)
    print("[DỌN DẸP] Hoàn tất! Đã giải phóng toàn bộ tiến trình.", flush=True)


def _register_windows_close_handler() -> None:
    """Đăng ký ConsoleCtrlHandler trên Windows để bắt sự kiện bấm nút X đóng cửa sổ CMD."""
    if os.name != "nt":
        return
    try:
        HANDLER_ROUTINE = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_uint)

        def _ctrl_handler(ctrl_type: int) -> bool:
            # 0=CTRL_C, 1=CTRL_BREAK, 2=CTRL_CLOSE (bấm X), 5=LOGOFF, 6=SHUTDOWN
            if ctrl_type in (0, 1, 2, 5, 6):
                cleanup_processes()
            return False

        # Giữ tham chiếu toàn cục để GC không thu hồi callback C
        global _WIN_CTRL_CALLBACK
        _WIN_CTRL_CALLBACK = HANDLER_ROUTINE(_ctrl_handler)
        ctypes.windll.kernel32.SetConsoleCtrlHandler(_WIN_CTRL_CALLBACK, True)
    except Exception:
        pass


def ensure_cloudflared() -> str:
    """Tìm cloudflared trong PATH hoặc tools/cloudflared.exe; tự tải bản chính thức nếu chưa có."""
    in_path = shutil.which("cloudflared")
    if in_path:
        print(f"[1/4] Đã tìm thấy cloudflared trong PATH: {in_path}", flush=True)
        return in_path

    if os.path.isfile(LOCAL_CLOUDFLARED) and os.path.getsize(LOCAL_CLOUDFLARED) > 1_000_000:
        print(f"[1/4] Đã sẵn sàng cloudflared cục bộ: {LOCAL_CLOUDFLARED}", flush=True)
        return LOCAL_CLOUDFLARED

    os.makedirs(TOOLS_DIR, exist_ok=True)
    part_path = LOCAL_CLOUDFLARED + ".part"
    print(f"[1/4] Chưa có cloudflared.exe -> Đang tải bản chính thức từ GitHub Cloudflare...", flush=True)
    print(f"      URL: {CLOUDFLARED_URL}", flush=True)

    with requests.get(CLOUDFLARED_URL, stream=True, timeout=120) as resp:
        resp.raise_for_status()
        total = int(resp.headers.get("content-length", 0))
        downloaded = 0
        with open(part_path, "wb") as f:
            for chunk in resp.iter_content(chunk_size=262_144):
                if chunk:
                    f.write(chunk)
                    downloaded += len(chunk)
                    if total > 0:
                        pct = int(downloaded * 100 / total)
                        print(f"\r      Đang tải: {downloaded / 1_048_576:.1f}/{total / 1_048_576:.1f} MB ({pct}%)", end="", flush=True)
    print("", flush=True)
    os.replace(part_path, LOCAL_CLOUDFLARED)
    print(f"      ✅ Đã lưu cloudflared.exe tại: {LOCAL_CLOUDFLARED}", flush=True)
    return LOCAL_CLOUDFLARED


def _is_ollama_ready() -> bool:
    try:
        r = requests.get(f"{OLLAMA_URL}/api/tags", timeout=2.5)
        return r.status_code == 200
    except Exception:
        return False


def ensure_ollama_running() -> None:
    """Kiểm tra Ollama localhost:11434; nếu chưa chạy thì tự khởi động ngầm `ollama serve`."""
    if _is_ollama_ready():
        print(f"[2/4] Ollama đang hoạt động bình thường tại {OLLAMA_URL}", flush=True)
        return

    print(f"[2/4] Ollama chưa chạy -> Đang khởi động ngầm 'ollama serve'...", flush=True)
    creation_flags = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
    try:
        subprocess.Popen(
            ["ollama", "serve"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            creationflags=creation_flags,
        )
    except FileNotFoundError:
        print("      ⚠️ Không tìm thấy lệnh 'ollama' trong PATH. Hãy mở ứng dụng Ollama trước!", flush=True)
        return

    for sec in range(1, 21):
        if _is_ollama_ready():
            print(f"      ✅ Ollama đã sẵn sàng sau {sec}s!", flush=True)
            return
        time.sleep(1.0)
    print("      ⚠️ Ollama phản hồi chậm hơn 20s, tiếp tục khởi chạy giao diện Web...", flush=True)


def _is_streamlit_ready() -> bool:
    try:
        r = requests.get(f"{LOCAL_APP_URL}/_stcore/health", timeout=2.0)
        return r.status_code == 200
    except Exception:
        return False


def start_streamlit() -> subprocess.Popen | None:
    """Khởi chạy Streamlit trên cổng 8501 với cấu hình sẵn sàng cho Cloudflare Tunnel."""
    if _is_streamlit_ready():
        print(f"[3/4] Streamlit đã sẵn sàng tại {LOCAL_APP_URL} (dùng phiên hiện tại).", flush=True)
        return None

    if not os.path.isfile(STREAMLIT_EXE):
        raise FileNotFoundError(f"Không tìm thấy Streamlit tại: {STREAMLIT_EXE}")

    cmd = [
        STREAMLIT_EXE,
        "run",
        "app_ui.py",
        "--server.address",
        "0.0.0.0",
        "--server.port",
        str(STREAMLIT_PORT),
        "--server.headless",
        "true",
        "--server.enableXsrfProtection",
        "false",
        "--server.enableCORS",
        "false",
        "--browser.gatherUsageStats",
        "false",
    ]
    print(f"[3/4] Đang khởi chạy Streamlit Web UI tại {LOCAL_APP_URL}...", flush=True)
    creation_flags = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
    child_env = os.environ.copy()
    child_env["PYTHONUTF8"] = "1"
    child_env["PYTHONIOENCODING"] = "utf-8"
    proc = subprocess.Popen(
        cmd,
        cwd=BASE_DIR,
        env=child_env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        creationflags=creation_flags,
    )
    _MANAGED_PROCS.append(("Streamlit", proc))

    for sec in range(1, 31):
        if proc.poll() is not None:
            raise RuntimeError(f"Streamlit thoát sớm với mã lỗi {proc.returncode}.")
        if _is_streamlit_ready():
            print(f"      ✅ Streamlit đã khởi động thành công sau {sec}s!", flush=True)
            return proc
        time.sleep(1.0)

    print("      ⚠️ Đã quá 30s chờ healthcheck Streamlit, vẫn tiếp tục mở Tunnel...", flush=True)
    return proc


def copy_to_clipboard_windows(text: str) -> bool:
    """Copy đường dẫn công khai vào Clipboard Windows bằng lệnh clip."""
    try:
        subprocess.run(["clip"], input=text.encode("utf-8"), check=True)
        return True
    except Exception as e:
        print(f"      ⚠️ Không thể copy tự động vào Clipboard: {e}", flush=True)
        return False


def _get_lan_ip() -> str:
    """Lấy địa chỉ IP LAN của máy tính để chia sẻ nhanh trong cùng mạng Wi-Fi."""
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.connect(("1.1.1.1", 80))
            return s.getsockname()[0]
    except Exception:
        return ""


def _doh_has_a_record(doh_url: str, hostname: str) -> bool:
    """Kiểm tra bản ghi DNS qua DoH (1.1.1.1 / 8.8.8.8) để KHÔNG làm router Wi-Fi cache NXDOMAIN sớm."""
    try:
        r = requests.get(
            doh_url,
            params={"name": hostname, "type": "A"},
            headers={"Accept": "application/dns-json"},
            timeout=3.0,
        )
        if r.status_code != 200:
            return False
        data = r.json()
        return data.get("Status") == 0 and bool(data.get("Answer"))
    except Exception:
        return False


def _wait_for_public_dns_ready(public_url: str, max_wait: int = 25) -> bool:
    """Chờ Cloudflare (1.1.1.1) và Google (8.8.8.8) đồng bộ xong bản ghi DNS trước khi công bố link."""
    hostname = urlparse(public_url).hostname or ""
    if not hostname:
        return False
    print("      ⏳ Đang chờ DNS toàn cầu (1.1.1.1 & 8.8.8.8) đồng bộ tên miền mới...", flush=True)
    for sec in range(1, max_wait + 1):
        cf_ok = _doh_has_a_record("https://1.1.1.1/dns-query", hostname)
        gg_ok = _doh_has_a_record("https://dns.google/resolve", hostname)
        if cf_ok and gg_ok:
            # Chờ thêm 2s để các DNS nhà mạng VN đồng bộ theo, tránh router cache lỗi NXDOMAIN
            time.sleep(2.0)
            print(f"      ✅ DNS toàn cầu đã đồng bộ thành công sau {sec}s!", flush=True)
            return True
        time.sleep(1.0)
    print("      ⚠️ DNS đồng bộ hơi chậm; nếu máy khác báo không tìm thấy trang hãy đợi 10 giây rồi F5.", flush=True)
    return False


def start_cloudflare_tunnel(cloudflared_bin: str) -> None:
    """Mở Cloudflare Quick Tunnel (HTTP/2 ổn định trên mạng VN), chờ kết nối & DNS sẵn sàng rồi copy link."""
    print(f"[4/4] Đang mở Cloudflare Quick Tunnel tới {LOCAL_APP_URL}...", flush=True)
    cmd = [cloudflared_bin, "tunnel", "--protocol", "http2", "--url", LOCAL_APP_URL]
    proc = subprocess.Popen(
        cmd,
        cwd=BASE_DIR,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace",
        bufsize=1,
    )
    _MANAGED_PROCS.append(("Cloudflare Tunnel", proc))

    public_url = ""
    announced = False
    url_found_at = 0.0
    assert proc.stdout is not None
    for line in proc.stdout:
        clean_line = line.rstrip()
        if not public_url:
            m = TRYCLOUDFLARE_REGEX.search(clean_line)
            if m:
                public_url = m.group(0)
                url_found_at = time.time()
                print(f"      -> Đã cấp phát tên miền tạm: {public_url}", flush=True)
                print("      ⏳ Đang chờ tunnel đăng ký kết nối với máy chủ Cloudflare...", flush=True)
        elif not announced:
            tunnel_registered = "Registered tunnel connection" in clean_line
            timed_out_reg = (time.time() - url_found_at) > 12.0
            if tunnel_registered or timed_out_reg:
                announced = True
                _wait_for_public_dns_ready(public_url, max_wait=25)
                copy_to_clipboard_windows(public_url)
                lan_ip = _get_lan_ip()
                # Phát âm báo nhẹ khi link đã thực sự sẵn sàng truy cập
                print("\a", end="", flush=True)
                border = "=" * 78
                print(f"\n{border}", flush=True)
                print("  DA COPY LINK VAO CLIPBOARD - CHI CAN NHAN CTRL + V DE GUI CHO NGUOI KHAC!", flush=True)
                print(f"  LINK CHIA SE INTERNET  : {public_url}", flush=True)
                if lan_ip:
                    print(f"  LINK CUNG WI-FI (LAN)  : http://{lan_ip}:{STREAMLIT_PORT}", flush=True)
                print(f"  LINK CUC BO (MAY NAY)  : {LOCAL_APP_URL}", flush=True)
                print(f"{border}", flush=True)
                print("  [GIU CUA SO NAY MO DE DUY TRI LINK CHIA SE | NHAN CTRL + C DE TAT]\n", flush=True)

                try:
                    webbrowser.open(LOCAL_APP_URL)
                except Exception:
                    pass
        else:
            # Chỉ in các dòng lỗi nghiêm trọng nếu có sau khi tunnel đã kết nối
            if "ERR" in clean_line and "context canceled" not in clean_line:
                print(f"[cloudflared] {clean_line}", flush=True)

    proc.wait()


def main() -> None:
    atexit.register(cleanup_processes)
    _register_windows_close_handler()

    def _sig_handler(signum, frame):
        cleanup_processes()
        sys.exit(0)

    signal.signal(signal.SIGINT, _sig_handler)
    signal.signal(signal.SIGTERM, _sig_handler)

    print("==============================================================================", flush=True)
    print("  AI SINH & KIEM DINH DE THI TIN HOC 10 (CHU DE F) - CHE DO CHIA SE 1-CLICK", flush=True)
    print("==============================================================================\n", flush=True)

    try:
        cloudflared_bin = ensure_cloudflared()
        ensure_ollama_running()
        start_streamlit()
        start_cloudflare_tunnel(cloudflared_bin)
    except KeyboardInterrupt:
        pass
    except Exception as e:
        print(f"\n❌ Lỗi khởi chạy chia sẻ công khai: {e}", flush=True)
        input("\nNhấn Enter để đóng cửa sổ...")
    finally:
        cleanup_processes()


if __name__ == "__main__":
    main()
