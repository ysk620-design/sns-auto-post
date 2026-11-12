"""ストーリー形式（アメコミ風カルーセル＋国旗チャットのリール）のデザイン。

カルーセル（1080×1350）とリール用の縦長画面（1080×1920）のHTMLを作る。
文字に使える装飾は <br> と <em>（チャットの見出しの黄色マーカー）だけ。
"""
from .art import guy, burst, icon

REAL = "実話をもとに再現"

FONT = '*{margin:0;padding:0;box-sizing:border-box}body{font-family:"Noto Sans CJK JP","Noto Color Emoji",sans-serif;color:#111}'
COMMON = '''
.logo{position:absolute;top:50px;left:60px;background:#ffe14d;border:6px solid #111;border-radius:999px;padding:8px 30px;font-size:32px;font-weight:900;box-shadow:6px 6px 0 #111;z-index:5}
.note{position:absolute;bottom:18px;right:28px;font-size:22px;color:#fff;opacity:.75}
.fl{width:92px;height:92px;border-radius:50%;background:#fff;border:5px solid #111;display:flex;align-items:center;justify-content:center;font-size:54px;flex:none}
'''
AC = FONT + COMMON + '''
.s{width:1080px;height:1350px;position:relative;overflow:hidden;padding:170px 70px 110px;
 background:repeating-conic-gradient(from 0deg at 50% 45%,#ff4a3d 0 6deg,#ff6d3d 6deg 12deg)}
.s.blue{background:repeating-conic-gradient(from 0deg at 85% 90%,#2b6cff 0 6deg,#4a8bff 6deg 12deg)}
.s.yel{background:repeating-conic-gradient(from 0deg at 50% 50%,#ffd21f 0 6deg,#ffe14d 6deg 12deg)}
.yel .note{color:#111}
.pg{position:absolute;top:56px;right:60px;background:#fff;border:5px solid #111;border-radius:999px;padding:2px 22px;font-size:30px;font-weight:900}
.t{font-weight:900;-webkit-text-stroke:16px #111;paint-order:stroke fill;transform:rotate(-3deg);transform-origin:left}
.t.w{color:#fff}.t.y{color:#ffe14d}
.p{background:#fff;border:8px solid #111;border-radius:12px;box-shadow:14px 14px 0 #111}
.cm{display:flex;gap:26px;align-items:flex-start;padding:34px 38px;margin-bottom:44px}
.cm small{display:block;font-size:28px;font-weight:900;color:#2b6cff;margin-bottom:6px}
.cm p{font-size:43px;font-weight:900;line-height:1.45}
.foot{position:absolute;bottom:40px;left:70px;font-size:30px;font-weight:900;color:#fff;-webkit-text-stroke:7px #111;paint-order:stroke fill}
.btn{display:inline-block;background:#ff4f7b;color:#fff;border:7px solid #111;border-radius:999px;padding:22px 56px;font-size:46px;font-weight:900;box-shadow:10px 10px 0 #111}
'''

def cover_inner(p, tall=False):
    """表紙の中身。tall=True ならリール用(1080x1920)に縦位置をずらす"""
    dy = 285 if tall else 0
    return f'''
  <div class="t w" style="position:absolute;left:70px;top:{170+dy}px;font-size:62px">{p["top"]}</div>
  <div class="t y" style="position:absolute;left:70px;top:{265+dy}px;font-size:{p.get("big_size",112)}px;line-height:1.2">{p["big"]}</div>
  <div style="position:absolute;left:50px;top:{640+dy}px">{icon(p["icon"],430)}</div>
  <div style="position:absolute;left:400px;top:{560+dy}px">{burst(p.get("burst","WOW!"),300,"#ffe14d").replace('fill="#fff" stroke="#222"','fill="#ff3d5a" stroke="#111"')}</div>
  <div style="position:absolute;right:40px;top:{700+dy}px">{guy("wow",340)}</div>
  <div class="p" style="position:absolute;left:70px;right:70px;top:{1110+dy}px;padding:24px 30px;font-size:52px;font-weight:900;text-align:center">海外の反応は…？ ▶</div>'''

RC = AC.replace('.s{width:1080px;height:1350px', '.s{width:1080px;height:1920px') + '''
.chat{width:1080px;height:1920px;position:relative;overflow:hidden;background:#e9eef5}
.hd{position:absolute;top:0;left:0;right:0;height:330px;background:#fff;border-bottom:8px solid #111;padding:150px 60px 0}
.hd .logo{top:50px}
.hd h1{font-size:50px;font-weight:900;line-height:1.35}
.hd h1 em{font-style:normal;background:linear-gradient(transparent 55%,#ffe14d 55%)}
.list{position:absolute;top:380px;left:50px;right:150px}
.row{display:flex;gap:20px;align-items:flex-start;margin-bottom:30px}
.row.r{flex-direction:row-reverse}
.bb{background:#fff;border:5px solid #111;border-radius:34px;padding:22px 32px;font-size:40px;font-weight:700;line-height:1.45;max-width:730px;box-shadow:6px 6px 0 #111}
.bb small{display:block;font-size:26px;color:#6b7590;font-weight:900}
.row.r .bb{background:#d8f5d2}
.row.new .bb{background:#fff7b8}
.row.r.new .bb{background:#fff7b8}
.chat .note{color:#111}
'''

CSS = AC + '''
.note{font-size:22px}
.kj{display:inline-flex;width:120px;height:120px;border-radius:50%;background:#ffe14d;border:8px solid #111;align-items:center;justify-content:center;font-size:72px;font-weight:900;box-shadow:8px 8px 0 #111;margin-right:24px;flex:none}
.hrow{display:flex;align-items:center;margin-bottom:36px}
.stage{position:relative;height:560px;overflow:hidden;background:#fff}
.say{position:absolute;top:30px;left:40px;right:40px;background:#fff;border:6px solid #111;border-radius:40px;padding:20px 30px;font-size:46px;font-weight:900;text-align:center;z-index:3}
.say:after{content:"";position:absolute;bottom:-30px;right:180px;width:36px;height:36px;background:#fff;border-right:6px solid #111;border-bottom:6px solid #111;transform:rotate(45deg)}
.say.l:after{right:auto;left:180px}
.real{position:absolute;top:56px;right:60px;background:#fff;border:5px solid #111;border-radius:999px;padding:6px 24px;font-size:28px;font-weight:900}
.nar{margin-top:44px;background:#ffe14d;border:7px solid #111;padding:30px 40px;font-size:44px;font-weight:700;line-height:1.6;box-shadow:12px 12px 0 #111}
'''
CLERK = dict(hair="#2b2b2b", shirt="#ff9a3c")

POLICE = dict(hair="#2b2b2b", shirt="#2f4a8a")
def cm2(f, n, t):
    return f'<div class="p cm"><div class="fl">{f}</div><div><small>{n}</small><p>{t}</p></div></div>'

def stage(sc):
    side = "l" if sc.get("clerk") else ""
    parts = [f'<div class="say {side}">{sc["say"]}</div>']
    if sc.get("clerk"):
        look = dict(POLICE if sc.get("police") else CLERK); look.update(sc.get("look", {}))
        cw = 250 if sc.get("kid") else 330
        parts.append(f'<div style="position:absolute;left:30px;bottom:-10px">{guy(sc["clerk"],cw,**look)}</div>')
        if sc.get("prop"): parts.append(f'<div style="position:absolute;left:{cw}px;bottom:40px">{icon(sc["prop"],230)}</div>')
    elif sc.get("prop"):
        parts.append(f'<div style="position:absolute;left:40px;bottom:20px">{icon(sc["prop"],360)}</div>')
    parts.append(f'<div style="position:absolute;right:40px;bottom:-10px">{guy(sc["mood"],340)}</div>')
    return f'<div class="p stage">{"".join(parts)}</div>'

def stat(p, n, name, handle, tall=False):
    st = p["stat"]
    return f'''<section class="s blue"{' style="height:1920px;padding-top:380px"' if tall else ''}><div class="logo"{' style="top:200px"' if tall else ''}>🌏 {name}</div>{'' if tall else f'<div class="pg">{n-1}/{n}</div>'}
  <div class="t w" style="font-size:80px;margin-bottom:40px">実は…</div>
  <div class="p" style="padding:46px 50px"><div style="font-size:40px;font-weight:700">{st["l1"]}</div>
  <div style="font-size:96px;font-weight:900;color:#ff3d5a;line-height:1.2;margin:10px 0 24px">{st["n1"]}</div>
  <div style="font-size:40px;font-weight:700">{st["l2"]}</div>
  <div style="font-size:96px;font-weight:900;color:#2b6cff;line-height:1.2;margin-top:10px">{st["n2"]}</div></div>
  <div class="p" style="padding:26px 40px;margin-top:40px;font-size:40px;font-weight:900;line-height:1.5">{st["msg"]}</div>
  <div style="font-size:24px;color:#fff;margin-top:24px;font-weight:700">{st["src"]}</div>
  <div class="foot"{' style="bottom:300px"' if tall else ''}>{handle}</div></section>'''

def carousel(p, name, handle):
    sc = p["scenes"]; C = p["comments"]
    chunks = [C[i:i+3] for i in range(0, len(C), 3)]
    if len(chunks) == 2 and len(chunks[1]) == 1 and len(C) == 4: chunks = [C[:2], C[2:]]
    n = 1 + len(sc) + len(chunks) + 2
    bg = ["blue", "", "blue", ""]
    S = [f'<section class="s"><div class="logo">🌏 {name}</div>{cover_inner(p)}<div class="real">{REAL}</div><div class="foot">{handle}</div></section>']
    for i, s in enumerate(sc):
        S.append(f'''<section class="s {bg[i]}"><div class="logo">🌏 {name}</div><div class="pg">{2+i}/{n}</div>
  <div class="t w" style="font-size:76px;margin-bottom:40px">{s["title"]}</div>
  {stage(s)}<div class="nar">{s["nar"]}</div>
  <div class="foot">{handle}</div></section>''')
    for k, ch in enumerate(chunks):
        num = "①②③"[k] if len(chunks) > 1 else ""
        S.append(f'''<section class="s {"blue" if k % 2 == 0 else ""}"><div class="logo">🌏 {name}</div><div class="pg">{2+len(sc)+k}/{n}</div>
  <div class="t y" style="font-size:80px;margin-bottom:44px">この話に海外は…{num}</div>
  {"".join(cm2(*c) for c in ch)}<div class="foot">{handle}</div></section>''')
    S.append(stat(p, n, name, handle))
    S.append(f'''<section class="s yel"><div class="logo">🌏 {name}</div><div class="pg">{n}/{n}</div>
  <div class="p" style="padding:56px;margin-top:40px"><div style="font-size:60px;font-weight:900;line-height:1.5">{p["cta"]}</div>
  <div style="font-size:40px;font-weight:900;color:#ff3d5a;margin-top:26px">💬 コメントで教えて！</div></div>
  <div style="font-size:42px;font-weight:900;line-height:1.8;margin-top:50px">📌 保存して友だちにシェア<br>🌏 海外のほっこり話を毎日お届け</div>
  <div style="margin-top:40px"><span class="btn">フォローする</span></div>
  <div style="position:absolute;right:50px;bottom:60px">{guy("happy",300)}</div>
  <div class="foot" style="color:#111;-webkit-text-stroke:0">{handle}</div></section>''')
    return f'<!DOCTYPE html><html lang="ja"><head><meta charset="utf-8"><style>{CSS}</style></head><body>{"".join(S)}</body></html>'

def reel_pages(p, name, handle, credit=""):
    C, sc = p["comments"], p["scenes"]
    P = [f'<section class="s" style="height:1920px"><div class="logo" style="top:200px">🌏 {name}</div>{cover_inner(p, tall=True)}<div class="real" style="top:206px">{REAL}</div><div class="foot" style="bottom:300px">{handle}</div></section>']
    bg = ["blue", "", "blue", ""]
    for i, s in enumerate(sc):
        P.append(f'''<section class="s {bg[i % 4]}" style="height:1920px;padding-top:330px"><div class="logo" style="top:200px">🌏 {name}</div><div class="real" style="top:206px">{REAL}</div>
  <div class="t w" style="font-size:76px;margin-bottom:40px">{s["title"]}</div>
  {stage(s)}<div class="nar">{s["nar"]}</div>
  <div class="foot" style="bottom:300px">{handle}</div></section>''')
    head = f'<div class="hd"><div class="logo">🌏 {name}</div><h1>{p["chat_title"]}</h1></div>'
    for k in range(1, len(C) + 1):
        rows = "".join(f'<div class="row{" r" if i%2 else ""}{" new" if i==k-1 else ""}"><div class="fl">{f}</div><div class="bb"><small>{n}</small>{t}</div></div>' for i, (f, n, t) in enumerate(C[:k]))
        P.append(f'<section class="chat">{head}<div class="list">{rows}</div></section>')
    P.append(stat(p, 0, name, handle, tall=True))
    cr = f'<div style="position:absolute;left:0;right:0;bottom:330px;text-align:center;font-size:28px;font-weight:700">{credit}</div>' if credit else ""
    P.append(f'''<section class="s yel" style="height:1920px"><div class="logo" style="top:200px">🌏 {name}</div>
  <div class="p" style="position:absolute;left:70px;right:70px;top:420px;padding:56px"><div style="font-size:64px;font-weight:900;line-height:1.5">{p["cta"]}</div>
  <div style="font-size:42px;font-weight:900;color:#ff3d5a;margin-top:26px">💬 コメントで教えて！</div></div>
  <div style="position:absolute;left:0;right:0;top:960px;text-align:center">{guy("happy",380)}</div>{cr}</section>''')
    return f'<!DOCTYPE html><html lang="ja"><head><meta charset="utf-8"><style>{CSS}{RC}</style></head><body>{"".join(P)}</body></html>'

