"""Monte la video de demonstration a partir des deux prises reelles.

Entrees (dans ce dossier) : terminal3.mp4 (capture gdigrab de `tournage.py`),
marques.json (instants des scenes), webvid/*.webm (Playwright, demo Render),
voix-*.mp3 (edge-tts). Sortie : le chemin passe en argument.
"""
import json, re, subprocess, sys
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

ICI = Path(__file__).resolve().parent
SORTIE = Path(sys.argv[1])
W, H, FPS = 1920, 1080, 30
FOND = (14, 15, 17)
POLICE = "C:/Windows/Fonts/segoeui.ttf"
POLICE_G = "C:/Windows/Fonts/segoeuib.ttf"
MONO = "C:/Windows/Fonts/consola.ttf"

def dur(p):
    return float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(p)],
                                capture_output=True, text=True).stdout)

def ff(*args):
    subprocess.run(["ffmpeg", "-y", "-v", "error", *map(str, args)], check=True)

# ---------- cartons ----------
def carton(nom, lignes):
    im = Image.new("RGB", (W, H), FOND); d = ImageDraw.Draw(im)
    y = 330
    for texte, police, taille, couleur in lignes:
        f = ImageFont.truetype(police, taille)
        w = d.textlength(texte, font=f)
        d.text(((W - w) / 2, y), texte, font=f, fill=couleur)
        y += int(taille * 1.6)
    im.save(ICI / nom)

carton("carton-debut.png", [
    ("Spend Mandate", POLICE_G, 96, (240, 240, 240)),
    ("Live run on the machine it was built for  ·  10 November 2026", POLICE, 40, (190, 196, 204)),
    ("", POLICE, 20, FOND),
    ("Part 1 — terminal:  python -m mandat.demo   (scene A pays in the PayPal sandbox)", MONO, 32, (150, 200, 255)),
    ("Part 2 — the hosted demo on Render, in Chrome", MONO, 32, (150, 200, 255)),
])
carton("carton-fin.png", [
    ("The agent proposes. The code decides.", POLICE_G, 72, (240, 240, 240)),
    ("", POLICE, 20, FOND),
    ("github.com/Yoh5/paypal-mandat   ·   Apache-2.0", MONO, 40, (150, 200, 255)),
    ("spend-mandate-demo.onrender.com", MONO, 40, (150, 200, 255)),
])

# Badge pose sur la marge droite du terminal.
badge = Image.new("RGBA", (W, H), (0, 0, 0, 0)); d = ImageDraw.Draw(badge)
f1, f2 = ImageFont.truetype(POLICE_G, 30), ImageFont.truetype(POLICE, 24)
d.rectangle([1690, 40, 1890, 170], fill=(176, 30, 30, 255))
d.text((1710, 52), "LIVE RUN", font=f1, fill="white")
d.text((1710, 96), "this machine", font=f2, fill="white")
d.text((1710, 128), "PayPal sandbox", font=f2, fill="white")
badge.save(ICI / "badge.png")

# ---------- segments ----------
m = json.load(open(ICI / "marques.json"))
T0 = 3.5                                     # instant ou le texte apparait dans terminal3.mp4
sc = {k: T0 + t for k, t in m["marques"]}    # Scene A/B/D/C -> instant dans la video
fin_c = T0 + m["fin"]
V = {k: dur(ICI / f"voix-{k}.mp3") for k in ("intro", "A", "B", "D", "C", "web1", "web2", "web3", "outro")}

segments = []   # (fichier, duree)
def seg_carton(img, d, nom):
    out = ICI / f"s-{nom}.mp4"
    ff("-loop", "1", "-t", d, "-i", ICI / img, "-r", FPS, "-c:v", "libx264", "-pix_fmt", "yuv420p", "-preset", "veryfast", out)
    segments.append((out, d))

def seg_terminal(nom, debut, fin, voix):
    brut = fin - debut
    d = max(brut, voix + 0.8)
    out = ICI / f"s-{nom}.mp4"
    vf = (f"scale=-2:960:flags=lanczos,pad={W}:{H}:(ow-iw)/2:0:color=0x0c0c0c,"
          f"tpad=stop_mode=clone:stop_duration={d - brut + 0.1:.2f},fps={FPS}")
    ff("-ss", f"{debut:.2f}", "-t", f"{brut:.2f}", "-i", ICI / "terminal3.mp4", "-i", ICI / "badge.png",
       "-filter_complex", f"[0:v]{vf}[v];[v][1:v]overlay=0:0,trim=duration={d:.2f}[o]", "-map", "[o]",
       "-c:v", "libx264", "-pix_fmt", "yuv420p", "-preset", "veryfast", "-crf", "18", out)
    segments.append((out, d))

seg_carton("carton-debut.png", 4.0, "debut")
seg_terminal("ouverture", T0, sc["Scene A"], 0)
seg_terminal("A", sc["Scene A"], sc["Scene B"], V["A"])
seg_terminal("B", sc["Scene B"], sc["Scene D"], V["B"])
seg_terminal("D", sc["Scene D"], sc["Scene C"], V["D"])
seg_terminal("C", sc["Scene C"], sc["Scene C"] + 12.5, V["C"])

web = sorted((ICI / "webvid").glob("*.webm"))[0]
web_brut = dur(web)
web_d = max(web_brut, 20.5 + V["web3"] + 0.8)
out = ICI / "s-web.mp4"
ff("-i", web, "-vf", f"crop=1280:720:0:0,scale=1706:960:flags=lanczos,pad={W}:{H}:(ow-iw)/2:0:color=0x0c0c0c,tpad=stop_mode=clone:stop_duration={web_d - web_brut + 0.1:.2f},fps={FPS},trim=duration={web_d:.2f}",
   "-c:v", "libx264", "-pix_fmt", "yuv420p", "-preset", "veryfast", "-crf", "18", out)
segments.append((out, web_d))
seg_carton("carton-fin.png", V["outro"] + 1.2, "fin")

# ---------- quand chaque voix commence ----------
debuts, t = {}, 0.0
for (f, d) in segments:
    debuts[f.stem] = t; t += d
TOTAL = t
pose = {
    "intro": debuts["s-debut"] + 0.5,
    "A": debuts["s-A"] + 0.4, "B": debuts["s-B"] + 0.4, "D": debuts["s-D"] + 0.4, "C": debuts["s-C"] + 0.4,
    "web1": debuts["s-web"] + 0.4, "web2": debuts["s-web"] + 12.2, "web3": debuts["s-web"] + 20.5,
    "outro": debuts["s-fin"] + 0.3,
}
# Garde-fou : deux voix ne se chevauchent jamais.
ordre = sorted(pose, key=pose.get)
for a, b in zip(ordre, ordre[1:]):
    assert pose[a] + V[a] <= pose[b] + 0.01, (a, b, pose[a] + V[a], pose[b])

# ---------- sous-titres : une phrase = un sous-titre, temps au prorata des caracteres ----------
txt = json.load(open(ICI / "voix.json", encoding="utf-8"))
def hms(s):
    h, r = divmod(s, 3600); mi, se = divmod(r, 60)
    return f"{int(h):02d}:{int(mi):02d}:{int(se):02d},{int(round((se % 1) * 1000)):03d}".replace(",1000", ",999")
srt, n = [], 1
for k in ordre:
    phrases = [p for p in re.split(r"(?<=[.])\s+", txt[k]) if p]
    total_car = sum(len(p) for p in phrases); t = pose[k]
    for p in phrases:
        d = V[k] * len(p) / total_car
        srt.append(f"{n}\n{hms(t)} --> {hms(t + d - 0.05)}\n{p}\n"); n += 1; t += d
(ICI / "live.en.srt").write_text("\n".join(srt), encoding="utf-8")

# ---------- assemblage ----------
(ICI / "liste.txt").write_text("".join(f"file '{f.name}'\n" for f, _ in segments), encoding="utf-8")
ff("-f", "concat", "-safe", "0", "-i", ICI / "liste.txt", "-c", "copy", ICI / "images.mp4")
entrees, filtres = [], []
for i, k in enumerate(ordre):
    entrees += ["-i", ICI / f"voix-{k}.mp3"]
    ms = int(pose[k] * 1000)
    filtres.append(f"[{i + 1}:a]aresample=48000,adelay={ms}|{ms}[a{i}]")
mix = "".join(f"[a{i}]" for i in range(len(ordre))) + f"amix=inputs={len(ordre)}:normalize=0:duration=longest[a]"
style = "FontName=Segoe UI,FontSize=17,PrimaryColour=&H00FFFFFF,BackColour=&H99000000,BorderStyle=4,Outline=0,Shadow=0,MarginV=8"
subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", "images.mp4", *map(str, entrees),
                "-filter_complex", ";".join(filtres) + ";" + mix + f";[0:v]subtitles=live.en.srt:force_style='{style}'[v]",
                "-map", "[v]", "-map", "[a]", "-c:v", "libx264", "-preset", "medium", "-crf", "20", "-pix_fmt", "yuv420p",
                "-c:a", "aac", "-b:a", "160k", "-t", f"{TOTAL:.2f}", "-movflags", "+faststart", str(SORTIE)], check=True, cwd=ICI)
print(json.dumps({"total_s": round(TOTAL, 2), "segments": {f.stem: round(d, 2) for f, d in segments},
                  "voix": {k: round(pose[k], 2) for k in ordre}}, indent=1))
