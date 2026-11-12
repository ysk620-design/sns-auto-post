# オリジナルキャラ「旅する外国人」と小物アイコン（SVG）
K = '#222'

def guy(mood="wow", w=300, hair="#ffc93c", shirt="#35c5f0"):
    """mood: wow / happy / love / think"""
    eyes = {
        "wow":  '<ellipse cx="118" cy="150" rx="17" ry="22" fill="#fff" stroke="#222" stroke-width="5"/><ellipse cx="182" cy="150" rx="17" ry="22" fill="#fff" stroke="#222" stroke-width="5"/><circle cx="118" cy="154" r="8" fill="#222"/><circle cx="182" cy="154" r="8" fill="#222"/>'
                '<path d="M96 112 Q118 98 138 110 M162 110 Q182 98 204 112" stroke="#222" stroke-width="6" fill="none" stroke-linecap="round"/>',
        "happy":'<path d="M102 152 Q118 132 134 152 M166 152 Q182 132 198 152" stroke="#222" stroke-width="7" fill="none" stroke-linecap="round"/>',
        "love": '<path d="M118 168 L100 150 A10 10 0 0 1 118 136 A10 10 0 0 1 136 150 Z" fill="#ff4f7b" stroke="#222" stroke-width="4"/><path d="M182 168 L164 150 A10 10 0 0 1 182 136 A10 10 0 0 1 200 150 Z" fill="#ff4f7b" stroke="#222" stroke-width="4"/>',
        "sad":  '<path d="M100 146 Q118 158 136 146 M164 146 Q182 158 200 146" stroke="#222" stroke-width="7" fill="none" stroke-linecap="round"/><path d="M104 120 L134 132 M196 120 L166 132" stroke="#222" stroke-width="6" stroke-linecap="round"/><path d="M110 160 Q100 185 110 196 Q122 185 110 160Z" fill="#7cc7ff" stroke="#222" stroke-width="3"/>',
        "think":'<circle cx="118" cy="152" r="8" fill="#222"/><circle cx="182" cy="152" r="8" fill="#222"/><path d="M100 126 L136 132 M164 126 Q182 116 200 124" stroke="#222" stroke-width="6" fill="none" stroke-linecap="round"/>',
    }[mood]
    mouth = {
        "wow":  '<ellipse cx="150" cy="205" rx="20" ry="26" fill="#3a1010" stroke="#222" stroke-width="5"/><ellipse cx="150" cy="218" rx="12" ry="8" fill="#ff6b6b"/>',
        "happy":'<path d="M118 190 Q150 236 182 190 Z" fill="#3a1010" stroke="#222" stroke-width="5" stroke-linejoin="round"/><path d="M134 212 Q150 224 166 212 Q150 204 134 212" fill="#ff6b6b"/>',
        "love": '<path d="M122 192 Q150 228 178 192" stroke="#222" stroke-width="6" fill="none" stroke-linecap="round"/>',
        "sad":  '<path d="M124 214 Q150 192 176 214" stroke="#222" stroke-width="6" fill="none" stroke-linecap="round"/>',
        "think":'<path d="M132 205 Q150 196 170 207" stroke="#222" stroke-width="6" fill="none" stroke-linecap="round"/>',
    }[mood]
    if mood in ("wow", "happy"):   # 両手バンザイ
        arms = ('<path d="M92 290 L36 196" stroke="#222" stroke-width="30" stroke-linecap="round"/><path d="M92 290 L36 196" stroke="#35c5f0" stroke-width="18" stroke-linecap="round"/>'
                '<path d="M208 290 L264 196" stroke="#222" stroke-width="30" stroke-linecap="round"/><path d="M208 290 L264 196" stroke="#35c5f0" stroke-width="18" stroke-linecap="round"/>'
                '<circle cx="32" cy="186" r="20" fill="#ffd9b8" stroke="#222" stroke-width="5"/><circle cx="268" cy="186" r="20" fill="#ffd9b8" stroke="#222" stroke-width="5"/>')
    elif mood == "love":           # 片手でグッド
        arms = ('<path d="M214 300 L262 236" stroke="#222" stroke-width="30" stroke-linecap="round"/><path d="M214 300 L262 236" stroke="#35c5f0" stroke-width="18" stroke-linecap="round"/>'
                '<rect x="244" y="204" width="40" height="40" rx="12" fill="#ffd9b8" stroke="#222" stroke-width="5"/><rect x="252" y="176" width="16" height="36" rx="8" fill="#ffd9b8" stroke="#222" stroke-width="5"/>')
    elif mood == "sad":            # 腕を下げる
        arms = ('<path d="M96 300 L70 336" stroke="#222" stroke-width="30" stroke-linecap="round"/><path d="M96 300 L70 336" stroke="SHIRT" stroke-width="18" stroke-linecap="round"/>'
                '<path d="M204 300 L230 336" stroke="#222" stroke-width="30" stroke-linecap="round"/><path d="M204 300 L230 336" stroke="SHIRT" stroke-width="18" stroke-linecap="round"/>')
    else:                          # あごに手
        arms = ('<path d="M100 330 Q110 260 140 252" stroke="#222" stroke-width="30" stroke-linecap="round" fill="none"/><path d="M100 330 Q110 260 140 252" stroke="#35c5f0" stroke-width="18" stroke-linecap="round" fill="none"/>'
                '<circle cx="148" cy="246" r="20" fill="#ffd9b8" stroke="#222" stroke-width="5"/>')
    arms = arms.replace("#35c5f0", shirt).replace("SHIRT", shirt)
    return f'''<svg viewBox="0 0 300 340" width="{w}" height="{w*340//300}" xmlns="http://www.w3.org/2000/svg">
<path d="M70 340 Q70 250 150 248 Q230 250 230 340 Z" fill="{shirt}" stroke="#222" stroke-width="6"/>
<path d="M128 252 L150 290 L172 252" fill="#fff" stroke="#222" stroke-width="5" stroke-linejoin="round"/>
{arms}
<circle cx="62" cy="160" r="18" fill="#ffd9b8" stroke="#222" stroke-width="5"/><circle cx="238" cy="160" r="18" fill="#ffd9b8" stroke="#222" stroke-width="5"/>
<circle cx="150" cy="160" r="88" fill="#ffd9b8" stroke="#222" stroke-width="6"/>
<path d="M60 150 Q52 62 150 56 Q248 62 240 150 L222 118 L200 138 L182 104 L158 130 L136 100 L114 134 L96 110 L78 140 Z" fill="{hair}" stroke="#222" stroke-width="6" stroke-linejoin="round"/>
<circle cx="96" cy="190" r="13" fill="#ff9fb4" opacity=".8"/><circle cx="204" cy="190" r="13" fill="#ff9fb4" opacity=".8"/>
{eyes}{mouth}
</svg>'''

def burst(text="WOW!", w=300, fill="#ff4f7b"):
    import math
    pts = []
    for i in range(28):
        r = 140 if i % 2 == 0 else 100
        a = math.pi * 2 * i / 28
        pts.append(f"{150+r*math.cos(a):.0f},{150+r*math.sin(a)*0.8:.0f}")
    return f'''<svg viewBox="0 0 300 300" width="{w}" height="{w}" xmlns="http://www.w3.org/2000/svg">
<polygon points="{' '.join(pts)}" fill="{fill}" stroke="#222" stroke-width="7" stroke-linejoin="round"/>
<text x="150" y="172" text-anchor="middle" font-family="Noto Sans CJK JP" font-weight="900" font-size="56" fill="#fff" stroke="#222" stroke-width="7" stroke-linejoin="round" paint-order="stroke" transform="rotate(-8 150 150)">{text}</text>
</svg>'''

def icon(kind, w=260):
    kind, _, label = kind.partition(":")
    body = {
    "wallet": '''<rect x="30" y="70" width="220" height="150" rx="26" fill="#d98a4e" stroke="#222" stroke-width="7"/>
<path d="M30 110 L250 110" stroke="#222" stroke-width="6"/>
<rect x="170" y="120" width="80" height="56" rx="16" fill="#b86b34" stroke="#222" stroke-width="6"/><circle cx="198" cy="148" r="10" fill="#ffd23f" stroke="#222" stroke-width="5"/>
<rect x="56" y="40" width="120" height="44" rx="6" fill="#9be08b" stroke="#222" stroke-width="6" transform="rotate(-8 116 62)"/>
<path d="M250 40 l8 -20 l8 20 l20 8 l-20 8 l-8 20 l-8 -20 l-20 -8 z" fill="#fff" stroke="#222" stroke-width="4"/>''',
    "wagyu": '''<ellipse cx="140" cy="170" rx="128" ry="62" fill="#fff" stroke="#222" stroke-width="7"/>
<path d="M50 150 Q60 92 140 96 Q232 98 230 150 Q222 196 140 194 Q56 194 50 150 Z" fill="#e8576a" stroke="#222" stroke-width="7"/>
<path d="M80 130 Q110 120 130 140 M150 116 Q170 130 200 124 M90 168 Q130 156 160 176 M176 160 Q196 150 214 164 M110 108 Q120 120 104 130" stroke="#fff" stroke-width="7" fill="none" stroke-linecap="round"/>
<path d="M100 70 Q90 50 104 34 M140 64 Q130 44 144 28 M180 70 Q170 50 184 34" stroke="#222" stroke-width="5" fill="none" stroke-linecap="round" opacity=".6"/>''',
    "sushi": '''<rect x="10" y="180" width="260" height="34" rx="10" fill="#c98a4b" stroke="#222" stroke-width="7"/>
<rect x="30" y="122" width="100" height="62" rx="26" fill="#fff" stroke="#222" stroke-width="6"/>
<path d="M22 132 Q30 92 80 96 Q130 92 138 132 Q80 120 22 132 Z" fill="#ff9a5a" stroke="#222" stroke-width="6"/>
<path d="M48 108 L58 124 M76 102 L84 120 M104 104 L110 122" stroke="#fff" stroke-width="5" stroke-linecap="round"/>
<rect x="150" y="122" width="100" height="62" rx="26" fill="#fff" stroke="#222" stroke-width="6"/>
<path d="M142 132 Q150 92 200 96 Q250 92 258 132 Q200 120 142 132 Z" fill="#d6304a" stroke="#222" stroke-width="6"/>
<path d="M230 50 l8 -20 l8 20 l20 8 l-20 8 l-8 20 l-8 -20 l-20 -8 z" fill="#fff" stroke="#222" stroke-width="4"/>''',
    "watch": '''<rect x="104" y="10" width="72" height="70" rx="12" fill="#2f3b5c" stroke="#222" stroke-width="6"/>
<rect x="104" y="196" width="72" height="66" rx="12" fill="#2f3b5c" stroke="#222" stroke-width="6"/>
<rect x="238" y="124" width="18" height="30" rx="5" fill="#ccd3dd" stroke="#222" stroke-width="5"/>
<circle cx="140" cy="138" r="100" fill="#ccd3dd" stroke="#222" stroke-width="7"/>
<circle cx="140" cy="138" r="80" fill="#5da9e9" stroke="#222" stroke-width="5"/>
<g stroke="#fff" stroke-width="6" stroke-linecap="round"><path d="M140 66 V80 M140 196 V210 M68 138 H82 M198 138 H212"/></g>
<path d="M140 138 L140 92 M140 138 L176 152" stroke="#fff" stroke-width="8" stroke-linecap="round"/><path d="M140 138 L104 176" stroke="#ff4f7b" stroke-width="4" stroke-linecap="round"/>
<circle cx="140" cy="138" r="8" fill="#fff" stroke="#222" stroke-width="3"/>
<path d="M60 70 l8 -20 l8 20 l20 8 l-20 8 l-8 20 l-8 -20 l-20 -8 z" fill="#fff" stroke="#222" stroke-width="4"/>''',
    "ramen": '''<path d="M30 120 H250 Q246 230 140 236 Q34 230 30 120 Z" fill="#ff5a4e" stroke="#222" stroke-width="7"/>
<path d="M30 120 H250" stroke="#222" stroke-width="7"/><path d="M60 136 H220" stroke="#fff" stroke-width="6" stroke-dasharray="14 10"/>
<path d="M90 120 Q100 70 110 120 M130 120 Q140 60 150 120 M170 120 Q180 70 190 120" stroke="#ffe08a" stroke-width="8" fill="none"/>
<path d="M200 30 L120 118 M230 40 L140 118" stroke="#8a5a2b" stroke-width="9" stroke-linecap="round"/>
<circle cx="80" cy="112" r="16" fill="#fff" stroke="#222" stroke-width="5"/><circle cx="80" cy="112" r="7" fill="#ffc93c"/>''',
    "noren": '''<rect x="20" y="30" width="240" height="18" rx="6" fill="#8a5a2b" stroke="#222" stroke-width="6"/>
<path d="M30 48 H250 V200 H30 Z" fill="#d6304a" stroke="#222" stroke-width="7"/>
<path d="M103 48 V200 M177 48 V200" stroke="#222" stroke-width="6"/>
<text x="66" y="150" text-anchor="middle" font-family="Noto Sans CJK JP" font-weight="900" font-size="64" fill="#fff"></text>
<text x="140" y="150" text-anchor="middle" font-family="Noto Sans CJK JP" font-weight="900" font-size="80" fill="#fff">LABEL</text>
<text x="214" y="150" text-anchor="middle" font-family="Noto Sans CJK JP" font-weight="900" font-size="64" fill="#fff"></text>''',
    "question": '''<rect x="40" y="90" width="200" height="140" rx="20" fill="#fff" stroke="#222" stroke-width="7" stroke-dasharray="18 12"/>
<text x="140" y="200" text-anchor="middle" font-family="Noto Sans CJK JP" font-weight="900" font-size="120" fill="#ff3d5a" stroke="#222" stroke-width="5">?</text>''',
    "koban": '''<rect x="40" y="90" width="200" height="150" fill="#f4efe3" stroke="#222" stroke-width="7"/>
<path d="M24 96 L140 30 L256 96 Z" fill="#2f4a8a" stroke="#222" stroke-width="7" stroke-linejoin="round"/>
<rect x="70" y="104" width="140" height="40" rx="6" fill="#fff" stroke="#222" stroke-width="5"/>
<text x="140" y="134" text-anchor="middle" font-family="Noto Sans CJK JP" font-weight="900" font-size="28" fill="#222">KOBAN</text>
<rect x="110" y="160" width="60" height="80" fill="#9ad0ff" stroke="#222" stroke-width="5"/>
<circle cx="140" cy="70" r="12" fill="#ff3d5a" stroke="#222" stroke-width="4"/>''',
    "ball": '''<circle cx="140" cy="146" r="104" fill="#fff" stroke="#222" stroke-width="7"/>
<polygon points="140,104 178,132 164,176 116,176 102,132" fill="#222"/>
<path d="M140 104 V48 M178 132 L232 114 M164 176 L196 226 M116 176 L84 226 M102 132 L48 114" stroke="#222" stroke-width="6"/>
<path d="M120 46 L160 46 L150 60 L130 60Z M226 100 L240 136 L224 130Z M40 136 L54 100 L58 130Z" fill="#222"/>
<path d="M236 40 l8 -20 l8 20 l20 8 l-20 8 l-8 20 l-8 -20 l-20 -8 z" fill="#fff" stroke="#222" stroke-width="4"/>''',
    "trash": '''<path d="M70 96 Q60 230 90 250 H190 Q220 230 210 96 Z" fill="#3a3f4a" stroke="#222" stroke-width="7" stroke-linejoin="round"/>
<path d="M70 96 Q140 70 210 96 L196 70 Q140 52 84 70 Z" fill="#555c6a" stroke="#222" stroke-width="6" stroke-linejoin="round"/>
<path d="M120 60 Q140 20 160 60" fill="none" stroke="#222" stroke-width="7"/>
<path d="M104 140 Q140 128 176 140 M100 190 Q140 178 180 190" stroke="#8a93a6" stroke-width="5" fill="none"/>
<rect x="96" y="150" width="88" height="30" rx="6" fill="#fff" stroke="#222" stroke-width="4"/>
<text x="140" y="174" text-anchor="middle" font-family="Noto Sans CJK JP" font-weight="900" font-size="22" fill="#2b6cff">THANK YOU</text>''',
    "crane": '''<path d="M60 230 H230" stroke="#222" stroke-width="6" stroke-linecap="round" opacity=".3"/>
<polygon points="96,170 150,140 204,170 150,214" fill="#ff8fb1" stroke="#222" stroke-width="7" stroke-linejoin="round"/>
<polygon points="150,150 104,40 170,150" fill="#ffb3c9" stroke="#222" stroke-width="7" stroke-linejoin="round"/>
<polygon points="150,150 214,52 176,160" fill="#ff8fb1" stroke="#222" stroke-width="7" stroke-linejoin="round"/>
<polygon points="110,172 50,92 74,96 126,166" fill="#ff8fb1" stroke="#222" stroke-width="6" stroke-linejoin="round"/>
<polygon points="50,92 30,110 62,104" fill="#ff8fb1" stroke="#222" stroke-width="5" stroke-linejoin="round"/>
<polygon points="190,170 256,110 250,132 200,178" fill="#ff8fb1" stroke="#222" stroke-width="6" stroke-linejoin="round"/>
<path d="M96 170 L204 170" stroke="#222" stroke-width="4"/>
<path d="M232 196 l8 -20 l8 20 l20 8 l-20 8 l-8 20 l-8 -20 l-20 -8 z" fill="#fff" stroke="#222" stroke-width="4"/>''',
    "sandwich": '''<path d="M30 220 L250 220 L140 60 Z" fill="#fff4dc" stroke="#222" stroke-width="7" stroke-linejoin="round"/>
<path d="M58 180 L222 180 L196 142 L84 142 Z" fill="#ffd84d" stroke="#222" stroke-width="6" stroke-linejoin="round"/>
<path d="M90 165 Q100 155 110 165 M140 160 Q150 150 160 160 M180 166 Q188 158 196 166" stroke="#fff" stroke-width="5" fill="none" stroke-linecap="round"/>
<path d="M30 220 L250 220" stroke="#e9c48f" stroke-width="10"/><path d="M30 220 L250 220" stroke="#222" stroke-width="4"/>
<path d="M232 50 l8 -20 l8 20 l20 8 l-20 8 l-8 20 l-8 -20 l-20 -8 z" fill="#fff" stroke="#222" stroke-width="4"/>''',
    "train": '''<rect x="50" y="40" width="180" height="180" rx="34" fill="#e9eef5" stroke="#222" stroke-width="7"/>
<rect x="74" y="66" width="132" height="70" rx="12" fill="#9ad0ff" stroke="#222" stroke-width="6"/>
<rect x="50" y="150" width="180" height="22" fill="#ff3d5a" stroke="#222" stroke-width="5"/>
<circle cx="92" cy="196" r="12" fill="#ffd23f" stroke="#222" stroke-width="5"/><circle cx="188" cy="196" r="12" fill="#ffd23f" stroke="#222" stroke-width="5"/>
<path d="M80 220 L56 260 M200 220 L224 260" stroke="#222" stroke-width="8" stroke-linecap="round"/>''',
    "phone": '''<rect x="80" y="20" width="130" height="240" rx="24" fill="#2f3b5c" stroke="#222" stroke-width="7"/>
<rect x="94" y="46" width="102" height="180" rx="8" fill="#fff" stroke="#222" stroke-width="4"/>
<rect x="104" y="58" width="82" height="22" rx="4" fill="#ff3d5a"/>
<text x="145" y="75" text-anchor="middle" font-family="Noto Sans CJK JP" font-weight="900" font-size="17" fill="#fff">NEWS</text>
<rect x="104" y="92" width="82" height="52" rx="4" fill="#9ad0ff"/>
<path d="M106 162 H184 M106 180 H184 M106 198 H160" stroke="#9aa3b5" stroke-width="7" stroke-linecap="round"/>
<path d="M226 60 Q246 80 226 100 M240 46 Q272 80 240 114" stroke="#222" stroke-width="6" fill="none" stroke-linecap="round"/>''',
    "bag": '''<path d="M60 100 H220 L206 250 H74 Z" fill="#ffd23f" stroke="#222" stroke-width="7" stroke-linejoin="round"/>
<path d="M100 100 Q100 40 140 40 Q180 40 180 100" fill="none" stroke="#222" stroke-width="9"/>
<circle cx="110" cy="80" r="26" fill="#ff5a4e" stroke="#222" stroke-width="5"/><path d="M110 54 Q116 44 126 44" stroke="#3a9a3a" stroke-width="6" fill="none"/>
<rect x="148" y="56" width="40" height="60" rx="8" fill="#fff" stroke="#222" stroke-width="5"/>
<path d="M110 170 l12 12 l24 -26" stroke="#222" stroke-width="8" fill="none" stroke-linecap="round" stroke-linejoin="round"/>''',
    "shinkansen": '''<path d="M14 200 L14 150 Q40 80 150 76 H266 V200 Z" fill="#fff" stroke="#222" stroke-width="7" stroke-linejoin="round"/>
<path d="M56 112 Q90 92 140 92 V126 H50 Z" fill="#2f4a8a" stroke="#222" stroke-width="5" stroke-linejoin="round"/>
<rect x="160" y="96" width="34" height="30" rx="5" fill="#9ad0ff" stroke="#222" stroke-width="4"/><rect x="206" y="96" width="34" height="30" rx="5" fill="#9ad0ff" stroke="#222" stroke-width="4"/>
<path d="M14 168 H266" stroke="#2b6cff" stroke-width="12"/>
<path d="M0 222 H280" stroke="#222" stroke-width="7"/><circle cx="80" cy="208" r="12" fill="#666" stroke="#222" stroke-width="4"/><circle cx="210" cy="208" r="12" fill="#666" stroke="#222" stroke-width="4"/>''',
    "broom": '''<path d="M190 20 L120 160" stroke="#8a5a2b" stroke-width="14" stroke-linecap="round"/>
<path d="M100 150 L150 172 L130 262 Q80 262 46 236 Z" fill="#ffd23f" stroke="#222" stroke-width="7" stroke-linejoin="round"/>
<path d="M76 222 L110 172 M96 240 L126 180 M60 236 L98 166" stroke="#c9a12a" stroke-width="5"/>
<rect x="96" y="140" width="62" height="24" rx="6" fill="#ff3d5a" stroke="#222" stroke-width="5" transform="rotate(24 127 152)"/>
<path d="M220 150 l8 -20 l8 20 l20 8 l-20 8 l-8 20 l-8 -20 l-20 -8 z" fill="#fff" stroke="#222" stroke-width="4"/>
<path d="M226 230 l6 -14 l6 14 l14 6 l-14 6 l-6 14 l-6 -14 l-14 -6 z" fill="#fff" stroke="#222" stroke-width="4"/>''',
    "coffee": '''<ellipse cx="140" cy="236" rx="110" ry="24" fill="#fff" stroke="#222" stroke-width="7"/>
<path d="M60 110 H210 L196 220 Q140 238 84 220 Z" fill="#fff" stroke="#222" stroke-width="7" stroke-linejoin="round"/>
<path d="M208 132 Q256 132 248 172 Q240 204 200 200" fill="none" stroke="#222" stroke-width="9"/>
<ellipse cx="135" cy="112" rx="74" ry="14" fill="#7a4a24" stroke="#222" stroke-width="5"/>
<path d="M150 112 L196 14" stroke="#ff4f7b" stroke-width="14" stroke-linecap="round"/><path d="M150 112 L196 14" stroke="#222" stroke-width="3" stroke-dasharray="2 14"/>
<path d="M90 92 Q80 72 92 56 M120 90 Q110 70 122 54" stroke="#222" stroke-width="5" fill="none" stroke-linecap="round" opacity=".6"/>''',
    }[kind].replace("LABEL", label or "麺")
    return f'<svg viewBox="0 0 280 280" width="{w}" height="{w}" xmlns="http://www.w3.org/2000/svg">{body}</svg>'
