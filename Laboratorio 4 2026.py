from machine import I2C, Pin
import ssd1306
import socket
import network
import time

# ── Configuración I2C ──────────────────────────────────────────
i2c = I2C(0, scl=Pin(22), sda=Pin(21), freq=400000)

LM75_ADDR = 0x48
OLED_ADDR  = 0x3C

oled = ssd1306.SSD1306_I2C(128, 64, i2c, addr=OLED_ADDR)

# ── Función: leer LM75 ─────────────────────────────────────────
def leer_lm75():
    data = i2c.readfrom_mem(LM75_ADDR, 0x00, 2)
    raw = (data[0] << 1) | (data[1] >> 7)
    if raw > 255:
        raw -= 512
    return raw * 0.5

# ── Función: decodificar URL encoding ─────────────────────────
def url_decode(s):
    res = ''
    i = 0
    while i < len(s):
        if s[i] == '%' and i + 2 < len(s):
            res += chr(int(s[i+1:i+3], 16))
            i += 3
        elif s[i] == '+':
            res += ' '
            i += 1
        else:
            res += s[i]
            i += 1
    return res

# ── Función: mostrar en OLED ───────────────────────────────────
# y=0  → "Temperatura"  (título)
# y=12 → "XX.X C"       (valor)
# y=24 → separador
# y=36 → mensaje (1 línea)
# y=52 → IP
def mostrar_texto_oled(texto, temperatura):
    oled.fill(0)
    oled.text("Temperatura", 0, 0)
    oled.text("{:.1f} C".format(temperatura), 0, 12)
    for x in range(128):
        if x % 2 == 0:
            oled.pixel(x, 24, 1)
    if texto:
        palabras = texto.split(' ')
        linea = ''
        for palabra in palabras:
            prueba = linea + (' ' if linea else '') + palabra
            if len(prueba) <= 16:
                linea = prueba
            else:
                break
        if linea:
            oled.text(linea, 0, 36)
    oled.text(ip, 0, 52)
    oled.show()

# ── WiFi ───────────────────────────────────────────────────────
WIFI_SSID     = "iPhone Danic"
WIFI_PASSWORD = "1007109983"

sta = network.WLAN(network.STA_IF)
sta.active(True)
sta.connect(WIFI_SSID, WIFI_PASSWORD)

print("Conectando a WiFi", end="")
timeout = 15
while not sta.isconnected() and timeout > 0:
    print(".", end="")
    time.sleep(1)
    timeout -= 1

if sta.isconnected():
    ip = sta.ifconfig()[0]
    print("\nConectado! IP:", ip)
else:
    print("\nFalló WiFi. Iniciando como Access Point...")
    sta.active(False)
    ap = network.WLAN(network.AP_IF)
    ap.active(True)
    ap.config(essid="ESP32-LM75", password="12345678")
    while not ap.active():
        pass
    ip = ap.ifconfig()[0]
    print("Access Point activo. IP:", ip)

oled.fill(0)
oled.text("WiFi OK!", 0, 10)
oled.text(ip, 0, 30)
oled.show()

# ── Página HTML ────────────────────────────────────────────────
def web_page(temp, msg=""):
    msg_escaped = msg.replace('"', '&quot;')
    return """<!DOCTYPE html>
<html lang="es">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>ESP32 - Temperatura</title>
  <style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');
    * {{ box-sizing: border-box; margin: 0; padding: 0; }}
    body {{
      font-family: 'Inter', sans-serif;
      background: #0f0e17;
      color: #e2e8f0;
      display: flex;
      flex-direction: column;
      align-items: center;
      justify-content: center;
      min-height: 100vh;
      padding: 20px;
      gap: 16px;
    }}
    .dashboard {{
      background: #1a1830;
      border: 1px solid #2a2845;
      border-radius: 16px;
      padding: 28px 32px 24px;
      max-width: 520px;
      width: 100%;
      box-shadow: 0 8px 40px rgba(0,0,0,0.5);
    }}
    .title {{
      font-size: 0.7rem;
      letter-spacing: 0.18em;
      text-transform: uppercase;
      color: #4a4870;
      margin-bottom: 16px;
      font-weight: 600;
    }}
    .main-value {{
      font-size: 3.8rem;
      font-weight: 700;
      color: #1de9b6;
      line-height: 1;
      letter-spacing: -1px;
    }}
    .main-label {{
      font-size: 0.72rem;
      color: #4a4870;
      letter-spacing: 0.12em;
      text-transform: uppercase;
      margin-top: 4px;
      margin-bottom: 18px;
    }}
    .chart-wrap {{
      width: 100%;
      height: 80px;
      margin-bottom: 20px;
      position: relative;
    }}
    canvas {{
      width: 100% !important;
      height: 80px !important;
    }}
    .stats-row {{
      display: grid;
      grid-template-columns: 1fr 1fr 1fr;
      gap: 10px;
      border-top: 1px solid #2a2845;
      padding-top: 16px;
      margin-bottom: 20px;
    }}
    .stat {{ text-align: center; }}
    .stat-label {{
      font-size: 0.62rem;
      letter-spacing: 0.12em;
      text-transform: uppercase;
      color: #4a4870;
      margin-bottom: 4px;
    }}
    .stat-value {{ font-size: 1.3rem; font-weight: 700; color: #1de9b6; }}
    .stat-value.red {{ color: #ff6b6b; }}
    .stat-value.blue {{ color: #74b9ff; }}
    .unit {{ font-size: 0.8rem; color: #4a4870; margin-left: 2px; }}
    .dot {{
      display: inline-block;
      width: 7px; height: 7px;
      background: #1de9b6;
      border-radius: 50%;
      margin-right: 6px;
      animation: pulse 1s infinite;
      vertical-align: middle;
    }}
    @keyframes pulse {{
      0%,100% {{ opacity:1; box-shadow: 0 0 0 0 rgba(29,233,182,0.4); }}
      50% {{ opacity:0.6; box-shadow: 0 0 0 5px rgba(29,233,182,0); }}
    }}
    .live-label {{
      font-size: 0.65rem;
      color: #4a4870;
      margin-bottom: 14px;
    }}

    /* ── Escala de temperatura ── */
    .scale-section {{
      border-top: 1px solid #2a2845;
      padding-top: 18px;
    }}
    .scale-header {{
      display: flex;
      justify-content: space-between;
      align-items: center;
      margin-bottom: 10px;
    }}
    .scale-label {{
      font-size: 0.62rem;
      letter-spacing: 0.12em;
      text-transform: uppercase;
      color: #4a4870;
    }}
    .scale-value {{
      font-size: 0.85rem;
      font-weight: 700;
      color: #1de9b6;
    }}
    .scale-track {{
      position: relative;
      width: 100%;
      height: 10px;
      border-radius: 999px;
      background: linear-gradient(
        to right,
        #74b9ff 0%,
        #1de9b6 25%,
        #ffd32a 55%,
        #ff6b6b 100%
      );
      margin-bottom: 6px;
    }}
    .scale-thumb {{
      position: absolute;
      top: 50%;
      transform: translate(-50%, -50%);
      width: 18px;
      height: 18px;
      border-radius: 50%;
      background: #fff;
      border: 3px solid #1de9b6;
      box-shadow: 0 0 8px rgba(29,233,182,0.6);
      transition: left 0.6s cubic-bezier(0.34, 1.56, 0.64, 1),
                  border-color 0.4s ease;
    }}
    .scale-limits {{
      display: flex;
      justify-content: space-between;
      font-size: 0.6rem;
      color: #4a4870;
      letter-spacing: 0.08em;
    }}
    .scale-ticks {{
      display: flex;
      justify-content: space-between;
      padding: 0 2px;
      margin-bottom: 4px;
    }}
    .scale-ticks span {{
      font-size: 0.55rem;
      color: #4a4870;
    }}

    /* ── Panel OLED ── */
    .oled-panel {{
      background: #1a1830;
      border: 1px solid #2a2845;
      border-radius: 16px;
      padding: 24px 32px;
      max-width: 520px;
      width: 100%;
      box-shadow: 0 8px 40px rgba(0,0,0,0.5);
    }}
    .oled-panel .title {{ margin-bottom: 14px; }}
    .oled-input-row {{
      display: flex;
      gap: 10px;
      align-items: center;
    }}
    .oled-input {{
      flex: 1;
      background: #0f0e17;
      border: 1px solid #2a2845;
      border-radius: 10px;
      padding: 10px 14px;
      color: #e2e8f0;
      font-family: 'Inter', sans-serif;
      font-size: 0.95rem;
      outline: none;
      transition: border-color 0.2s;
    }}
    .oled-input:focus {{ border-color: #1de9b6; }}
    .oled-btn {{
      background: #1de9b6;
      color: #0f0e17;
      border: none;
      border-radius: 10px;
      padding: 10px 20px;
      font-family: 'Inter', sans-serif;
      font-size: 0.9rem;
      font-weight: 700;
      cursor: pointer;
      transition: opacity 0.2s;
      white-space: nowrap;
    }}
    .oled-btn:hover {{ opacity: 0.85; }}
    .oled-status {{
      margin-top: 10px;
      font-size: 0.7rem;
      letter-spacing: 0.1em;
      color: #4a4870;
      min-height: 16px;
    }}
    .oled-status.ok {{ color: #1de9b6; }}
    .oled-status.err {{ color: #ff6b6b; }}
    .oled-preview {{
      background: #000;
      border: 2px solid #333;
      border-radius: 8px;
      width: 160px;
      height: 80px;
      margin-top: 14px;
      font-family: monospace;
      font-size: 8px;
      color: #1de9b6;
      padding: 3px 5px;
      line-height: 1.6;
      overflow: hidden;
    }}
    .oled-preview .sep {{ color: #444; }}
    .oled-preview .ip  {{ color: #888; }}
  </style>
</head>
<body>

  <div class="dashboard">
    <p class="title">&#9656; Monitor de Temperatura</p>
    <div class="main-value" id="temp">{:.1f}<span style="font-size:1.8rem; color:#4a4870;">°C</span></div>
    <p class="main-label">Sensor LM75 &bull; I²C</p>
    <div class="chart-wrap">
      <canvas id="chart"></canvas>
    </div>
    <p class="live-label"><span class="dot"></span>Actualización en tiempo real &mdash; cada 1 s</p>
    <div class="stats-row">
      <div class="stat">
        <p class="stat-label">Promedio</p>
        <p class="stat-value" id="avg">--<span class="unit">°C</span></p>
      </div>
      <div class="stat">
        <p class="stat-label">Máximo</p>
        <p class="stat-value red" id="max">--<span class="unit">°C</span></p>
      </div>
      <div class="stat">
        <p class="stat-label">Mínimo</p>
        <p class="stat-value blue" id="min">--<span class="unit">°C</span></p>
      </div>
    </div>

    <!-- Escala visual 0-100 -->
    <div class="scale-section">
      <div class="scale-header">
        <p class="scale-label">Escala de temperatura</p>
        <p class="scale-value" id="scale-val">-- °C</p>
      </div>
      <div class="scale-track">
        <div class="scale-thumb" id="scale-thumb"></div>
      </div>
      <div class="scale-ticks">
        <span>0</span>
        <span>25</span>
        <span>50</span>
        <span>75</span>
        <span>100</span>
      </div>
      <div class="scale-limits">
        <span>0 °C &mdash; Frío</span>
        <span>Caliente &mdash; 100 °C</span>
      </div>
    </div>
  </div>

  <div class="oled-panel">
    <p class="title">&#9656; Mensaje en pantalla OLED</p>
    <div class="oled-input-row">
      <input class="oled-input" type="text" id="oled-msg" maxlength="48"
             placeholder="Escribe un mensaje..." value="{}" />
      <button class="oled-btn" onclick="enviarMensaje()">Enviar</button>
    </div>
    <p class="oled-status" id="oled-status"></p>
    <div class="oled-preview">
      <span style="color:#aaa">Temperatura</span><br>
      <span id="prev-temp">-- C</span><br>
      <span class="sep">- - - - - - - - -</span><br>
      <span id="prev-msg"></span><br>
      <span class="ip">{}</span>
    </div>
  </div>

  <script>
    const MAX_POINTS = 60;
    const history = [];
    const canvas = document.getElementById('chart');
    const ctx = canvas.getContext('2d');
    const SCALE_MIN = 0;
    const SCALE_MAX = 100;

    function resizeCanvas() {{
      canvas.width = canvas.offsetWidth;
      canvas.height = 80;
    }}
    resizeCanvas();
    window.addEventListener('resize', resizeCanvas);

    function drawChart() {{
      const W = canvas.width, H = canvas.height;
      ctx.clearRect(0, 0, W, H);
      if (history.length < 2) return;
      const mn = Math.min(...history) - 1;
      const mx = Math.max(...history) + 1;
      const toY = v => H - ((v - mn) / (mx - mn)) * (H - 10) - 5;
      const grad = ctx.createLinearGradient(0, 0, 0, H);
      grad.addColorStop(0, 'rgba(29,233,182,0.25)');
      grad.addColorStop(1, 'rgba(29,233,182,0.0)');
      ctx.beginPath();
      history.forEach((v, i) => {{
        const x = (i / (MAX_POINTS - 1)) * W;
        i === 0 ? ctx.moveTo(x, toY(v)) : ctx.lineTo(x, toY(v));
      }});
      ctx.lineTo((history.length - 1) / (MAX_POINTS - 1) * W, H);
      ctx.lineTo(0, H);
      ctx.closePath();
      ctx.fillStyle = grad;
      ctx.fill();
      ctx.beginPath();
      history.forEach((v, i) => {{
        const x = (i / (MAX_POINTS - 1)) * W;
        i === 0 ? ctx.moveTo(x, toY(v)) : ctx.lineTo(x, toY(v));
      }});
      ctx.strokeStyle = '#1de9b6';
      ctx.lineWidth = 2;
      ctx.lineJoin = 'round';
      ctx.stroke();
      const lx = ((history.length - 1) / (MAX_POINTS - 1)) * W;
      const ly = toY(history[history.length - 1]);
      ctx.beginPath();
      ctx.arc(lx, ly, 4, 0, Math.PI * 2);
      ctx.fillStyle = '#1de9b6';
      ctx.fill();
    }}

    function updateStats() {{
      if (history.length === 0) return;
      const avg = (history.reduce((a, b) => a + b, 0) / history.length).toFixed(1);
      const mx  = Math.max(...history).toFixed(1);
      const mn  = Math.min(...history).toFixed(1);
      document.getElementById('avg').innerHTML = avg + '<span class="unit">°C</span>';
      document.getElementById('max').innerHTML = mx  + '<span class="unit">°C</span>';
      document.getElementById('min').innerHTML = mn  + '<span class="unit">°C</span>';
    }}

    function updateScale(val) {{
      const pct = Math.min(Math.max((val - SCALE_MIN) / (SCALE_MAX - SCALE_MIN), 0), 1);
      const thumb = document.getElementById('scale-thumb');
      thumb.style.left = (pct * 100) + '%';
      if (val < 15)       thumb.style.borderColor = '#74b9ff';
      else if (val < 30)  thumb.style.borderColor = '#1de9b6';
      else if (val < 60)  thumb.style.borderColor = '#ffd32a';
      else                thumb.style.borderColor = '#ff6b6b';
      document.getElementById('scale-val').textContent = val.toFixed(1) + ' \u00b0C';
    }}

    setInterval(function() {{
      fetch('/temp')
        .then(r => r.text())
        .then(t => {{
          const val = parseFloat(t);
          if (isNaN(val)) return;
          document.getElementById('temp').innerHTML =
            val.toFixed(1) + '<span style="font-size:1.8rem;color:#4a4870;">\u00b0C</span>';
          document.getElementById('prev-temp').textContent = val.toFixed(1) + ' C';
          history.push(val);
          if (history.length > MAX_POINTS) history.shift();
          drawChart();
          updateStats();
          updateScale(val);
        }})
        .catch(() => {{}});
    }}, 1000);

    function wrapText(text, maxChars) {{
      const words = text.split(' ');
      let line = '';
      for (const word of words) {{
        const prueba = line ? line + ' ' + word : word;
        if (prueba.length <= maxChars) line = prueba;
        else break;
      }}
      return line;
    }}

    document.getElementById('oled-msg').addEventListener('input', function() {{
      document.getElementById('prev-msg').textContent = wrapText(this.value, 16);
    }});

    function enviarMensaje() {{
      const msg = document.getElementById('oled-msg').value.trim();
      const status = document.getElementById('oled-status');
      if (!msg) {{
        status.textContent = 'Escribe algo primero.';
        status.className = 'oled-status err';
        return;
      }}
      status.textContent = 'Enviando...';
      status.className = 'oled-status';
      fetch('/oled?msg=' + encodeURIComponent(msg))
        .then(r => r.text())
        .then(() => {{
          status.textContent = '\u2713 Mensaje enviado a la OLED';
          status.className = 'oled-status ok';
          document.getElementById('prev-msg').textContent = wrapText(msg, 16);
        }})
        .catch(() => {{
          status.textContent = '\u2717 Error al enviar';
          status.className = 'oled-status err';
        }});
    }}

    document.getElementById('oled-msg').addEventListener('keydown', function(e) {{
      if (e.key === 'Enter') enviarMensaje();
    }});
  </script>
</body>
</html>""".format(temp, msg_escaped, ip)

# ── Servidor HTTP ──────────────────────────────────────────────
s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
s.bind(('', 80))
s.listen(5)

print("Servidor listo en http://{}".format(ip))

ultima_temp = None
mensaje_oled = ""

while True:
    try:
        conn, addr = s.accept()
        request = conn.recv(1024).decode()

        temperatura = leer_lm75()
        print("Petición de {} → {:.1f} °C".format(addr[0], temperatura))

        if '/oled' in request:
            try:
                msg_raw = request.split('/oled?msg=')[1].split(' ')[0]
                mensaje_oled = url_decode(msg_raw)[:48]
            except:
                mensaje_oled = ""
            mostrar_texto_oled(mensaje_oled, temperatura)
            ultima_temp = temperatura
            conn.send("HTTP/1.1 200 OK\r\nContent-Type: text/plain\r\nConnection: close\r\n\r\n")
            conn.sendall("ok")

        elif '/temp' in request:
            if temperatura != ultima_temp:
                mostrar_texto_oled(mensaje_oled, temperatura)
                ultima_temp = temperatura
            conn.send("HTTP/1.1 200 OK\r\nContent-Type: text/plain\r\nConnection: close\r\n\r\n")
            conn.sendall("{:.1f}".format(temperatura))

        else:
            mensaje_oled = ""
            mostrar_texto_oled("", temperatura)
            ultima_temp = temperatura
            html = web_page(temperatura, mensaje_oled)
            conn.send("HTTP/1.1 200 OK\r\nContent-Type: text/html\r\nConnection: close\r\n\r\n")
            conn.sendall(html)

        conn.close()

    except Exception as e:
        print("Error:", e)
        try:
            conn.close()
        except:
            pass