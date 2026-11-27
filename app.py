#!/usr/bin/env python3
import json
import os
import urllib.parse
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
REFERER = "https://www.premrawat.com/gifts-album/"
USER_AGENT = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36"


def find_json_file():
    search_dirs = [
        BASE_DIR,
        os.getcwd(),
        os.path.expanduser("~"),
        os.path.expanduser("~/Descargas"),
        os.path.expanduser("~/Downloads"),
        os.path.expanduser("~/Música"),
        os.path.expanduser("~/Music"),
    ]
    seen = set()
    for d in search_dirs:
        norm = os.path.abspath(d)
        if norm in seen or not os.path.isdir(norm):
            continue
        seen.add(norm)
        for name in ("gifts_album_yt.json", "gifts_album.json"):
            p = os.path.join(norm, name)
            if os.path.isfile(p):
                return p
    return None


HTML_PAGE = """<!DOCTYPE html>
<html lang="es">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>Lyrics Sync Para Prem</title>
  <script src="https://cdn.jsdelivr.net/npm/hls.js@latest"></script>
  <style>
    body { font-family: system-ui, sans-serif; margin: 16px; background: #141619; color: #eef1f4; }
    .row { display: flex; gap: 8px; flex-wrap: wrap; align-items: center; margin-bottom: 10px; }
    select, button { padding: 8px 12px; border-radius: 6px; border: 1px solid #343a40; background: #212529; color: #fff; cursor: pointer; }
    select { flex: 1; min-width: 240px; }
    button:hover { background: #2c3238; }
    .clock {
      font-family: monospace;
      font-size: 1.6rem;
      font-weight: bold;
      padding: 4px 12px;
      min-width: 155px;
      text-align: center;
      box-sizing: border-box;
      border: 1px solid #495057;
      border-radius: 6px;
      background: #1b1e23;
    }
    .grid { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; margin-bottom: 12px; }
    .box { border: 1px solid #2b3036; border-radius: 8px; padding: 10px; background: #191c20; height: 380px; overflow-y: auto; }
    .line-item { padding: 6px 8px; border-radius: 4px; cursor: pointer; margin-bottom: 4px; font-size: 0.95rem; }
    .line-item.active { background: #1f4e78; }
    .done-item { display: flex; gap: 10px; padding: 6px 8px; border-radius: 4px; cursor: pointer; margin-bottom: 4px; font-size: 0.92rem; }
    .done-item.selected { background: #2b593f; }
    .stamp { font-family: monospace; color: #8ce99a; white-space: nowrap; }
    .status { font-size: 0.9rem; color: #adb5bd; }
    .modal-backdrop { position: fixed; inset: 0; background: rgba(0, 0, 0, 0.7); display: none; align-items: center; justify-content: center; padding: 16px; z-index: 999; }
    .modal-backdrop.open { display: flex; }
    .modal-card { width: 100%; max-width: 680px; background: #191c20; border: 1px solid #343a40; border-radius: 8px; padding: 14px; display: flex; flex-direction: column; gap: 10px; }
    .modal-card textarea { width: 100%; height: 300px; background: #141619; color: #eef1f4; border: 1px solid #343a40; border-radius: 6px; padding: 10px; font-family: inherit; font-size: 0.95rem; resize: vertical; box-sizing: border-box; }
    .modal-actions { display: flex; justify-content: flex-end; gap: 8px; }
    @media (max-width: 760px) { .grid { grid-template-columns: 1fr; } }
  </style>
  <link rel="manifest" href="/manifest.json" />
  <link rel="icon" type="image/svg+xml" href="/icon.svg" />
  <meta name="theme-color" content="#141619" />
</head>
<body>
  <div class="row">
    <label for="songSelect">Canción:</label>
    <select id="songSelect"></select>
    <button id="btnPlay" type="button">▶ Reproducir / Pausa</button>
    <span id="clock" class="clock">00:00.00</span>
  </div>

  <div class="row">
    <button type="button" onclick="adjustTime(-0.50)">⏪ -0.50s</button>
    <button type="button" onclick="adjustTime(-0.10)">◀ -0.10s</button>
    <button type="button" onclick="adjustTime(+0.10)">+0.10s ▶</button>
    <button type="button" onclick="adjustTime(+0.50)">+0.50s ⏩</button>
    <button type="button" onclick="stampLine()">⏱ Marcar frase (Enter)</button>
    <button type="button" onclick="undoLast()">↩ Deshacer última</button>
    <button type="button" onclick="openEditModal()">✏️ Editar entrada</button>
    <button type="button" onclick="downloadLrc()">💾 Descargar .lrc</button>
  </div>

  <div class="grid">
    <div class="box">
      <div id="pendingHeader" style="font-weight:bold; margin-bottom:8px;">Pendientes</div>
      <div id="pendingList"></div>
    </div>
    <div class="box">
      <div style="font-weight:bold; margin-bottom:8px;">Ya hecho (clic para ajustar tiempo)</div>
      <div id="doneList"></div>
    </div>
  </div>

  <div id="status" class="status">Cargando canciones...</div>
  <audio id="audioEl"></audio>

  <div id="editModal" class="modal-backdrop">
    <div class="modal-card">
      <div style="font-weight:bold;">Editar letra de la entrada completa</div>
      <textarea id="editTextarea" placeholder="Una línea por frase..."></textarea>
      <div class="modal-actions">
        <button type="button" onclick="closeEditModal()">Cancelar</button>
        <button type="button" onclick="saveEditModal()">Guardar entrada</button>
      </div>
    </div>
  </div>

  <script>
    let songs = [];
    let currentSong = null;
    let pending = [];
    let activePendingIdx = 0;
    let done = [];
    let selectedDone = null;
    let hls = null;
    let manualTimeSec = 0;
    let seekCooldownUntil = 0;

    const audioEl = document.getElementById("audioEl");
    const songSelect = document.getElementById("songSelect");
    const clockEl = document.getElementById("clock");
    const statusEl = document.getElementById("status");
    const editModal = document.getElementById("editModal");
    const editTextarea = document.getElementById("editTextarea");

    function formatLrcTime(sec) {
      let totalCentis = Math.max(0, Math.round((Number(sec) || 0) * 100));
      const mins = Math.floor(totalCentis / 6000);
      totalCentis %= 6000;
      const secs = Math.floor(totalCentis / 100);
      const centis = totalCentis % 100;

      return `${String(mins).padStart(2, "0")}:${String(secs).padStart(2, "0")}.${String(centis).padStart(2, "0")}`;
    }

    function splitLines(raw) {
      if (!raw) return [];
      return raw
        .split(/(?:\\r?\\n)+| {2,}/)
        .map(x => x.replace(/\\s+/g, " ").trim())
        .filter(Boolean);
    }

    function currentTimeSec() {
      if (performance.now() < seekCooldownUntil) {
        return manualTimeSec;
      }
      if (!audioEl.paused && Number.isFinite(audioEl.currentTime)) {
        manualTimeSec = Number(audioEl.currentTime) || 0;
      }
      return manualTimeSec;
    }

    function setCurrentTimeSec(val) {
      const target = Math.max(0, Number(val) || 0);
      manualTimeSec = target;
      seekCooldownUntil = performance.now() + 350;
      clockEl.textContent = formatLrcTime(target);
      try {
        if (audioEl.readyState >= 1 || Number.isFinite(audioEl.duration)) {
          audioEl.currentTime = target;
        }
      } catch (_err) {}
    }

    function loadLyricsFromText(rawText, titleText) {
      pending = splitLines(rawText);
      activePendingIdx = 0;
      done = [];
      selectedDone = null;
      const cleanTitle = (titleText || "").replace(/\\s+/g, " ").trim();
      if (cleanTitle) {
        done.push({ seconds: 1.0, stamp: `[${formatLrcTime(1.0)}]`, text: `Título de la canción: ${cleanTitle}`, origIndex: null });
      }
      renderLists();
    }

    function loadSongAt(idx) {
      if (idx < 0 || idx >= songs.length) return;
      currentSong = songs[idx];
      audioEl.pause();
      seekCooldownUntil = 0;
      manualTimeSec = 0;
      clockEl.textContent = formatLrcTime(0);

      const title = (currentSong.title || "").trim();
      loadLyricsFromText(currentSong.lyrics || "", title);

      const yt = (currentSong.link_youtube || "").trim();
      statusEl.textContent = `Pista ${idx + 1}/${songs.length}: ${title} | ${yt ? "YouTube: " + yt : "Sin link de YouTube"}`;
      setupAudioSource(currentSong.audio || "");
    }

    function setupAudioSource(rawUrl) {
      if (hls) {
        hls.destroy();
        hls = null;
      }
      if (!rawUrl) return;
      const proxied = "/proxy?url=" + encodeURIComponent(rawUrl);

      if (audioEl.canPlayType("application/vnd.apple.mpegurl")) {
        audioEl.src = proxied;
      } else if (window.Hls && Hls.isSupported()) {
        hls = new Hls({ enableWorker: true });
        hls.loadSource(proxied);
        hls.attachMedia(audioEl);
      } else {
        audioEl.src = proxied;
      }
    }

    function renderLists() {
      const pList = document.getElementById("pendingList");
      const dList = document.getElementById("doneList");
      document.getElementById("pendingHeader").textContent = `Pendientes (${pending.length} líneas)`;

      if (pending.length === 0) {
        activePendingIdx = 0;
      } else if (activePendingIdx < 0 || activePendingIdx >= pending.length) {
        activePendingIdx = 0;
      }

      pList.innerHTML = "";
      pending.forEach((line, i) => {
        const div = document.createElement("div");
        div.className = "line-item" + (i === activePendingIdx ? " active" : "");
        div.textContent = line;
        div.onclick = () => {
          activePendingIdx = i;
          renderLists();
        };
        pList.appendChild(div);
      });

      dList.innerHTML = "";
      done.forEach((row, i) => {
        const div = document.createElement("div");
        div.className = "done-item" + (i === selectedDone ? " selected" : "");
        div.innerHTML = `<span class="stamp">${row.stamp}</span><span>${row.text}</span>`;
        div.onclick = () => {
          selectedDone = selectedDone === i ? null : i;
          renderLists();
        };
        dList.appendChild(div);
      });
    }

    function stampLine() {
      if (!pending.length) return;
      const idx = Math.max(0, Math.min(activePendingIdx, pending.length - 1));
      const [line] = pending.splice(idx, 1);
      const t = currentTimeSec();
      done.push({ seconds: t, stamp: `[${formatLrcTime(t)}]`, text: line, origIndex: idx });
      selectedDone = done.length - 1;
      activePendingIdx = pending.length ? Math.min(idx, pending.length - 1) : 0;
      renderLists();
    }

    function undoLast() {
      if (!done.length) return;
      const last = done.pop();
      if (last.origIndex !== null && last.origIndex !== undefined) {
        const pos = Math.max(0, Math.min(last.origIndex, pending.length));
        pending.splice(pos, 0, last.text);
        activePendingIdx = pos;
      } else {
        pending.unshift(last.text);
        activePendingIdx = 0;
      }
      selectedDone = done.length ? done.length - 1 : null;
      renderLists();
    }

    function getFullEntryText() {
      const doneWithPos = done.filter(r => r.origIndex !== null && r.origIndex !== undefined);
      if (doneWithPos.length) {
        const map = new Map();
        doneWithPos.forEach(r => map.set(r.origIndex, r.text));
        const total = Math.max(...Array.from(map.keys())) + 1 + pending.length;
        const merged = [];
        let pCursor = 0;
        for (let i = 0; i < total; i++) {
          if (map.has(i)) {
            merged.push(map.get(i));
          } else if (pCursor < pending.length) {
            merged.push(pending[pCursor++]);
          }
        }
        while (pCursor < pending.length) {
          merged.push(pending[pCursor++]);
        }
        return merged.join("\\n");
      }
      return pending.join("\\n");
    }

    function openEditModal() {
      editTextarea.value = getFullEntryText();
      editModal.classList.add("open");
      editTextarea.focus();
    }

    function closeEditModal() {
      editModal.classList.remove("open");
    }

    function saveEditModal() {
      const updated = editTextarea.value;
      if (currentSong) {
        currentSong.lyrics = updated;
      }
      const title = (currentSong && currentSong.title) || "";
      loadLyricsFromText(updated, title);
      closeEditModal();
      statusEl.textContent = "Entrada completa actualizada.";
    }

    function adjustTime(delta) {
      const nextTime = Math.max(0, manualTimeSec + delta);
      setCurrentTimeSec(nextTime);

      if (selectedDone !== null && done[selectedDone]) {
        const nextSec = Math.max(0, done[selectedDone].seconds + delta);
        done[selectedDone].seconds = nextSec;
        done[selectedDone].stamp = `[${formatLrcTime(nextSec)}]`;
        renderLists();
      }
    }

    function downloadLrc() {
      const lines = [];
      const yt = (currentSong && currentSong.link_youtube || "").trim();
      if (yt) lines.push(`#Link a youtube: ${yt}`);
      done.forEach(r => lines.push(`${r.stamp}${r.text}`));

      const blob = new Blob([lines.join("\\n") + "\\n"], { type: "text/plain;charset=utf-8" });
      const a = document.createElement("a");
      const safeTitle = ((currentSong && currentSong.title) || "cancion").replace(/[\\\\/:*?"<>|]/g, "");
      a.href = URL.createObjectURL(blob);
      a.download = `Prem Rawat - ${safeTitle}.lrc`;
      a.click();
      URL.revokeObjectURL(a.href);
    }

    document.getElementById("btnPlay").onclick = async () => {
      if (audioEl.paused) {
        try {
          if (manualTimeSec > 0.05 && audioEl.readyState >= 1) {
            audioEl.currentTime = manualTimeSec;
          }
          await audioEl.play();
        } catch (e) {
          statusEl.textContent = "Error al reproducir: " + e.message;
        }
      } else {
        manualTimeSec = Number(audioEl.currentTime) || manualTimeSec;
        audioEl.pause();
      }
    };

    songSelect.onchange = () => loadSongAt(songSelect.selectedIndex);

    setInterval(() => {
      if (!audioEl.paused && performance.now() >= seekCooldownUntil) {
        manualTimeSec = Number(audioEl.currentTime) || manualTimeSec;
        clockEl.textContent = formatLrcTime(manualTimeSec);
      }
    }, 80);

    document.addEventListener("keydown", (e) => {
      if (editModal.classList.contains("open")) {
        if (e.key === "Escape") closeEditModal();
        return;
      }
      if (["INPUT", "SELECT", "TEXTAREA"].includes(document.activeElement.tagName)) return;
      if (e.key === "Enter") { e.preventDefault(); stampLine(); }
      else if (e.key === "ArrowLeft") { e.preventDefault(); adjustTime(e.shiftKey ? -10 : -0.05); }
      else if (e.key === "ArrowRight") { e.preventDefault(); adjustTime(e.shiftKey ? 10 : 0.05); }
    });

    fetch("/api/songs")
      .then(r => r.json())
      .then(data => {
        songs = data;
        songs.forEach((s, i) => {
          const opt = document.createElement("option");
          opt.textContent = `${String(i + 1).padStart(3, "0")} - ${s.title || "Pista"} ${s.tag || ""}`.trim();
          songSelect.appendChild(opt);
        });
        if (songs.length) loadSongAt(0);
      })
      .catch(err => { statusEl.textContent = "No se pudo cargar /api/songs: " + err; });
  </script>
</body>
</html>
"""

MANIFEST_JSON = json.dumps({
    "name": "Lyrics Sync Para Prem",
    "short_name": "Lyrics Sync Para Prem",
    "start_url": "/",
    "display": "standalone",
    "background_color": "#141619",
    "theme_color": "#141619",
    "icons": [
        {
            "src": "/icon.svg",
            "sizes": "any",
            "type": "image/svg+xml",
            "purpose": "any maskable"
        }
    ]
}, ensure_ascii=False)

ICON_SVG = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 128 128">
  <rect width="128" height="128" rx="24" fill="#1f4e78"/>
  <circle cx="64" cy="64" r="36" fill="none" stroke="#8ce99a" stroke-width="8"/>
  <polygon points="56,46 84,64 56,82" fill="#eef1f4"/>
</svg>"""


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        if parsed.path in ("/", "/index.html"):
            body = HTML_PAGE.encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return

        if parsed.path == "/api/songs":
            json_path = find_json_file()
            songs = []
            if json_path:
                with open(json_path, "r", encoding="utf-8") as f:
                    songs = json.load(f)
            body = json.dumps(songs, ensure_ascii=False).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return

        if parsed.path == "/manifest.json":
            body = MANIFEST_JSON.encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/manifest+json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return

        if parsed.path == "/icon.svg":
            body = ICON_SVG.encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "image/svg+xml; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return

        if parsed.path == "/proxy":
            qs = urllib.parse.parse_qs(parsed.query)
            target_url = (qs.get("url") or [""])[0]
            if not target_url.startswith("https://secureaudio.timelesstoday.tv/"):
                self.send_error(403, "URL no permitida")
                return
            try:
                req = urllib.request.Request(
                    target_url,
                    headers={"Referer": REFERER, "User-Agent": USER_AGENT},
                )
                with urllib.request.urlopen(req, timeout=20) as resp:
                    content = resp.read()
                    ctype = resp.headers.get("Content-Type", "application/octet-stream")
                    if ".m3u8" in target_url or "mpegurl" in ctype.lower():
                        text = content.decode("utf-8", errors="replace")
                        rewritten = []
                        for line in text.splitlines():
                            s = line.strip()
                            if s and not s.startswith("#"):
                                abs_seg = urllib.parse.urljoin(target_url, s)
                                rewritten.append("/proxy?url=" + urllib.parse.quote(abs_seg, safe=""))
                            else:
                                rewritten.append(line)
                        content = ("\n".join(rewritten) + "\n").encode("utf-8")
                        ctype = "application/vnd.apple.mpegurl"

                self.send_response(200)
                self.send_header("Content-Type", ctype)
                self.send_header("Content-Length", str(len(content)))
                self.end_headers()
                self.wfile.write(content)
            except Exception as e:
                self.send_error(502, str(e))
            return

        self.send_error(404)

    def log_message(self, format, *args):
        return


def main():
    port = int(os.environ.get("PORT", "8765"))
    server = ThreadingHTTPServer(("0.0.0.0", port), Handler)
    print(f"App web escuchando en http://0.0.0.0:{port}", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
