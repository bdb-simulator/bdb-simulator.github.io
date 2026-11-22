"""입상 덱 샘플을 시뮬레이터에 넣는다.

data/decks_winning.json (공식 사이트 입상 덱) 중 samples 목록의 덱을 골라,
그 덱에 쓰인 카드를 data/cards.json에서 찾아 시뮬레이터 카드 정의로 바꾼 뒤
simulator/index.html 의 /*GEN-SAMPLES-START*/ ~ /*GEN-SAMPLES-END*/ 사이에 넣는다.

자동 처리: 코스트, 색, 파워, 히트, 속성, 칭호, 에이스, 버스터/샷,
          아이콘 능력(조건 x 효과), 브라이트.
나머지 텍스트 능력은 카드 설명에 원문을 보여 주고 수동 조작으로 처리한다.

  python collector/build_samples.py
"""
import json, re, sys, unicodedata
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(Path(__file__).resolve().parent))
from translate_rules import rule_translate
from parse_effects import parse_card
_KO = (json.load(open(ROOT / 'db' / 'ko_lines.json', encoding='utf-8'))['lines'] if (ROOT / 'db' / 'ko_lines.json').exists() else {})


def ko(line):
    """한국어 번역: 번역 DB 우선, 없으면 정형 문장 규칙, 그래도 없으면 None"""
    return _KO.get(line) or rule_translate(line)
CARDS = ROOT / 'data' / 'cards.json'
DECKS = ROOT / 'data' / 'decks_winning.json'
HTML = ROOT / 'simulator' / 'index.html'


def norm(t):
    return unicodedata.normalize('NFKC', t).replace('スぺード', 'スペード').replace('パワーえ', 'パワー')


def parse_icon(line):
    """아이콘 능력 한 줄 -> ('icon', {cond, eff}) | ('bright', {...}) | None"""
    t = norm(line)
    m = re.fullmatch(r'【ブライト(\d+):(.+?)】', t)
    if m:
        return 'bright', {'attrs': m.group(2).split('/'), 'amount': int(m.group(1))}
    kw = {'デコイ': 'decoy', 'ブリッツ': 'blitz', 'バーサーク': 'berserk'}
    m = re.fullmatch(r'【(デコイ|ブリッツ|バーサーク)】', t)
    if m:
        return 'icon', {'cond': 'always', 'eff': kw[m.group(1)]}
    m = re.fullmatch(r'【スカウト(\d):(登場|ドロップ|バトル)時】', t)
    if m:
        return 'icon', {'cond': {'登場': 'enter', 'ドロップ': 'drop', 'バトル': 'battle'}[m.group(2)], 'eff': 'scout' + m.group(1)}
    if '自' in t[:3] and '時' in t:
        cond = 'enter' if '登場した時' in t else 'drop' if 'ドロップした時' in t else 'battle' if 'バトルする時' in t else None
        m = re.search(r'スカウト(\d)', t)
        eff = f'scout{m.group(1)}' if m else None
        if not eff:
            m = re.search(r'(\d)枚引く', t)
            eff = f'draw{m.group(1)}' if m else None
        if not eff and 'ライフの先頭' in t:
            eff = 'life1'
        return ('icon', {'cond': cond, 'eff': eff}) if cond and eff else None
    cond = ('terr' if 'テリトリー' in t else 'redzone' if 'レッドゾーン' in t
            else 'oppTurn' if '相手のターン中' in t else 'myTurn' if 'あなたのターン中' in t else None)
    eff = None
    m = re.search(r'パワーを\+(\d+)', t)
    if m and m.group(1) in ('3000', '5000'):
        eff = 'pow' + m.group(1)[0]
    m = re.search(r'ヒットを\+(\d)', t)
    if m:
        eff = 'hit' + m.group(1)
    m = re.search(r'【(デコイ|ブリッツ|バーサーク)】を得る', t)
    if m:
        eff = kw[m.group(1)]
    return ('icon', {'cond': cond, 'eff': eff}) if cond and eff else None


_LAND = set(json.load(open(ROOT / 'data' / 'territory_landscape.json', encoding='utf-8'))['ids']) if (ROOT / 'data' / 'territory_landscape.json').exists() else set()


def to_def(c):
    d = {'jp': c['id'], 'name': c['name'], 'color': c['color'], 'type': c['type'], 'cost': c['cost'],
         'attr': c.get('attr') or [], 'titles': c.get('titles') or [], 'icons': [], 'gen': 1}
    m = re.search(r'/card/([0-9a-f]+)/image_path\.png\?(\d+)', c.get('img') or '')
    if m:
        d['im'] = m.group(1) + '?' + m.group(2)   # 공식 이미지 주소 (게시 페이지 밖에서 열 때만 사용)
    if c['type'] == 'unit':
        d['power'] = c.get('power') or 0
        d['hit'] = c.get('hit') or 0
        if c.get('sub') == 'ace':
            d['sub'] = 'ace'
    if c.get('trigger'):
        d['icon'] = c['trigger']
    text, rest, in_icon = [], [], False
    for line in c.get('text') or []:
        if line.strip() == '・アイコン能力':
            in_icon = True
            continue
        if in_icon:
            r = parse_icon(line)
            if r and r[0] == 'bright':
                d['bright'] = r[1]
                continue
            if r:
                d['icons'].append(r[1])
                continue
        rest.append(line)
    if c['type'] == 'territory' and c['id'] in _LAND:
        d['land'] = 1   # 앞면 그림이 가로
    if c['type'] == 'territory':
        d['tfx'] = {'text': ' / '.join(rest) or '(효과 없음)'}
        k = [ko(x) for x in rest]
        if rest and all(k):
            d['tfx']['ko'] = ' / '.join(k)
    else:
        text = rest
    if text:
        d['text'] = text
        d['manual'] = 1
        k = [ko(x) for x in text]
        if any(k):
            d['ko'] = k
    ab, done = parse_card(d)
    if ab:
        d['ab'] = ab
    if done:
        d['al'] = sorted(done)
    nlines = len(d.get('text') or []) if c['type'] != 'territory' else len([x for x in d['tfx']['text'].split(' / ') if x != '(효과 없음)'])
    if d.get('manual') and len(done) >= nlines:
        del d['manual']   # 모든 줄 자동 처리
    if not d['icons']:
        del d['icons']
    if not d['attr']:
        del d['attr']
    if not d['titles']:
        del d['titles']
    return d


KW_NAMES = ('ブライト', 'デコイ', 'ブリッツ', 'スキル')
NAME_KEYS = ('name', 'nameEq')
LIST_NAME_KEYS = ('nameAny',)
TITLE_KEYS = ('title', 'terrTitle')
LIST_TITLE_KEYS = ('titleAny', 'terrTitleAny')


def fold(t):
    """반각/전각·대소문자 차이를 무시한 비교용 문자열"""
    return unicodedata.normalize('NFKC', t).lower()


def fix_refs(defs):
    """능력 데이터의 카드명·칭호·속성 표기를 실제 카드 데이터 표기에 맞춤
    (원문 「いざ調合!」 대 카드명 「いざ調合！」, 「ANGEL PLAYER」 대 칭호 「Angel Player」, 속성 「スペード/ハート」 묶음 등)"""
    names = [d['name'] for d in defs.values()]
    titles = sorted({t for d in defs.values() for t in d.get('titles', [])})
    tmap = {fold(t): t for t in titles}
    def fix_name(n):
        if not isinstance(n, str) or any(n in x for x in names):
            return n
        f = fold(n)
        for x in names:
            i = fold(x).find(f)
            if i >= 0 and len(fold(x)) == len(x):
                return x[i:i + len(n)]
        return n
    def fix_title(t):
        if not isinstance(t, str) or t in titles:
            return t
        if fold(t) in tmap:
            return tmap[fold(t)]
        near = [x for x in titles if len(x) == len(t) and sum(a != b for a, b in zip(x, t)) == 1]   # 원문 오탈자 (生命繊維 → 칭호 生命戦維)
        return near[0] if len(near) == 1 else t
    fixed = []
    def walk(x, cid):
        if isinstance(x, list):
            for y in x:
                walk(y, cid)
        elif isinstance(x, dict):
            if isinstance(x.get('name'), str) and not any(x['name'] in n for n in names) and x['name'] in KW_NAMES:
                v = x.pop('name')   # 「【ブライト】を持つ」를 카드명으로 읽은 것
                if v == 'ブライト': x['bright'] = 1
                else: x['kwText'] = v
                fixed.append((cid, 'name→키워드', v, x))
            for k, v in list(x.items()):
                nv = v
                if k in NAME_KEYS: nv = fix_name(v)
                elif k in LIST_NAME_KEYS and isinstance(v, list): nv = [fix_name(n) for n in v]
                elif k in TITLE_KEYS: nv = fix_title(v)
                elif k in LIST_TITLE_KEYS and isinstance(v, list): nv = [fix_title(t) for t in v]
                elif k == 'attr' and isinstance(v, list) and any('/' in a for a in v if isinstance(a, str)):
                    nv = [b for a in v for b in a.split('/')]
                if nv != v:
                    x[k] = nv
                    fixed.append((cid, k, v, nv))
                walk(x[k], cid)
    for cid, d in defs.items():
        walk(d.get('ab', []), cid)
    for f in fixed:
        print('표기 맞춤:', *f)


# 사이트 데이터에 칭호가 빠진 테리토리: 카드 그림(개방면 오른쪽 칭호 마크)을 보고 채움
TERR_TITLES = {
    '2717': ['冴えカノ'], '2723': ['冴えカノ'], '2729': ['blessing software'], '2735': ['blessing software'],
    '4815': ['怪異譚'],
    '5002': ['恋愛は戦!!'], '5029': ['告白'], '5033': ['告白'], '5037': ['秀知院学園'], '5049': ['秀知院学園'],
}


def fill_terr_titles(defs):
    for cid, d in defs.items():
        if d.get('type') == 'territory' and not d.get('titles') and cid in TERR_TITLES:
            d['titles'] = list(TERR_TITLES[cid])
    for cid, d in defs.items():   # 다른 그림 판은 기본 카드의 칭호를 물려받음
        b = str(d.get('b', ''))
        if d.get('type') == 'territory' and not d.get('titles') and defs.get(b, {}).get('titles'):
            d['titles'] = list(defs[b]['titles'])
    left = [k for k, d in defs.items() if d.get('type') == 'territory' and not d.get('titles')]
    if left:
        print('칭호 없는 테리토리:', left)


def export_db(cards):
    """덱 편성용 전체 카드 정의 -> simulator/cards_db.json (게시 페이지에서 cards_db.json 으로 불러옴)"""
    collabs, defs, base = [], {}, []
    for cid in sorted(cards):
        c = cards[cid]
        d = to_def(c)
        cn = c.get('collabName') or ''
        if cn not in collabs:
            collabs.append(cn)
        d['cb'] = collabs.index(cn)
        if c.get('rarity'):
            d['r'] = c['rarity']
        if c.get('base') and c['base'] != cid:
            d['b'] = c['base']
        else:
            base.append(cid)
        defs[str(cid)] = d
    fill_terr_titles(defs)
    fix_refs(defs)
    asks = [k for k, d in defs.items() if '"askIf"' in json.dumps(d.get('ab', []))]
    if asks:   # 조건 충족을 플레이어에게 묻는 단계는 만들지 않음
        raise SystemExit(f'조건 충족을 묻는 단계가 생성됨 (해석기 수정 필요): {asks[:20]}')
    out = ROOT / 'simulator' / 'cards_db.json'
    out.write_text(json.dumps({'v': 1, 'collabs': collabs, 'base': base, 'defs': defs}, ensure_ascii=False, separators=(',', ':')), encoding='utf-8')
    print(f'전체 카드 {len(defs)}장 (기본 {len(base)}종) -> {out.name} {out.stat().st_size // 1024}KB')
    return defs


def main():
    cards = {c['id']: c for c in json.load(open(CARDS, encoding='utf-8'))}
    dbdefs = export_db(cards)
    src = json.load(open(DECKS, encoding='utf-8'))
    pick = src.get('samples') or [d['hashid'] for d in src['decks']]
    decks = {d['hashid']: d for d in src['decks']}
    defs, out = {}, []
    for h in pick:
        dk = decks[h]
        cs = dk['cards']
        terr = [c for c in cs if cards[c[0]]['type'] == 'territory']
        if len(terr) != 1:
            print('테리토리 개수 이상, 건너뜀:', h, file=sys.stderr)
            continue
        for cid, _ in cs:
            defs[str(cid)] = {k: v for k, v in dbdefs[str(cid)].items() if k not in ('cb', 'r', 'b')}   # 표기 맞춤·칭호 보충이 끝난 정의
        main_ = [[str(cid), n] for cid, n in cs if cards[cid]['type'] != 'territory']
        tc = cards[terr[0][0]]
        out.append({'key': 'w' + h, 'label': dk['name'], 'date': dk['date'], 'territory': str(terr[0][0]),
                    'main': main_, 'collab': tc.get('collabName', '')})
    block = ('/*GEN-SAMPLES-START*/\n'
             '/* 자동 생성: collector/build_samples.py — 공식 사이트 입상 덱과 그 카드 */\n'
             f'const GEN_DEFS = {json.dumps(defs, ensure_ascii=False, separators=(",", ":"))};\n'
             f'const GEN_DECKS = {json.dumps(out, ensure_ascii=False, separators=(",", ":"))};\n'
             '/*GEN-SAMPLES-END*/')
    html = HTML.read_text(encoding='utf-8')
    html2 = re.sub(r'/\*GEN-SAMPLES-START\*/.*?/\*GEN-SAMPLES-END\*/', lambda m: block, html, flags=re.S)
    assert html2 != html or block in html, '표시(GEN-SAMPLES) 위치를 찾지 못했습니다'
    HTML.write_text(html2, encoding='utf-8')
    # 조건 충족을 플레이어에게 묻는 단계는 만들지 않음: 생기면 데이터 생성 실패
    asks = [k for k, d in defs.items() if '"askIf"' in json.dumps(d.get('ab', []))]
    if asks:
        raise SystemExit(f'조건 충족을 묻는 단계가 생성됨 (해석기 수정 필요): {asks[:20]}')
    manual = sum(1 for d in defs.values() if d.get('manual'))
    print(f'덱 {len(out)}개, 카드 {len(defs)}종 (텍스트 능력 수동 {manual}종), {len(block) // 1024}KB')


if __name__ == '__main__':
    main()
