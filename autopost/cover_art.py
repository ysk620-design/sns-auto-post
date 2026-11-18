import html
import math
import random

"""表紙に入れるオリジナルのイラスト（cover の "art" で指定）。

特定の作品・キャラクター・ロゴに似せない、汎用のモチーフだけを描く。
  food      チュロス・ソフトクリーム・ターキーレッグと値段の札（下側）。札の文字は art_labels で変えられる
  ticket    表紙全体を家族の年パス券に見立てる（明るい券の上に文字をのせる）
  park      観覧車・ジェットコースター・家族（下側）
  calendar  カレンダーと積んだ硬貨（右下）
色はアカウントの theme に合わせて置きかえる。
"""
GOLD="#efc75e"; ACC="#c9932a"; CREAM="#f7f4ec"; DARK="#1d3c32"; MINT="#5fb39a"; CORAL="#e8806a"; SKY="#7cc3e8"

def family(x, y, s=1.0, fill=CREAM):
    # 手をつないだ4人家族のシルエット（大人2・子ども2）
    def person(cx, h, r):
        return (f'<circle cx="{cx}" cy="{y-h-r}" r="{r}" fill="{fill}"/>'
                f'<rect x="{cx-r*0.95}" y="{y-h+r*0.15}" width="{r*1.9}" height="{h*0.62}" rx="{r*0.9}" fill="{fill}"/>'
                f'<rect x="{cx-r*0.75}" y="{y-h*0.45}" width="{r*0.6}" height="{h*0.45}" rx="{r*0.3}" fill="{fill}"/>'
                f'<rect x="{cx+r*0.15}" y="{y-h*0.45}" width="{r*0.6}" height="{h*0.45}" rx="{r*0.3}" fill="{fill}"/>')
    ppl = [(0,150,26),(78,98,20),(140,82,18),(205,150,26)]
    out = f'<g transform="translate({x},{0}) scale({s}) " >'
    out=''
    g=''
    for dx,h,r in ppl:
        g+=person(x+dx*s, h*s, r*s)
    # つないだ手
    g+=f'<path d="M{x+20*s} {y-95*s} Q{x+50*s} {y-70*s} {x+62*s} {y-62*s} M{x+95*s} {y-62*s} Q{x+110*s} {y-55*s} {x+124*s} {y-55*s} M{x+156*s} {y-55*s} Q{x+175*s} {y-70*s} {x+186*s} {y-95*s}" stroke="{fill}" stroke-width="{9*s}" fill="none" stroke-linecap="round"/>'
    return g

def balloon(x,y,r,c):
    return (f'<path d="M{x} {y+r} q-10 40 6 80" stroke="{CREAM}" stroke-width="3" fill="none" opacity=".7"/>'
            f'<ellipse cx="{x}" cy="{y}" rx="{r*0.85}" ry="{r}" fill="{c}"/>'
            f'<ellipse cx="{x-r*0.3}" cy="{y-r*0.35}" rx="{r*0.18}" ry="{r*0.28}" fill="#fff" opacity=".45"/>'
            f'<path d="M{x-6} {y+r+6} l6 -8 l6 8z" fill="{c}"/>')

def park_skyline():
    # 観覧車・ジェットコースター・旗・風船・家族（汎用の遊園地）
    w=1080; base=1350
    spokes=''.join(f'<line x1="830" y1="930" x2="{830+150*__import__("math").cos(a*__import__("math").pi/6):.1f}" y2="{930+150*__import__("math").sin(a*__import__("math").pi/6):.1f}" stroke="{GOLD}" stroke-width="5"/>' for a in range(12))
    import math
    cabins=''.join(f'<rect x="{830+150*math.cos(a*math.pi/6)-14:.1f}" y="{930+150*math.sin(a*math.pi/6)-6:.1f}" width="28" height="26" rx="8" fill="{[CORAL,SKY,MINT,GOLD][a%4]}"/>' for a in range(12))
    flags=''.join(f'<path d="M{100+i*60} {1040+ (i%2)*10} l30 0 l-15 32z" fill="{[CORAL,GOLD,SKY,MINT][i%4]}"/>' for i in range(8))
    return f'''
<svg class="art" viewBox="0 0 1080 1350" xmlns="http://www.w3.org/2000/svg">
  <circle cx="830" cy="930" r="150" fill="none" stroke="{GOLD}" stroke-width="8"/>
  {spokes}{cabins}
  <path d="M770 1230 L830 930 L890 1230" stroke="{GOLD}" stroke-width="10" fill="none"/>
  <path d="M60 1180 C180 1180 220 980 330 980 C420 980 400 1110 470 1110 C540 1110 560 1020 640 1030" stroke="{CORAL}" stroke-width="10" fill="none"/>
  <path d="M60 1205 C180 1205 220 1005 330 1005 C420 1005 400 1135 470 1135 C540 1135 560 1045 640 1055" stroke="{CORAL}" stroke-width="6" fill="none" opacity=".7"/>
  {''.join(f'<line x1="{x}" y1="{y}" x2="{x}" y2="1240" stroke="{CORAL}" stroke-width="5" opacity=".6"/>' for x,y in [(150,1150),(250,1030),(330,1000),(420,1060),(520,1100),(600,1035)])}
  <path d="M100 1035 Q340 1080 580 1030" stroke="{CREAM}" stroke-width="3" fill="none" opacity=".6"/>
  {flags}
  {balloon(960,1060,34,CORAL)}{balloon(1010,1110,28,SKY)}
  <rect x="0" y="1238" width="1080" height="112" fill="#000" fill-opacity=".22"/>
  {family(380,1240,1.0)}
</svg>'''

def churro(x,y,ang,s=1):
    ridges=''.join(f'<line x1="{-150}" y1="{dy}" x2="{150}" y2="{dy}" stroke="#b5701c" stroke-width="3" opacity=".7"/>' for dy in (-12,0,12))
    sugar=''.join(f'<circle cx="{cx}" cy="{cy}" r="3" fill="#fff" opacity=".8"/>' for cx,cy in [(-120,-8),(-80,6),(-40,-10),(0,8),(40,-4),(80,10),(110,-8),(-100,10),(60,-12)])
    return (f'<g transform="translate({x},{y}) rotate({ang}) scale({s})">'
            f'<rect x="-160" y="-22" width="320" height="44" rx="22" fill="#e2a04a"/>{ridges}{sugar}'
            f'<path d="M-170 -34 h120 l-10 68 h-100z" fill="{CREAM}"/><path d="M-170 -34 h120 l-10 68 h-100z" fill="none" stroke="{CORAL}" stroke-width="5"/>'
            f'<line x1="-150" y1="-34" x2="-150" y2="34" stroke="{CORAL}" stroke-width="10" opacity=".9"/><line x1="-110" y1="-34" x2="-115" y2="34" stroke="{CORAL}" stroke-width="10" opacity=".9"/>'
            '</g>')

def turkey(x,y,ang,s=1):
    return (f'<g transform="translate({x},{y}) rotate({ang}) scale({s})">'
            f'<path d="M-40 -90 C40 -120 120 -40 70 30 C40 70 0 70 -20 50 L-60 90 C-55 110 -80 125 -92 110 C-110 118 -125 95 -108 85 L-70 45 C-95 10 -95 -60 -40 -90z" fill="#a8562a"/>'
            f'<path d="M-20 -70 C30 -90 80 -40 55 0" stroke="#d98a4e" stroke-width="12" fill="none" stroke-linecap="round" opacity=".8"/>'
            f'<circle cx="-100" cy="100" r="16" fill="{CREAM}"/><circle cx="-84" cy="114" r="16" fill="{CREAM}"/><path d="M-90 98 L-60 70" stroke="{CREAM}" stroke-width="18" stroke-linecap="round"/>'
            '</g>')

def softserve(x,y,s=1):
    return (f'<g transform="translate({x},{y}) scale({s})">'
            f'<path d="M-50 0 L0 130 L50 0z" fill="#e2a04a"/><path d="M-36 20 L30 20 M-26 50 L22 50 M-16 80 L14 80" stroke="#b5701c" stroke-width="4"/>'
            f'<path d="M-62 2 C-70 -30 -40 -40 -30 -42 C-40 -80 20 -90 22 -60 C40 -100 0 -130 0 -130 C40 -120 60 -80 40 -50 C70 -45 75 -10 60 2z" fill="{CREAM}"/>'
            '</g>')

def tag(x,y,text,ang=-6):
    return (f'<g transform="translate({x},{y}) rotate({ang})"><rect x="-95" y="-34" width="190" height="68" rx="34" fill="{CORAL}"/>'
            f'<text x="0" y="13" font-size="36" font-weight="900" fill="#fff" text-anchor="middle" font-family="Noto Sans CJK JP">{text}</text></g>')

def food(labels=('500円〜', '1,000円〜')):
    sparkles=''.join(f'<path d="M{x} {y-18} L{x+5} {y-5} L{x+18} {y} L{x+5} {y+5} L{x} {y+18} L{x-5} {y+5} L{x-18} {y} L{x-5} {y-5}z" fill="{GOLD}"/>' for x,y in [(150,880),(990,840),(650,840),(90,1060)])
    return f'''
<svg class="art" viewBox="0 0 1080 1350" xmlns="http://www.w3.org/2000/svg">
  <ellipse cx="540" cy="1200" rx="660" ry="260" fill="#000" fill-opacity=".22"/>
  {churro(300,1010,-28,1.05)}
  {turkey(760,1000,8,1.25)}
  {softserve(540,1000,0.95)}
  {tag(250,1135,html.escape(labels[0]),-8)}{tag(870,1150,html.escape(labels[1]),6)}
  {sparkles}
</svg>'''

def ticket_bg():
    holes=''.join(f'<circle cx="{x}" cy="1010" r="7" fill="{DARK}" opacity=".25"/>' for x in range(150,940,34))
    return f'''
<svg class="art back" viewBox="0 0 1080 1350" xmlns="http://www.w3.org/2000/svg">
  <path d="M70 150 H1010 V1010 a46 46 0 0 0 0 92 V1240 H70 V1102 a46 46 0 0 0 0 -92z" fill="{CREAM}"/>
  <path d="M70 150 H1010 V230 H70z" fill="{GOLD}"/>
  <text x="110" y="208" font-size="40" font-weight="900" fill="{DARK}" font-family="Noto Sans CJK JP" letter-spacing="6">ANNUAL PASS ｜ FAMILY</text>
  {holes}
  {family(130,1215,0.62,DARK)}
  <text x="400" y="1150" font-size="34" font-weight="700" fill="{DARK}" opacity=".7" font-family="Noto Sans CJK JP">ADULT ×2　CHILD ×2</text>
  <text x="400" y="1205" font-size="30" fill="{DARK}" opacity=".5" font-family="Noto Sans CJK JP">VALID 1 YEAR</text>
  <circle cx="900" cy="1160" r="54" fill="none" stroke="{CORAL}" stroke-width="6" opacity=".8"/>
  <text x="900" y="1172" font-size="34" font-weight="900" fill="{CORAL}" text-anchor="middle" font-family="Noto Sans CJK JP" opacity=".85">OK!</text>
</svg>'''

def calendar_coins():
    cells=''
    import random; random.seed(3)
    for r in range(4):
        for c in range(7):
            cx=640+c*52; cy=1000+r*48
            mark = random.random()<0.35
            cells+=f'<rect x="{cx}" y="{cy}" width="40" height="36" rx="8" fill="{GOLD if mark else "#e8e2d2"}"/>'
            if mark: cells+=f'<path d="M{cx+10} {cy+18} l7 7 l13 -14" stroke="{DARK}" stroke-width="5" fill="none" stroke-linecap="round"/>'
    coins=''.join(f'<ellipse cx="180" cy="{1230-i*26}" rx="80" ry="24" fill="{GOLD}" stroke="{ACC}" stroke-width="5"/>' for i in range(6))
    coins+=''.join(f'<ellipse cx="350" cy="{1230-i*26}" rx="80" ry="24" fill="{GOLD}" stroke="{ACC}" stroke-width="5"/>' for i in range(4))
    return f'''
<svg class="art" viewBox="0 0 1080 1350" xmlns="http://www.w3.org/2000/svg">
  <rect x="610" y="900" width="400" height="320" rx="28" fill="{CREAM}" transform="rotate(4 810 1060)"/>
  <g transform="rotate(4 810 1060)">
  <rect x="610" y="900" width="400" height="80" rx="28" fill="{CORAL}"/><rect x="610" y="950" width="400" height="30" fill="{CORAL}"/>
  <text x="810" y="958" font-size="42" font-weight="900" fill="#fff" text-anchor="middle" font-family="Noto Sans CJK JP">いつでもOK</text>
  {cells}
  <circle cx="680" cy="900" r="12" fill="{DARK}"/><circle cx="940" cy="900" r="12" fill="{DARK}"/>
  </g>
  {coins}
  <text x="350" y="1168" font-size="34" font-weight="900" fill="{ACC}" text-anchor="middle" font-family="Noto Sans CJK JP">¥</text>
</svg>'''


ARTS = ("food", "ticket", "park", "calendar")
# 文字を上に寄せるか、明るい券の上に文字をのせるか
ART_CLASS = {"food": "withart top", "ticket": "withart top light", "park": "withart top", "calendar": "withart top"}


def svg(name: str, theme: dict, labels=None) -> str:
    if name == "food":
        out = food(tuple(labels) if labels and len(labels) == 2 else ("500円〜", "1,000円〜"))
    else:
        out = {"ticket": ticket_bg, "park": park_skyline, "calendar": calendar_coins}[name]()
    # 基本の色（厳選お得の配色）をアカウントの配色に置きかえる
    for default, key in ((DARK, "main"), (CREAM, "base"), (GOLD, "accent_soft"), (ACC, "accent")):
        out = out.replace(default, theme.get(key, default))
    return out
