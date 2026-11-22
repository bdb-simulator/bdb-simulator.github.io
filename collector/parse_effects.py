"""카드 텍스트 능력(일본어 원문) -> 시뮬레이터가 실행하는 효과 스크립트.

원문을 문장 조각 단위로 읽어, 아는 조각만으로 끝까지 읽히는 줄만 자동 처리한다.
한 조각이라도 모르면 그 줄은 None (수동 조작으로 남음).

결과 형식 (카드 정의의 ab 배열 한 항목):
  {li:[원문 줄 번호], k:'auto'|'perm'|'play', on:발동 시점, src:'self'|'own'|'ownAce'|'opp',
   if:[조건], once:1, cost:[비용], do:[단계]}
"""
import json
import re
import copy, unicodedata

N = lambda t: unicodedata.normalize('NFKC', t)

# ---------- 대상 묘사 (…ユニット) ----------
_DESC_TOKENS = [
    (r'⁅?(?:ハート|スペード|ダイヤ|クラブ)⁆?(?:か⁅?(?:ハート|スペード|ダイヤ|クラブ)⁆?)+(?:の)?', lambda m, f: f.__setitem__('attr', re.findall('ハート|スペード|ダイヤ|クラブ', m.group(0)))),
    (r'相手の', lambda m, f: f.__setitem__('side', 'opp')),
    (r'、', lambda m, f: None),
    (r'属性(\d)つの', lambda m, f: f.__setitem__('attrN', int(m.group(1)))),
    (r'あなたの', lambda m, f: f.__setitem__('side', 'own')),
    (r'このユニット以外の|他の', lambda m, f: f.__setitem__('notSelf', 1)),
    (r'総?コスト(\d+)以下(?:の|で)', lambda m, f: f.__setitem__('costLE', int(m.group(1)))),
    (r'総?コスト(\d+)以上(?:の|で)', lambda m, f: f.__setitem__('costGE', int(m.group(1)))),
    (r'パワー(\d+)以下(?:の|で)', lambda m, f: f.__setitem__('powLE', int(m.group(1)))),
    (r'パワー(\d+)以上(?:の|で)', lambda m, f: f.__setitem__('powGE', int(m.group(1)))),
    (r'⁅バスターアイコン⁆でない|バスターアイコンでない', lambda m, f: f.__setitem__('notIcon', 'buster')),
    (r'このターンに登場していない', lambda m, f: f.__setitem__('notNew', 1)),
    (r'ヒット(\d+)以下の', lambda m, f: f.__setitem__('hitLE', int(m.group(1)))),
    (r'ヒット(\d+)以上の', lambda m, f: f.__setitem__('hitGE', int(m.group(1)))),
    (r'レストしている|レスト状態の', lambda m, f: f.__setitem__('rested', 1)),
    (r'スタンドしている|スタンド状態の', lambda m, f: f.__setitem__('rested', 0)),
    (r'ダメージを受けている', lambda m, f: f.__setitem__('damaged', 1)),
    (r'エースでない', lambda m, f: f.__setitem__('ace', 0)),
    (r'称号「([^」]+)」(?:の|を持つ)?', lambda m, f: f.__setitem__('title', m.group(1))),
    (r'【スキル】を持つ', lambda m, f: f.__setitem__('skill', 1)),
    (r'(ハート|スペード|ダイヤ|クラブ)か(ハート|スペード|ダイヤ|クラブ)(?:の)?', lambda m, f: f.__setitem__('attr', [m.group(1), m.group(2)])),
    (r'(赤|青|白|黒)か(赤|青|白|黒)の', lambda m, f: f.__setitem__('color', [{'赤': 'red', '青': 'blue', '白': 'white', '黒': 'black'}[x] for x in m.groups()])),
    (r'エースか⁅バスターアイコン⁆の|エースカードか⁅バスターアイコン⁆', lambda m, f: f.__setitem__('aceOrBuster', 1)),
    (r'魔法', lambda m, f: f.__setitem__('magic', 1)),
    (r'(赤|青|白|黒)か⁅(ハート|スペード|ダイヤ|クラブ)⁆の', lambda m, f: f.__setitem__('colorOrAttr', [{'赤': 'red', '青': 'blue', '白': 'white', '黒': 'black'}[m.group(1)], m.group(2)])),
    (r'クラスカード(?:を持つ|がついている|のついた|がついた)', lambda m, f: f.__setitem__('hasClass', 1)),
    (r'(?:カード名に)?「([^」]+)」(?:か「([^」]+)」)+を(?:名前に)?含む', lambda m, f: f.__setitem__('nameAny', re.findall(r'「([^」]+)」', m.group(0)))),
    (r'(?:カード名に)?「([^」]+)」を(?:名前に)?含む', lambda m, f: f.__setitem__('name', m.group(1))),
    (r'カード名に、', lambda m, f: None),
    (r'【ブライト】を持たない', lambda m, f: f.__setitem__('noBright', 1)),
    (r'このターンにダメージを受けていない', lambda m, f: f.__setitem__('undamaged', 1)),
    (r'スタンドしている', lambda m, f: f.__setitem__('standE', 1)),
    (r'⁅B⁆(?:の)?', lambda m, f: f.__setitem__('icon', 'buster')),
    (r'対象よりパワーが(低い|高い)', lambda m, f: f.__setitem__('powLT_T' if m.group(1) == '低い' else 'powGT_T', 1)),
    (r'現在のパワーが元々のパワーより(低い|高い)', lambda m, f: f.__setitem__('powBelowPrinted' if m.group(1) == '低い' else 'powAbovePrinted', 1)),
    (r'である', lambda m, f: None),
    (r'(ハート|スペード|ダイヤ|クラブ)で', lambda m, f: f.__setitem__('attr', [m.group(1)])),
    (r'⁅?(バスター|ショット)アイコン⁆?(?:の)?(?=$)', lambda m, f: f.__setitem__('icon', 'buster' if m.group(1) == 'バスター' else 'shot')),
    (r'【夢見ない】を持つ', lambda m, f: f.__setitem__('yumemi', 1)),
    (r'【(スカウト\d+|デコイ|ブリッツ|バーサーク)】のアイコン能力を持つ', lambda m, f: f.__setitem__('iconEff', {'デコイ': 'decoy', 'ブリッツ': 'blitz', 'バーサーク': 'berserk'}.get(m.group(1), m.group(1).replace('スカウト', 'scout')))),
    (r'【(?!ブライト)([^】]+)】を持つ', lambda m, f: f.__setitem__('kwText', m.group(1))),
    (r'(赤|青|白|黒)(?:で|の)(?!な)', lambda m, f: f.__setitem__('color', [{'赤': 'red', '青': 'blue', '白': 'white', '黒': 'black'}[m.group(1)]])),
    (r'(赤|青|白|黒)でない、?', lambda m, f: f.__setitem__('notColor', {'赤': 'red', '青': 'blue', '白': 'white', '黒': 'black'}[m.group(1)])),
    (r'「([^」]+)」(?:の)?(?=$)', lambda m, f: f.__setitem__('name', m.group(1))),
    (r'【(鮮血|純潔|極制服|[^】]{1,6})】(?:の)?(?=$)', lambda m, f: f.__setitem__('name', m.group(1))),
    (r'⁅(ハート|スペード|ダイヤ|クラブ)⁆か⁅(ハート|スペード|ダイヤ|クラブ)⁆(?:の|を持つ)?', lambda m, f: f.__setitem__('attr', [m.group(1), m.group(2)])),
    (r'⁅(ハート|スペード|ダイヤ|クラブ)⁆(?:の|を持つ)?', lambda m, f: f.__setitem__('attr', [m.group(1)])),
    (r'【ブライト】を持つ', lambda m, f: f.__setitem__('bright', 1)),
    (r'【コスプレ】を持つ', lambda m, f: f.__setitem__('cos', 1)),
    (r'【我駆力】を持つ', lambda m, f: f.__setitem__('gaku', 1)),
    (r'【夢を?見ない】を持つ', lambda m, f: f.__setitem__('yumemi', 1)),
    (r'⁅神衣⁆を持つ', lambda m, f: f.__setitem__('kamui', 1)),
    (r'【ブライト】を持たない', lambda m, f: f.__setitem__('noBright', 1)),
    (r'【(?!スキル|ブライト|コスプレ|デコイ|ブリッツ|バーサーク)([^】]+)】を持つ', lambda m, f: f.__setitem__('kwText', m.group(1))),
    (r'【(マギア|マケイン|ログ)】を持つ', lambda m, f: f.__setitem__({'マギア': 'magia', 'マケイン': 'makein', 'ログ': 'log'}[m.group(1)], 1)),
    (r'アタック中の', lambda m, f: f.__setitem__('attacking', 1)),
    (r'アタックして', lambda m, f: None),
    (r'(ハート|スペード|ダイヤ|クラブ)の', lambda m, f: f.__setitem__('attr', [m.group(1)])),
    (r'【(デコイ|ブリッツ|バーサーク)】を持つ', lambda m, f: f.__setitem__('kw', {'デコイ': 'decoy', 'ブリッツ': 'blitz', 'バーサーク': 'berserk'}[m.group(1)])),
    (r'パワーがこのユニット(?:のパワー)?以下の', lambda m, f: f.__setitem__('powLE_self', 1)),
    (r'パワーがこのユニット(?:のパワー)?より低い', lambda m, f: f.__setitem__('powLT_self', 1)),
    (r'パワーが対象(?:のパワー)?以下の', lambda m, f: f.__setitem__('powLE_T', 1)),
    (r'パワーが対象(?:のパワー)?より低い', lambda m, f: f.__setitem__('powLT_T', 1)),
    (r'⁅B⁆の|バスターアイコンの', lambda m, f: f.__setitem__('icon', 'buster')),
    (r'アイコン能力を持つ', lambda m, f: f.__setitem__('hasIcon', 1)),
    (r'(赤|青|白|黒)の', lambda m, f: f.__setitem__('color', [{'赤': 'red', '青': 'blue', '白': 'white', '黒': 'black'}[m.group(1)]])),
    (r'⁅バスターアイコン⁆を持つ|バスターの|⁅バスターアイコン⁆の?', lambda m, f: f.__setitem__('icon', 'buster')),
    (r'⁅ショットアイコン⁆の?|⁅☆⁆の?', lambda m, f: f.__setitem__('icon', 'shot')),
    (r'(赤|青|白|黒)でない', lambda m, f: f.__setitem__('notColor', {'赤': 'red', '青': 'blue', '白': 'white', '黒': 'black'}[m.group(1)])),
    (r'パワー(\d+)(?:の|で)', lambda m, f: f.__setitem__('powEQ', int(m.group(1)))),
    (r'総?コスト(\d+)(?:ちょうど)?(?:の|で)', lambda m, f: f.__setitem__('costEQ', int(m.group(1)))),
    (r'「([^」]+)」(?:か「([^」]+)」)+(?:の)?', lambda m, f: f.__setitem__('nameAny', re.findall(r'「([^」]+)」', m.group(0)))),
    (r'「([^」]+)」(?=を\d|を全て|をN)', lambda m, f: f.__setitem__('name', m.group(1))),
    (r'⁅ショットアイコン⁆を持つ|ショットの', lambda m, f: f.__setitem__('icon', 'shot')),
    (r'で|、|かつ|の', lambda m, f: None),
]


_DESC_TOKENS.append((r'(?:、)?(?P<a>(?:ハート|スペード|ダイヤ|クラブ)(?:(?:か|、)(?:ハート|スペード|ダイヤ|クラブ))*)(?:の|で、?)?',
                     lambda m, f: f.__setitem__('attr', re.findall('ハート|スペード|ダイヤ|クラブ', m.group('a')))))


_DESC_TOKENS.insert(0, (r'総?コスト(\d+)でない', lambda m, f: f.__setitem__('costNE', int(m.group(1)))))
_DESC_TOKENS.insert(0, (r'((?:黒|白|青|赤)(?:か(?:黒|白|青|赤))+)(?:の|で、?)', lambda m, f: f.__setitem__('color', [{'黒': 'black', '白': 'white', '青': 'blue', '赤': 'red'}[c] for c in m.group(1).split('か')])))
_DESC_TOKENS.insert(0, (r'総?コスト(\d+)ちょうどで、?', lambda m, f: f.__setitem__('costEQ', int(m.group(1)))))
_DESC_TOKENS.insert(0, (r'パワー(\d+)かパワー(\d+)で、?', lambda m, f: f.__setitem__('powIn', [int(m.group(1)), int(m.group(2))])))
_DESC_TOKENS.insert(0, (r'⁅(ハート|スペード|ダイヤ|クラブ)⁆を持たない、?', lambda m, f: f.__setitem__('attrNot', m.group(1))))
_DESC_TOKENS.insert(0, (r'【(?!ブライト)([^】]+)】を持たない、?', lambda m, f: f.__setitem__('kwNot', m.group(1))))
_DESC_TOKENS.append((r'(黒|白|青|赤)でない、?', lambda m, f: f.__setitem__('colorNot', {'黒': 'black', '白': 'white', '青': 'blue', '赤': 'red'}[m.group(1)])))
_DESC_TOKENS.append((r'(?:総)?コスト(\d+)で、?(?!ない)', lambda m, f: f.__setitem__('costEQ', int(m.group(1)))))
_DESC_TOKENS.insert(0, (r'「([^」]+)」でない、?', lambda m, f: f.__setitem__('nameNot', m.group(1))))
_DESC_TOKENS.insert(0, (r'あなたのユニットと共通の色を持たない', lambda m, f: f.__setitem__('colorNotField', 1)))
_DESC_TOKENS.append((r'ユニットカードで、?', lambda m, f: f.__setitem__('type', 'unit')))
_DESC_TOKENS.append((r'コマンドカードで、?', lambda m, f: f.__setitem__('type', 'command')))
_DESC_TOKENS.append((r'表の?', lambda m, f: f.__setitem__('faceUp', 1)))


def _cost_label(c):
    if len(c) == 1 and c[0].get('op') == 'discard':
        return f"패 {c[0]['n']}장 드롭"
    if len(c) == 1 and c[0].get('op') == 'pick' and c[0].get('from') == 'drop' and c[0].get('to') == 'remove':
        return f"드롭 존 {c[0]['n']}장 리무브"
    if len(c) == 1 and c[0].get('op') == 'pick' and c[0].get('from') == 'hand' and c[0].get('to') == 'remove':
        return f"패 {c[0]['n']}장 리무브"
    if len(c) == 1 and c[0].get('op') == 'payEnergy':
        return f"에너지 {c[0]['n']}장 레스트"
    return '이 비용을 낸다'


def _top_ka(t):
    """괄호(「」【】⁅⁆『』) 밖의 「か」 위치들"""
    depth, out = 0, []
    for i, ch in enumerate(t):
        if ch in '「【⁅『':
            depth += 1
        elif ch in '」】⁆』':
            depth -= 1
        elif ch == 'か' and depth == 0 and i > 0 and t[i - 1] not in 'しるいう':
            out.append(i)
    return out


def parse_desc(desc, f=None):
    r = _parse_desc0(desc, f)
    if r is not None or not desc or 'か' not in desc:
        return r
    # 「AかBの」: 둘 중 하나에 맞으면 (진영은 바깥으로)
    for i in _top_ka(desc):
        L, R = desc[:i], desc[i + 1:]
        pre = {}
        mp = re.match(r'(.*?で、)', L)
        if mp and _parse_desc0(mp.group(1)) is not None:
            pre = _parse_desc0(mp.group(1)); L = L[mp.end():]
        fl = _parse_desc0(L) or _parse_desc0(L + 'の') or (_zdesc0(L) if re.search(r'(?:エース|カード|ユニット)$', L) else None)
        fr = _parse_desc0(R) or _parse_desc0(re.sub(r'の$', '', R) + 'の') if R else None
        if fl and fr:
            out = dict(f or {})
            side = fl.pop('side', None) or fr.pop('side', None)
            if side:
                out['side'] = side
            out['or'] = [fl, fr]
            out.update({k: v for k, v in pre.items() if k != 'side'})
            if pre.get('side'):
                out['side'] = pre['side']
            return out
    return None


def _parse_desc0(desc, f=None):
    """'相手の総コスト4以下の' 같은 묘사 -> 필터. 모르는 말이 남으면 None"""
    f = dict(f or {})
    t = desc
    while t:
        for pat, fn in _DESC_TOKENS:
            m = re.match(pat, t)
            if m:
                fn(m, f)
                t = t[m.end():]
                break
        else:
            return None
    return f


# 명사: 유닛 / 에이스 (카드)
_LAST = {}
_FAIL = {}   # 디버그: 마지막으로 못 읽은 조각
DESC = r'(?P<d>(?:[^。を]|を持つ|を持たない|を含む)*?)'
NOUN = r'(?P<noun>エースカード|エース|ユニットカード|ユニット|コマンドカード|カード|エナジー)'


def noun_filter(f, noun):
    noun = noun or ''
    if noun.startswith('エース'):
        f['ace'] = 1
    if noun in ('ユニットカード', 'ユニット', 'エース', 'エースカード'):
        f['type'] = 'unit'
    if noun == 'コマンドカード':
        f['type'] = 'command'
    return f


# ---------- 동사 끝 (끝맺음/이음) ----------
def V(*stems):
    return '(?:' + '|'.join(stems) + ')'


END = r'(?:。|、|$)'
MAY = r'(?P<may>(?:て|で)(?:も)?よい)?'

TO_SELF = r'このユニット'
TO_T = r'(?:対象|そのユニット|そのカード|それ)'

_DUR = r'(?:(?P<dur>そのターン中|このターン(?:中)?|次の(?:あなたの|相手の)?ターン(?:の)?(?:開始時|終了時)まで)、)?'


def subj(t):
    """효과 받는 쪽: 'T' | 'self' | {'all': filter}"""
    if re.fullmatch(TO_T, t):
        return 'T'
    if t == 'バトル相手':
        return 'vs'
    if t in ('その登場させたユニット', '登場させたユニット全て', '登場させたユニット', 'その登場したユニット', '登場した対象', '登場させたそのユニット'):
        return 'summoned'
    if t in ('そのアタックしたユニット', 'アタックしたユニット'):
        return 'T'
    if t == TO_SELF or t == 'このカード':
        return 'self'
    if t in ('あなたのドロップゾーンからこのカード', 'ドロップゾーンからこのカード', 'ドロップしたこのカード'):
        return 'card'
    if t in ('ドロップゾーンのこのカード', 'あなたのドロップゾーンのこのカード', 'ドロップゾーンからそのカード', 'ドロップゾーンのそのカード'):
        return 'T' if 'その' in t else 'card'
    if t in ('ドロップゾーンのこのカード', 'あなたのドロップゾーンのこのカード'):
        return 'card'
    if t in ('このカードがついているユニット', 'このカードがついたユニット', 'このカードをつけたユニット'):
        return 'host'
    if t in ('あなた', 'あなた自身'):
        return 'me'
    if t == '相手':
        return 'opp'
    m = re.fullmatch(r'(?P<d>.*?)' + NOUN + r'全て', t)
    if m:
        f = parse_desc(m.group('d'))
        if f is None:
            return None
        return {'all': noun_filter(f, m.group('noun'))}
    return None


# ---------- 효과 조각 ----------
def eff_patterns():
    P = []

    def add(rx, fn):
        P.append((re.compile(rx), fn))

    # 대상 지정
    def tgt(m):
        f = parse_desc(m.group('d') or '')
        if f is None:
            return None
        if not m.group('noun') and not m.group('zone'):
            return None
        noun_filter(f, m.group('noun'))
        zone = m.group('zone')
        if m.group('noun') == 'エナジー':
            zone = 'エナジー'
            f.setdefault('side', 'own')
        st = {'op': 'tgt', 'f': f, 'n': int(m.group('n')), 'upto': 1 if m.group('upto') else 0}
        if zone:
            st['zone'] = {'ドロップゾーン': 'drop', '手札': 'hand', 'エナジーゾーン': 'energy', 'エナジー': 'energy'}[zone]
            if m.group(0).startswith('相手の' + zone):
                f['side'] = 'opp'
        return st
    add(r'(?:(?:あなたの|相手の)?(?P<zone>ドロップゾーン|手札|エナジーゾーン|エナジー)の)?(?P<d>(?:[^。を]|を持つ|を持たない|を含む)*?)(?:' + NOUN + r')?を(?P<n>\d+)枚(?P<upto>まで)?対象と' + V('し', 'する') + END, tgt)

    # 데미지
    def dmg(m):
        to = subj(m.group('to'))
        if to in ('me', 'opp'):
            return {'op': 'lifeDmg', 'n': int(m.group('n')), 'who': to}
        return to and {'op': 'dmg', 'n': int(m.group('n')), 'to': to}
    add(r'(?P<to>[^、。]*?)に(?P<n>\d+)ダメージ(?:を与え(?:る|))?' + END, dmg)

    # 파워/히트 수정
    def mod(m):
        to = subj(m.group('to'))
        if not to:
            return None
        out = []
        for k, v in re.findall(r'(パワー|ヒット)を([+-]\d+)', m.group('mods')):
            out.append({'op': 'pow' if k == 'パワー' else 'hit', 'n': int(v), 'to': to})
        if not out:
            return None
        return out
    add(_DUR + r'(?P<to>[^、。]*?)の(?P<mods>(?:パワー|ヒット)を[+-]\d+(?:、(?:パワー|ヒット)を[+-]\d+)?)(?:する|し)?' + END, mod)

    # 키워드 얻기
    def kw(m):
        to = subj(m.group('to'))
        k = {'デコイ': 'decoy', 'ブリッツ': 'blitz', 'バーサーク': 'berserk'}.get(m.group('k'))
        return to and k and {'op': 'kw', 'kw': k, 'to': to}
    add(_DUR + r'(?P<to>[^、。]*?)は【(?P<k>デコイ|ブリッツ|バーサーク)】を得' + V('る', 'て') + END, kw)

    def restrict(m):
        to = subj(m.group('to'))
        ks = {'アタックとブロックができない': ['noAttack', 'noBlock'], 'アタックできない': ['noAttack'], 'ブロックができない': ['noBlock'],
              'ブロックできない': ['noBlock'], 'ブロックされない': ['unblockable'], 'アタックができない': ['noAttack']}[m.group('k')]
        return to and [{'op': 'kw', 'kw': k, 'to': to} for k in ks]
    add(_DUR + r'(?P<to>[^、。]*?)(?:は|では)(?P<k>アタックとブロックができない|アタックできない|アタックができない|ブロックができない|ブロックできない|ブロックされない)' + END, restrict)
    # 플레이어 데미지
    add(r'(?P<w>あなた|相手)に(?P<n>\d+)ダメージ' + END, lambda m: {'op': 'lifeDmg', 'n': int(m.group('n')), 'who': 'me' if m.group('w') == 'あなた' else 'opp'})

    # 이동
    moves = [
        (r'ドロップ' + V('させる', 'させ', 'する', 'し'), 'drop'),
        (r'(?:持ち主の)?手札に戻' + V('す', 'し'), 'bounce'),
        (r'(?:持ち主の)?山札の上に置' + V('く', 'き', 'い'), 'deckTop'),
        (r'(?:持ち主の)?山札の下に置' + V('く', 'き', 'い'), 'deckBottom'),
        (r'(?:持ち主の)?エナジーゾーンに置' + V('く', 'き', 'い'), 'energy'),
        (r'リムーブ' + V('する', 'し'), 'remove'),
        (r'レスト' + V('する', 'し', 'させる', 'させ'), 'rest'),
        (r'スタンド' + V('する', 'し', 'させる', 'させ'), 'stand'),
        (r'レストで登場' + V('させる', 'させ'), 'summonRested'),
        (r'登場' + V('させる', 'させ'), 'summon'),
        (r'(?:あなたの)?ライフの先頭に置' + V('く', 'き', 'い'), 'life'),
    ]
    for rx, op in moves:
        def mv(m, op=op):
            to = subj(m.group('to'))
            st = to and {'op': op, 'to': to}
            if st and m.group('may'):
                st['may'] = 1
            return st
        add(r'(?:さらに)?(?P<to>[^、。]*?)を' + rx + MAY + END, mv)

    # 대상 없이 쓰는 데미지 (앞의 대상에게)
    add(r'(?:代わりに)?(?P<n>\d+)ダメージ' + END, lambda m: {'op': 'dmg', 'n': int(m.group('n')), 'to': 'T'})
    # 주어 없는 수정: 앞 문장의 대상에게 (예: 「ブロックされず、ヒットを+1」)
    add(r'(?:さらに)?(?P<mods>(?:パワー|ヒット)を[+-]\d+)' + END, lambda m: {'op': 'pow' if m.group('mods').startswith('パワー') else 'hit', 'n': int(re.search(r'[+-]\d+', m.group('mods')).group()), 'to': '$prev'})
    add(r'さらに(?P<n>[+-]\d+)' + END, lambda m: {'op': '$prevop', 'n': int(m.group('n')), 'to': '$prev'})
    add(_DUR + r'(?P<to>[^、。]*?)はブロックされず' + END, lambda m: subj(m.group('to')) and {'op': 'kw', 'kw': 'unblockable', 'to': subj(m.group('to'))})
    # 상대는 ~ 유닛으로 공격·블록 못 함
    add(_DUR + r'相手は(?P<d>[^、。]*?)ユニットでは(?P<k>アタックとブロック|アタック|ブロック)ができない' + END,
        lambda m: (lambda f: f is not None and [{'op': 'kw', 'kw': k, 'to': {'all': {**f, 'side': 'opp', 'type': 'unit'}}} for k in {'アタックとブロック': ['noAttack', 'noBlock'], 'アタック': ['noAttack'], 'ブロック': ['noBlock']}[m.group('k')]])(parse_desc(m.group('d'))))
    # 대상을 A하거나 B
    add(r'(?:対象|そのカード)を手札に戻すか登場させる' + END, lambda m: {'op': 'choose', 'opts': [[{'op': 'bounce', 'to': 'T'}], [{'op': 'summon', 'to': 'T'}]], 'labels': ['패로 되돌린다', '등장시킨다']})
    # 에너지의 카드를 패로
    add(r'あなたの' + DESC + r'(?:' + NOUN[:-1] + r'))?の?エナジーを(?P<n>\d+)枚(?P<upto>まで)?手札に戻' + V('す', 'し') + END,
        lambda m: (lambda f: f is not None and {'op': 'pick', 'from': 'energy', 'to': 'hand', 'f': noun_filter(f, m.group('noun')), 'n': int(m.group('n')), 'upto': 1 if m.group('upto') else 0})(parse_desc(m.group('d'))))
    # 패의 카드를 공개해서 라이프 맨 앞에
    add(r'あなたの手札の、?' + DESC + r'を(?P<n>\d+)枚(?P<upto>まで)?公開し、公開したカードをライフの先頭に置' + V('く', 'き', 'い') + END,
        lambda m: (lambda f: f is not None and {'op': 'pick', 'from': 'hand', 'to': 'life', 'f': f, 'n': int(m.group('n')), 'upto': 1 if m.group('upto') else 0})(parse_desc(m.group('d'))))
    # 덱 위 1장 공개: 맞으면 패/등장, 아니면 드롭/덱 아래
    def reveal_top(m):
        f = parse_desc(m.group('d') or '')
        if f is None:
            return None
        if m.group('noun'):
            noun_filter(f, m.group('noun'))
        st = {'op': 'revealTop', 'f': f, 'yes': 'field' if '登場' in m.group('y') else 'hand', 'no': 'drop' if 'ドロップ' in m.group('n2') else 'hand' if '手札' in m.group('n2') else 'bottom'}
        if m.group('may'):
            st['may'] = 1
        return st
    add(r'(?:あなたの)?山札(?:を|の)上から1枚(?:を)?公開(?:し|して|する)' + MAY + r'(?:。|、)それが' + DESC + r'(?:' + NOUN[:-1] + r'))?なら(?P<y>手札に加え|登場させ)、違うなら(?P<n2>ドロップ|山札の下に置|手札に加え)' + V('する', 'く', 'し', 'き', 'る', '') + END, reveal_top)
    # 에너지의 커맨드를 코스트 없이 플레이
    add(r'あなたの' + DESC + r'コマンドカードのエナジーを1枚、コストを払わずにプレイ' + V('する', 'し') + MAY + END,
        lambda m: (lambda f: f is not None and {'op': 'playFree', 'from': 'energy', 'f': {**f, 'type': 'command'}, 'may': 1})(parse_desc(m.group('d').rstrip('で'))))
    # 플레이어 1명이 자기 유닛 1장을 드롭
    add(r'プレイヤー1人を対象とし、対象は自身のユニットを(?P<n>\d+)枚ドロップさせ' + V('る', '') + END,
        lambda m: {'op': 'choose', 'opts': [[{'op': 'sacrifice', 'who': 'me', 'n': int(m.group('n'))}], [{'op': 'sacrifice', 'who': 'opp', 'n': int(m.group('n'))}]], 'labels': ['나를 대상으로', '상대를 대상으로']})
    # 대상을 받는 말이 생략된 동사 (「対象とし、ドロップさせる」)
    for rx, op in [(r'ドロップさせ' + V('る', ''), 'drop'), (r'手札に戻' + V('す', 'し'), 'bounce'), (r'エナジーゾーンに置' + V('く', 'き', 'い'), 'energy'),
                   (r'山札の下に置' + V('く', 'き', 'い'), 'deckBottom'), (r'登場させ' + V('る', ''), 'summon'),
                   (r'ライフの先頭に置' + V('く', 'き', 'い'), 'life'), (r'山札の上に置' + V('く', 'き', 'い'), 'deckTop'), (r'リムーブ' + V('する', 'し'), 'remove')]:
        add(rx + MAY + END, lambda m, op=op: {'op': op, 'to': 'T', **({'may': 1} if m.group('may') else {})})
    # 다음 스탠드 페이즈에 스탠드하지 않음
    add(r'(?P<to>[^、。]*?)は次の(?:相手の|あなたの)?スタンドフェイズにスタンドしない' + END, lambda m: subj(m.group('to')) and {'op': 'freeze', 'to': subj(m.group('to'))})
    # 이번 턴 대상이 드롭되었을 때 ~
    def watch(m):
        sub = parse_effects(m.group('x'))
        return sub and {'op': 'watch', 'on': 'leave', 'do': sub}
    add(r'(?:そのターン中|このターン)、?対象が(?:フィールドから)?ドロップした時、(?P<x>[^。]+)(?:。|$)', watch)
    # 계약서 (ツイステッドワンダーランド): 덱 위 카드를 앞면으로 테리토리에 붙임
    add(r'あなたの山札(?:を|の)上から(?P<n>\d+)枚、表で(?:この)?テリトリーに契約書としてつけ' + V('る', '') + END, lambda m: {'op': 'contract', 'n': int(m.group('n'))})
    add(r'あなたの山札(?:を|の)上から(?P<n>\d+)枚、表で(?:この)?テリトリーに契約書としてつけてよい' + END, lambda m: {'op': 'contract', 'n': int(m.group('n')), 'may': 1})
    add(r'あなたの山札(?:を|の)上から(?P<n>\d+)枚、表で契約書としてこのテリトリーにつけ' + V('る', '') + END, lambda m: {'op': 'contract', 'n': int(m.group('n'))})
    add(r'あなたのつけた契約書を(?P<n>\d+)枚ドロップ' + V('する', 'し') + MAY + END, lambda m: {'op': 'contractDrop', 'n': int(m.group('n')), **({'may': 1} if m.group('may') else {})})
    add(r'相手のテリトリーにつけられている契約書を全てドロップ' + V('する', 'し') + END, lambda m: {'op': 'contractDrop', 'all': 1, 'who': 'opp'})
    add(r'あなたは追加の1ターンを行う' + END, lambda m: {'op': 'extraTurn'})
    add(r'__CHOOSE__$', lambda m: {'op': 'choose'})
    # 「~해도 된다」 비용형: 패의 카드를 드롭/공개, 에너지 드롭
    add(r'(?:あなたは)?(?:あなたの)?手札(?:の|から)、?' + DESC + r'(?:' + NOUN[:-1] + r'))?を(?P<n>\d+)枚(?P<v>ドロップ|公開)' + V('する', 'し') + MAY + END,
        lambda m: (lambda f: f is not None and {'op': 'discard' if m.group('v') == 'ドロップ' else 'revealHand', 'n': int(m.group('n')), 'f': noun_filter(f, m.group('noun')), **({'may': 1, 'opt': 1} if m.group('may') else {})})(parse_desc(m.group('d'))))
    add(r'あなたのエナジーを(?P<n>\d+)枚ドロップ' + V('する', 'し') + MAY + END, lambda m: {'op': 'payEnergy', 'n': int(m.group('n')), 'how': 'drop', **({'may': 1} if m.group('may') else {})})
    add(r'(?:あなたは)?(?:自分の|あなたの)?山札(?:を|の)上から(?P<n>\d+)枚(?P<upto>まで)?(?:を)?ドロップ' + V('する', 'し') + MAY + END,
        lambda m: {'op': 'mill', 'n': int(m.group('n')), **({'may': 1} if m.group('may') or m.group('upto') else {})})
    add(r'(?:あなたは)?(?P<n>\d+)枚引いてよい' + END, lambda m: {'op': 'draw', 'n': int(m.group('n')), 'may': 1})
    add(r'相手のライフの先頭をドロップ' + V('する', 'し', 'させる', 'させ') + END, lambda m: {'op': 'lifeDrop', 'n': 1, 'who': 'opp'})
    add(r'相手のライフの先頭を墓地に置' + V('く', 'き') + END, lambda m: {'op': 'lifeDrop', 'n': 1, 'who': 'opp'})
    add(r'(?:あなたの)?山札(?:を|の)上から(?P<n>\d+)枚、?(?:を)?(?P<z>ライフ(?:ゾーン)?の先頭|エナジーゾーン)に置' + V('く', 'き', 'い') + END,
        lambda m: {'op': 'lifeTop' if 'ライフ' in m.group('z') else 'deckEnergy', 'n': int(m.group('n'))})
    add(r'(?:あなたの)?山札をシャッフルして上から(?P<n>\d+)枚(?:を)?ライフ(?:ゾーン)?の先頭に置' + V('く', 'き', 'い') + END, lambda m: {'op': 'lifeTop', 'n': int(m.group('n')), 'shuffle': 1})
    add(r'対象とこのユニットは(?:互いの)?パワー分、ダメージを与えあう' + END, lambda m: [{'op': 'fight', 'self': 1}])
    add(r'それらは互いのパワー分、ダメージを与えあう' + END, lambda m: {'op': 'fight'})
    add(r'(?:そのターン中、)?(?P<to>このユニット|対象)(?:の)?ヒット(?P<n>[+-]\d+)' + END, lambda m: {'op': 'hit', 'n': int(m.group('n')), 'to': subj(m.group('to'))})
    add(r'ヒット(?P<n>[+-]\d+)' + END, lambda m: {'op': 'hit', 'n': int(m.group('n')), 'to': '$prev'})
    add(r'あなたのライフの先頭を見る。それが' + DESC + r'(?:' + NOUN[:-1] + r'))?なら、(?:公開して)?手札に加え(?:る|て(?:も)?よい)' + END,
        lambda m: (lambda f: f is not None and {'op': 'lifeTake', 'f': noun_filter(f, m.group('noun')), 'may': 1})(parse_desc(m.group('d'))))
    add(r'このカードを(?:ドロップゾーンに置く|ドロップする|解決しドロップする)際、代わりに手札に戻' + V('す', 'し') + END, lambda m: {'op': 'selfToHand'})
    add(r'(?:このターン|そのターン中、)?(?P<to>[^、。]*?)は1ダメージでも受けるとドロップする' + END, lambda m: subj(m.group('to')) and {'op': 'kw', 'kw': 'fragile', 'to': subj(m.group('to'))})
    add(r'(?:そのターン中、)?対象がドロップする際、代わりにリムーブ' + V('する', 'し') + END, lambda m: {'op': 'kw', 'kw': 'exile', 'to': 'T'})
    add(r'相手は対象を(?P<r>レストで)?登場させ' + V('る', '') + END, lambda m: {'op': 'summonRested' if m.group('r') else 'summon', 'to': 'T'})
    add(r'対象とこのユニットを(?P<st>スタンドで)?入れ替え' + V('る', '') + END, lambda m: {'op': 'swapT', **({'stand': 1} if m.group('st') else {})})
    add(r'あなたのエナジーを(?P<n>\d+)枚、?(?:望む順で)?山札の下に置' + V('く', 'き', 'い') + END, lambda m: {'op': 'pick', 'from': 'energy', 'to': 'bottom', 'f': {}, 'n': int(m.group('n')), 'upto': 0})
    add(r'(?:そのターン中、)?相手のユニット全ては可能な限りブロックする' + END, lambda m: {'op': 'kw', 'kw': 'mustBlock', 'to': {'all': {'side': 'opp', 'type': 'unit'}}})
    add(r'(?:あなたの)?山札を上から1枚見る。それがアタックしたユニットと異なる色でヒット(?P<h>\d+)なら登場させ、違うならドロップしてよい' + END,
        lambda m: {'op': 'peekDiff', 'hit': int(m.group('h'))})
    add(r'相手は対象をライフの先頭に置' + V('く', 'き', 'い') + END, lambda m: {'op': 'life', 'to': 'T'})
    add(r'ドロップゾーンのこのカードをレストで登場させるかエナジーゾーンに置' + V('く', 'き') + END,
        lambda m: {'op': 'choose', 'opts': [[{'op': 'summonRested', 'to': 'card'}], [{'op': 'energy', 'to': 'card'}]], 'labels': ['레스트로 등장', '에너지 존에 놓음']})
    add(_DUR + r'(?:次の(?:相手|あなたの)?ターンまで、)?(?P<to>[^、。]*?)はドロップ以外の方法でフィールドを離れない' + END,
        lambda m: subj(m.group('to')) and {'op': 'kw', 'kw': 'stayField', 'to': subj(m.group('to'))})
    def tturn(m):
        sub = parse_effects(m.group('x'))
        return sub and {'op': 'turnTrig', 'on': 'leave', 'side': 'opp' if m.group('w') == '相手' else 'own', 'do': sub}
    add(r'このターン(?P<w>相手|あなた)のユニットがフィールドからドロップした時、(?P<x>[^。]+)(?:。|$)', tturn)
    def twin(m):
        sub = parse_effects(m.group('x'))
        return sub and {'op': 'watch', 'on': 'win', 'do': sub}
    add(r'(?:そのターン中、)?対象がバトルに勝利した時、(?P<x>[^。]+)(?:。|$)', twin)
    add(r'あなたの山札(?:を|の)下から(?P<n>\d+)枚(?:を)?ドロップ' + V('する', 'し') + END, lambda m: {'op': 'millBottom', 'n': int(m.group('n'))})
    add(_DUR + r'(?P<to>[^、。]*?)はいかなる方法でもドロップしない' + END, lambda m: subj(m.group('to')) and {'op': 'kw', 'kw': 'indestructible', 'to': subj(m.group('to'))})
    add(r'(?:そのターン中、)?あなたはライフの枚数に関わらずレッドゾーンとなる' + END, lambda m: {'op': 'turnFlag', 'flag': 'red'})
    add(_DUR + r'(?:さらに)?(?P<mods>(?:パワー|ヒット)を[+-]\d+)' + END, lambda m: {'op': 'pow' if m.group('mods').startswith('パワー') else 'hit', 'n': int(re.search(r'[+-]\d+', m.group('mods')).group()), 'to': '$prev'})
    add(_DUR + r'(?P<to>このユニット|対象)は(?P<mods>(?:パワー|ヒット)を[+-]\d+)' + END, lambda m: {'op': 'pow' if m.group('mods').startswith('パワー') else 'hit', 'n': int(re.search(r'[+-]\d+', m.group('mods')).group()), 'to': subj(m.group('to'))})
    add(r'あなたの手札を(?P<n>\d+)枚(?P<upto>まで)?公開' + V('する', 'し') + END, lambda m: {'op': 'revealHand', 'n': int(m.group('n')), 'f': {}, **({'opt': 1} if m.group('upto') else {})})
    add(r'あなたの手札を(?P<n>\d+)枚リムーブ' + V('する', 'し') + MAY + END, lambda m: {'op': 'pick', 'from': 'hand', 'to': 'remove', 'f': {}, 'n': int(m.group('n')), 'upto': 1 if m.group('may') else 0})
    add(r'あなたの(?P<z>ドロップゾーン|手札|エナジーゾーン)の、?' + DESC + r'(?:' + NOUN[:-1] + r'))?を(?P<n>\d+)枚、コストを払わず(?:に)?プレイ' + V('する', 'し') + MAY + END,
        lambda m: (lambda f: f is not None and {'op': 'playFree', 'from': {'ドロップゾーン': 'drop', '手札': 'hand', 'エナジーゾーン': 'energy'}[m.group('z')], 'f': noun_filter(f, m.group('noun')), 'may': 1})(parse_desc(m.group('d'))))
    # --- 10차: 자주 남은 효과 문장 ---
    OPPALL = {'all': {'side': 'opp', 'type': 'unit'}}
    add(r'あなたの(?P<z>ドロップゾーン|手札|エナジーゾーン)(?:の|から)、?(?P<d>[^。]*?)を(?P<n>\d+)枚、?コストを払わず(?:に)?プレイ' + V('する', 'し') + MAY + END,
        lambda m: (lambda f: f is not None and {'op': 'playFree', 'from': {'ドロップゾーン': 'drop', '手札': 'hand', 'エナジーゾーン': 'energy'}[m.group('z')], 'f': f, 'may': 1})(_zdesc(m.group('d'))))
    add(r'その(?:コマンド|魔法)は解決の際、(?P<w>リムーブされる|エナジーゾーンに置く)' + END, lambda m: {'op': '_attach', 'afterPlay': 'remove' if 'リムーブ' in m.group('w') else 'energy'})
    add(r'相手のユニット全てにこのユニットのパワー分のダメージを与え' + V('る', '') + END, lambda m: {'op': 'dmgPow', 'from': 'self', 'to': OPPALL})
    add(r'対象と相手のユニット全てに対象のパワー分のダメージを与え' + V('る', '') + END, lambda m: [{'op': 'dmgPow', 'from': 'T', 'to': OPPALL}, {'op': 'dmgPow', 'from': 'T', 'to': 'T'}])
    add(r'相手のユニット全てに対象のパワー分のダメージを与え' + V('る', '') + END, lambda m: {'op': 'dmgPow', 'from': 'T', 'to': OPPALL})
    add(r'(?:対象に)?(?:対象|自身)のパワーと同じダメージを与え' + V('る', '') + END, lambda m: {'op': 'dmgPow', 'from': 'T', 'to': 'T'})
    add(r'(?:そのターン中、)?(?P<to>対象|このユニット)のパワーを(?P<n>\d+)になるよう増減させ' + V('る', '') + END, lambda m: {'op': 'powSet', 'n': int(m.group('n')), 'to': subj(m.group('to'))})
    add(r'(?:そのターン中、)?相手のユニット全てを、それぞれパワーが(?P<n>\d+)になるよう増減させ' + V('る', '') + END, lambda m: {'op': 'powSet', 'n': int(m.group('n')), 'to': OPPALL})
    add(r'(?:そのターン中、)?相手のユニット全てのヒットを(?P<n>\d+)になるよう増減させ' + V('る', '') + END, lambda m: {'op': 'hitSet', 'n': int(m.group('n')), 'to': OPPALL})
    def _recolor(m):
        to = {'そのユニット': 'T', '対象': 'T', 'このユニット': 'self'}.get(m.group('to')) or subj(m.group('to'))
        if not to:
            return None
        c = {'赤': 'red', '青': 'blue', '白': 'white', '黒': 'black'}[m.group('c')]
        return [{'op': 'kw', 'kw': 'colorAs:only', 'to': to}, {'op': 'kw', 'kw': 'colorAs:' + c, 'to': to}]
    add(r'(?:そのターン中、)?(?P<to>[^、。]*?)(?:の色)?は(?P<c>赤|青|白|黒)になり、(?:赤|青|白|黒)以外の色を失' + V('う', 'い') + END, _recolor)
    add(r'(?:そのターン中、)?(?P<to>[^、。]*?)はアタックもブロックもできない' + END,
        lambda m: subj(m.group('to')) and [{'op': 'kw', 'kw': 'noAttack', 'to': subj(m.group('to'))}, {'op': 'kw', 'kw': 'noBlock', 'to': subj(m.group('to'))}])
    add(r'あなたの、?(?P<d>[^。]*?)のエナジーを(?P<n>\d+)枚(?P<upto>まで)?対象と' + V('し', 'する') + END,
        lambda m: (lambda f: f is not None and {'op': 'tgt', 'zone': 'energy', 'f': dict(f, side='own'), 'n': int(m.group('n')), 'upto': 1 if m.group('upto') else 0})(_zdesc(m.group('d'))))
    add(r'(?:対象を)?このユニットと入れ替え' + V('る', '') + END, lambda m: {'op': 'swapT'})
    add(r'ドロップゾーンのこのカードをエナジーゾーンに裏で置' + V('く', 'き') + END, lambda m: {'op': 'energyDown', 'to': 'card'})
    add(r'ドロップゾーンのこのカードを山札に戻してシャッフル' + V('する', 'し') + END, lambda m: [{'op': 'deckTop', 'to': 'card'}, {'op': 'shuffle'}])
    add(r'そのターン中、あなたと、あなたのユニット全てが受けるダメージ全てを0にする' + END, lambda m: [{'op': 'kw', 'kw': 'noDamage', 'to': {'all': {'side': 'own', 'type': 'unit'}}}, {'op': 'turnFlag', 'flag': 'noPlayerDmg'}])
    def _grantT(m):
        ab = _parse_body2(m.group('ab'), {}, None)
        if not ab or ab.get('k') != 'auto':
            return None
        r = [{'op': 'grantT', 'ab': ab, 'to': 'T'}]
        if m.group('n'):
            r.append({'op': 'pow', 'n': int(m.group('n')), 'to': 'T'})
        return r
    add(r'(?:そのターン中、)?対象は『(?P<ab>⁅自動⁆[^』]+?)。?』を得(?:る|て、パワーを(?P<n>[+-]\d+))' + END, _grantT)
    # --- 11차 ---
    add(r'互いのパワー分、ダメージを与えあう' + END, lambda m: {'op': 'fight'})
    add(r'各プレイヤーの山札を上から(?P<n>\d+)枚リムーブ' + V('する', 'し') + END, lambda m: [{'op': 'deckRemove', 'n': int(m.group('n'))}, {'op': 'deckRemove', 'n': int(m.group('n')), 'who': 'opp'}])
    add(r'(?:そのターン中、)?(?P<to>[^、。]*?)は【デコイ】を失' + V('う', 'い') + END, lambda m: subj(m.group('to')) and {'op': 'kw', 'kw': 'loseDecoy', 'to': subj(m.group('to'))})
    add(r'(?:そのターン中、)?相手のユニット全てのパワーを(?P<n>\d+)になるよう増減させ' + V('る', '') + END, lambda m: {'op': 'powSet', 'n': int(m.group('n')), 'to': OPPALL})
    add(r'あなたの(?P<d>[^、。]*?)のエナジーを(?P<n>\d+)枚、?ライフの先頭に置' + V('く', 'き') + END,
        lambda m: (lambda f: f is not None and {'op': 'pick', 'from': 'energy', 'to': 'life', 'f': f, 'n': int(m.group('n')), 'upto': 0})(_zdesc(m.group('d'))))
    add(r'あなたの手札を(?P<n>\d+)枚エナジーゾーンに置' + V('く', 'き') + END, lambda m: {'op': 'pick', 'from': 'hand', 'to': 'energy', 'f': {}, 'n': int(m.group('n')), 'upto': 0})
    add(r'このターンこのユニットが与えるダメージでの⁅ショットアイコン⁆は無視される' + END, lambda m: {'op': 'kw', 'kw': 'noShotTrig', 'to': 'self'})
    add(r'相手のドロップゾーンのカードを(?P<n>\d+)枚(?P<upto>まで)?対象とし、相手は対象を山札に戻してシャッフル' + V('する', 'し') + END,
        lambda m: [{'op': 'tgt', 'zone': 'drop', 'f': {'side': 'opp'}, 'n': int(m.group('n')), 'upto': 1 if m.group('upto') else 0}, {'op': 'deckTop', 'to': 'T'}, {'op': 'shuffle', 'who': 'opp'}])
    add(r'あなたのドロップゾーンの(?P<d>[^、。]*?)を望む枚数リムーブ' + V('する', 'し') + END,
        lambda m: (lambda f: f is not None and {'op': 'pick', 'from': 'drop', 'to': 'remove', 'f': f, 'n': 99, 'upto': 1})(_zdesc(m.group('d'))))
    add(r'あなたのドロップゾーンのクラスカードを望む枚数、このユニットにつけ' + V('る', '') + END, lambda m: {'op': 'classFromDrop', 'n': 99, 'to': 'self'})
    add(r'ドロップしたカードと同じコストで(?P<c>赤|青|白|黒)のコマンドカードを1枚、あなたのドロップゾーンからコストを払わず(?:に)?プレイ' + V('する', 'し') + MAY + END,
        lambda m: {'op': 'playFree', 'from': 'drop', 'f': {'color': [{'赤': 'red', '青': 'blue', '白': 'white', '黒': 'black'}[m.group('c')]], 'type': 'command', 'costFromBright': 1}, 'may': 1})
    add(r'『(?P<x>[^』]+?)。?』を(?P<n>\d+)回行' + V('う', 'い') + END, lambda m: (lambda r: r is not None and r * int(m.group('n')))(parse_effects(m.group('x'))))
    add(r'あなたのドロップゾーンの(?P<d>[^、。]+?)を(?P<n>\d+)枚(?P<upto>まで)?手札に(?:戻|加え)' + V('す', 'し', 'る', '') + MAY + END,
        lambda m: (lambda f: f is not None and {'op': 'pick', 'from': 'drop', 'to': 'hand', 'f': f, 'n': int(m.group('n')), 'upto': 1 if m.group('upto') or m.group('may') else 0})(_zdesc(m.group('d'))))
    # --- 12차: 덱 보기 계열 (유연한 읽기) ---
    def look2(m):
        rest_txt = m.group('x')
        n = int(m.group('n'))
        f, k, dest, rest, rested, allm = {}, n, 'hand', 'bottom', 0, 0
        mm = re.match(r'(?:その中(?:から|の)、?)?(?:(?P<d>[^、。]*?)(?:を|の)?)?(?:(?P<k>\d+)枚(?P<up>まで)?|(?P<all>全て)|(?P<want>望む枚数))(?:を)?(?:公開(?:して|し、))?(?P<rst>レストで)?(?P<v>手札に加え|登場させ|ライフの先頭に置|エナジーゾーンに(?:レストで)?置|ドロップし|山札の上に置|フィールドに伏せ)', rest_txt)
        if not mm:
            return None
        if mm.group('d'):
            f = _zdesc(mm.group('d'))
            if f is None:
                f = _zdesc(mm.group('d') + 'カード')
            if f is None:
                return None
        k = 99 if mm.group('want') else int(mm.group('k')) if mm.group('k') else 99
        allm = 1 if mm.group('all') else 0
        v = mm.group('v')
        dest = 'field' if '登場' in v else 'life' if 'ライフ' in v else 'energy' if 'エナジー' in v else 'drop' if 'ドロップ' in v else 'top' if '山札の上' in v else 'set' if '伏せ' in v else 'hand'
        rested = 1 if (mm.group('rst') or 'レスト' in v) else 0
        tail = rest_txt[mm.end():]
        mr = re.search(r'残りを(?:望む順で)?(?P<r>山札の下|山札の上|ドロップ|エナジーゾーンにレストで|エナジーゾーン|リムーブ|手札)', tail)
        if mr:
            r = mr.group('r')
            rest = {'山札の下': 'bottom', '山札の上': 'top', 'ドロップ': 'drop', 'エナジーゾーンにレストで': 'energyR', 'エナジーゾーン': 'energy', 'リムーブ': 'remove', '手札': 'hand'}[r]
        elif 'シャッフル' in tail:
            rest = 'shuffle'
        elif dest in ('drop',):
            rest = 'top'
        st = {'op': 'look', 'n': n, 'f': f, 'k': k, 'to': dest, 'rest': rest, **({'rested': 1} if rested else {})}
        if allm:
            st['k'] = 99
        if 'シャッフル' in tail and rest != 'shuffle':
            return [st, {'op': 'shuffle'}]
        return st
    add(r'(?:あなたの)?山札(?:を|の)上から(?P<n>\d+)枚(?:見て|公開し|見、)、?(?P<x>[^。]+)' + END, look2)
    add(r'(?:あなたの)?山札(?:を|の)上から(?P<n>\d+)枚(?:見る|公開する)' + END, lambda m: {'op': 'look', 'n': int(m.group('n')), 'f': {}, 'k': 0, 'to': 'hand', 'rest': 'top'})
    add(r'(?:あなたの)?山札(?:を|の)上から(?P<n>\d+)枚公開(?:し|する)(?:。|、)それが(?P<d>[^、。]+?)なら(?P<y>手札に加え|登場させ)(?:、違うなら(?P<n2>ドロップ|山札の下に置)' + V('する', 'く', 'し', 'き') + r')?' + END,
        lambda m: (lambda f: f is not None and {'op': 'revealTop', 'f': f, 'yes': 'field' if '登場' in m.group('y') else 'hand', 'no': 'drop' if m.group('n2') and 'ドロップ' in m.group('n2') else 'bottom'})(_zdesc(m.group('d')) if _zdesc(m.group('d')) is not None else _zdesc(m.group('d') + 'カード')))
    add(r'(?:あなたの)?山札(?:を|の)上から(?P<n>\d+)枚まで(?P<r>レストで)?エナジーゾーンに置' + V('く', 'き') + END,
        lambda m: {'op': 'choose', 'opts': [[{'op': 'deckEnergy', 'n': k, **({'rested': 1} if m.group('r') else {})}] if k else [] for k in range(int(m.group('n')), -1, -1)], 'labels': [f'덱 위 {k}장을 에너지로' if k else '놓지 않음' for k in range(int(m.group('n')), -1, -1)]})
    add(r'(?:あなたの)?山札(?:を|の)上から(?P<n>\d+)枚、?(?P<r>レストで)エナジーゾーンに置' + V('く', 'き') + END, lambda m: {'op': 'deckEnergy', 'n': int(m.group('n')), 'rested': 1})
    add(r'(?:あなたの)?山札をシャッフルし(?:て|、)?上から(?P<n>\d+)枚、?ライフの先頭に置' + V('く', 'き') + END, lambda m: {'op': 'lifeTop', 'n': int(m.group('n')), 'shuffle': 1})
    add(r'(?:あなたの)?山札を上から(?P<n>\d+)枚、表で(?:この)?(?:テリトリーに)?契約書として(?:テリトリーに)?つけ' + V('る', '') + END, lambda m: {'op': 'contract', 'n': int(m.group('n'))})
    add(r'(?:あなたの)?山札を下から(?P<n>\d+)枚ドロップ' + V('する', 'し') + MAY + END, lambda m: {'op': 'millBottom', 'n': int(m.group('n')), **({'may': 1} if m.group('may') else {})})
    add(r'相手は自身の山札を上から(?P<n>\d+)枚ドロップ' + V('する', 'し') + MAY + END, lambda m: {'op': 'mill', 'n': int(m.group('n')), 'who': 'opp', **({'may': 1} if m.group('may') else {})})
    add(r'相手は自身の山札を上から1枚公開' + V('する', 'し') + END, lambda m: {'op': 'oppRevealTop'})
    # --- 단일 동작 ---
    add(r'手札のこのカードを(?P<r>レストで)?登場させ' + V('る', '') + MAY + END, lambda m: {'op': 'summonSelfHand', **({'rested': 1} if m.group('r') else {}), **({'may': 1} if m.group('may') else {})})
    add(r'(?:手札の|あなたの手札の)このカードをドロップ' + V('する', 'し') + MAY + END, lambda m: {'op': 'pick', 'from': 'hand', 'to': 'drop', 'f': {'selfCard': 1}, 'n': 1, 'upto': 1 if m.group('may') else 0})
    add(r'このカードをライフ(?:ゾーン)?の先頭に置' + V('く', 'き') + END, lambda m: {'op': 'life', 'to': 'card'})
    add(r'このカードを山札に戻' + V('す', 'し') + MAY + END, lambda m: {'op': 'deckTop', 'to': 'card', **({'may': 1} if m.group('may') else {})})
    add(r'相手のライフの先頭をドロップゾーンに置' + V('く', 'き') + END, lambda m: {'op': 'lifeDrop', 'n': 1, 'who': 'opp'})
    add(r'相手(?:プレイヤー)?に(?P<n>\d+)ダメージ' + END, lambda m: {'op': 'lifeDmg', 'n': int(m.group('n')), 'who': 'opp'})
    add(r'あなたのエナジーを(?P<n>\d+)枚ドロップし(?P<k>\d+)枚引いてよい' + END, lambda m: [{'op': 'confirm', 'text': '이 효과를 쓸까요?', 'alt': 1, 'no': [{'op': 'stop'}]}, {'op': 'pick', 'from': 'energy', 'to': 'drop', 'f': {}, 'n': int(m.group('n')), 'upto': 0}, {'op': 'draw', 'n': int(m.group('k'))}])
    add(r'その(?:エース|ユニット|ユニットカード|カード)を(?P<v>山札の下に置|エナジーゾーンに置|ドロップゾーンに置|手札に戻|スタンド)' + V('く', 'き', 'す', 'し', 'する') + MAY + END,
        lambda m: {'op': {'山札の下に置': 'deckBottom', 'エナジーゾーンに置': 'energy', 'ドロップゾーンに置': 'drop', '手札に戻': 'bounce', 'スタンド': 'stand'}[m.group('v')], 'to': 'T', **({'may': 1} if m.group('may') else {})})
    add(r'あなたの(?P<o>他の)?ユニットを(?P<n>\d+)枚まで手札に戻' + V('す', 'し') + MAY + END, lambda m: [{'op': 'tgt', 'f': {'side': 'own', 'type': 'unit', **({'notSelf': 1} if m.group('o') else {})}, 'n': int(m.group('n')), 'upto': 1}, {'op': 'bounce', 'to': 'T'}])
    add(r'あなたの(?P<d>[^、。]*?)ユニットを(?P<n>\d+)枚ドロップ(?:させ|し)' + V('る', 'て', '') + MAY + END,
        lambda m: (lambda f: f is not None and [{'op': 'tgt', 'f': dict(f, side='own', type='unit'), 'n': int(m.group('n')), 'upto': 1 if m.group('may') else 0}, {'op': 'drop', 'to': 'T'}])(parse_desc(m.group('d')) if m.group('d') else {}))
    add(r'あなたの手札の(?P<d>[^、。]+?)を(?P<n>\d+)枚(?P<v>ドロップ|公開)' + V('する', 'し') + MAY + END,
        lambda m: (lambda f: f is not None and {'op': 'discard' if m.group('v') == 'ドロップ' else 'revealHand', 'n': int(m.group('n')), 'f': f, **({'may': 1, 'opt': 1} if m.group('may') else {})})(_zdesc(m.group('d'))))
    add(r'(?P<w>各プレイヤーは自身の|あなたの)ライフの先頭を手札に加え' + V('る', '') + MAY + END, lambda m: [{'op': 'lifeHand', 'n': 1, **({'may': 1} if m.group('may') else {})}] + ([{'op': 'lifeHand', 'n': 1, 'who': 'opp'}] if m.group('w').startswith('各') else []))
    add(r'相手は自身のライフの先頭を手札に加え' + V('る', '') + r'\.?' + END, lambda m: {'op': 'lifeHand', 'n': 1, 'who': 'opp'})
    add(r'あなたのエナジーを(?P<n>\d+)枚レストしてよい' + END, lambda m: {'op': 'payEnergy', 'n': int(m.group('n')), 'may': 1})
    add(r'あなたの裏のエナジー全てを表にする' + END, lambda m: {'op': 'flipAll'})
    add(r'あなたは手札を全てドロップし、(?P<n>\d+)枚引' + V('く', 'き') + END, lambda m: [{'op': 'discardAll'}, {'op': 'draw', 'n': int(m.group('n'))}])
    add(r'あなたは自分の手札を全て山札に戻してシャッフルし、(?P<n>\d+)枚引' + V('く', 'き') + END, lambda m: [{'op': 'handToDeck'}, {'op': 'draw', 'n': int(m.group('n'))}])
    add(r'手札が(?P<h>\d+)枚の各プレイヤーは(?P<n>\d+)枚引' + V('く', 'き') + END, lambda m: {'op': 'drawIfHand', 'hand': int(m.group('h')), 'n': int(m.group('n'))})
    add(r'(?:この|あなたの)テリトリーを閉じ' + V('る', '') + END, lambda m: {'op': 'closeTerr'})
    add(r'各プレイヤーは自身のテリトリーを閉じ' + V('る', '') + END, lambda m: {'op': 'closeTerrAll'})
    add(r'各プレイヤーのユニット全てをリムーブ' + V('する', 'し') + END, lambda m: {'op': 'removeAllUnits', 'who': 'both'})
    add(r'(?P<to>[^。]*?ユニット全て)をドロップさせ' + V('る', '') + END, lambda m: subj(re.sub(r'^相手の、', '相手の', m.group('to'))) and {'op': 'drop', 'to': subj(re.sub(r'^相手の、', '相手の', m.group('to')))})
    add(r'(?:そのターン中、)?アタックしているユニットの(?P<k>パワー|ヒット)を(?P<n>[+-]\d+)' + END, lambda m: {'op': 'pow' if m.group('k') == 'パワー' else 'hit', 'n': int(m.group('n')), 'to': {'all': {'attacking': 1, 'type': 'unit'}}})
    # 가장 파워가 높은/낮은 유닛
    add(r'(?P<w>相手|あなた)は自身のユニットで最もパワーの(?P<h>高い|低い)ユニットから(?P<n>\d+)枚(?:を)?(?P<v>ドロップさせ|ドロップし|ドロップ|手札に戻|山札の下に置)' + V('る', 'す', 'く', 'し', '') + END,
        lambda m: {'op': 'pickExtreme', 'who': 'opp' if m.group('w') == '相手' else 'me', 'high': m.group('h') == '高い', 'n': int(m.group('n')), 'res': 'bounce' if '手札' in m.group('v') else 'bottom' if '山札' in m.group('v') else 'drop'})
    # 기간 제한
    add(r'次の相手(?:の)?ターン中、相手は(?P<n>\d+)回までしかアタックができない' + END, lambda m: {'op': 'restrict', 'r': {'kind': 'attackLimit', 'n': int(m.group('n')), 'who': 'opp', 'dur': 'nextOpp'}})
    add(r'次の相手(?:の)?ターン中、相手は【デコイ】を持たないユニットにアタックできない' + END, lambda m: {'op': 'restrict', 'r': {'kind': 'attackDecoyOnly', 'who': 'opp', 'dur': 'nextOpp'}})
    add(r'(?:そのターン中、)?相手は総?コスト(?P<n>\d+)以下のコマンドをプレイできない' + END, lambda m: {'op': 'restrict', 'r': {'kind': 'noCmdCostLE', 'n': int(m.group('n')), 'who': 'opp', 'dur': 'turn'}})
    add(r'次のあなたのターン開始時まで、各プレイヤーはユニットでアタックができない' + END, lambda m: {'op': 'restrict', 'r': {'kind': 'noAttack', 'who': 'both', 'dur': 'untilMyNext'}})
    # 「AするかB」 선택
    add(r'(?P<a>そのターン中、[^、。]+?)するか、(?P<b>[^。]+?)' + END, lambda m: (lambda a, b: a is not None and b is not None and {'op': 'choose', 'opts': [a, b], 'labels': ['앞의 효과', '뒤의 효과']})(parse_effects(m.group('a')), parse_effects('そのターン中、' + m.group('b'))))
    # 스킬 N회 반복
    def skill_rep(m):
        sk = _SKILL.get('s')
        body = parse_effects(m.group('x'))
        if not sk or body is None:
            return None
        out = []
        for i in range(int(m.group('n'))):
            out += [{'op': 'confirm', 'text': f'【스킬】을 발동할까요? ({i + 1}/{m.group("n")})', 'alt': 1, 'no': [{'op': 'stop'}], 'need': sk}] + [dict(x) for x in sk] + [dict(x) for x in body]
        return out
    add(r'【スキル】を(?P<n>\d+)回まで発動(?:させ|し)、1回につき、(?P<x>[^。]+)' + END, skill_rep)
    # --- 13차 ---
    add(r'(?P<to>[^。]*?ユニット全て)は、?(?:そのターン中、)?(?P<n>\d+)ダメージでも受けるとドロップする' + END,
        lambda m: subj(re.sub(r'^相手の、', '相手の', m.group('to'))) and {'op': 'kw', 'kw': 'fragile', 'to': subj(re.sub(r'^相手の、', '相手の', m.group('to')))})
    add(r'あなたの、?(?P<d>[^。]*?)であるエナジーを(?P<n>\d+)枚(?P<upto>まで)?対象と' + V('し', 'する') + END,
        lambda m: (lambda f: f is not None and {'op': 'tgt', 'zone': 'energy', 'f': dict(f, side='own'), 'n': int(m.group('n')), 'upto': 1 if m.group('upto') else 0})(_zdesc(m.group('d'))))
    add(r'(?P<w>相手|あなた)の(?P<z>ユニット|手札)(?P<k>\d+)枚につき、(?P<n>\d+)枚まで引' + V('く', 'き') + END,
        lambda m: {'op': 'drawUpTo', 'n': int(m.group('n')), 'per': {'side': 'opp' if m.group('w') == '相手' else 'own', 'zone': 'field' if m.group('z') == 'ユニット' else 'hand', 'k': int(m.group('k'))}})
    add(r'あなたのフィールドの(?P<l>(?:⁅(?:ハート|スペード|ダイヤ|クラブ)⁆と?)+)を(?P<n>\d+)枚ずつドロップ' + V('する', 'し') + MAY + END,
        lambda m: ([{'op': 'confirm', 'text': '이 효과를 쓸까요?', 'alt': 1, 'no': [{'op': 'stop'}]}] if m.group('may') else []) + sum([[{'op': 'tgt', 'f': {'side': 'own', 'type': 'unit', 'attr': [a]}, 'n': int(m.group('n')), 'upto': 0}, {'op': 'drop', 'to': 'T'}] for a in re.findall('ハート|スペード|ダイヤ|クラブ', m.group('l'))], []))
    add(r'あなたの山札を下から(?P<n>\d+)枚公開し、山札をシャッフル' + V('する', 'し') + END, lambda m: [{'op': 'revealBottom', 'n': int(m.group('n'))}, {'op': 'shuffle'}])
    add(r'あなたのライフの先頭をエナジーゾーンに置き、あなたの表のエナジーを(?P<n>\d+)枚(?P<up>まで)?ライフの先頭に置' + V('く', 'き') + END,
        lambda m: [{'op': 'lifeEnergy', 'n': 1}, {'op': 'pick', 'from': 'energy', 'to': 'life', 'f': {'faceUp': 1}, 'n': int(m.group('n')), 'upto': 1 if m.group('up') else 0}])
    add(r'あなたの手札の、?対象と同じコストの(?P<d>[^、。]*?)を(?P<n>\d+)枚(?P<up>まで)?登場させ' + V('る', '') + END,
        lambda m: (lambda f: f is not None and {'op': 'pick', 'from': 'hand', 'to': 'field', 'f': dict(f, costEqT=1), 'n': int(m.group('n')), 'upto': 1 if m.group('up') else 0})(_zdesc(m.group('d'))))
    add(r'あなたの、?手札かドロップゾーンから(?P<d>[^、。]+?)を(?P<n>\d+)枚(?P<up>まで)?(?P<r>レストで)?登場させ' + V('る', '') + END,
        lambda m: (lambda f: f is not None and {'op': 'pick', 'from': 'handOrDrop', 'to': 'field', 'f': f, 'n': int(m.group('n')), 'upto': 1 if m.group('up') else 0, **({'rested': 1} if m.group('r') else {})})(_zdesc(m.group('d'))))
    add(r'その(?:ドロップした)?(?:ユニットカード|ユニット|カード)を(?:手札に戻すか(?:レストで)?登場させ|(?:レストで)?登場させるか手札に戻)' + V('る', 'す', '') + END,
        lambda m: {'op': 'choose', 'opts': [[{'op': 'bounce', 'to': 'T'}], [{'op': 'summonRested' if 'レスト' in m.group(0) else 'summon', 'to': 'T'}]], 'labels': ['패로 되돌린다', '레스트로 등장시킨다' if 'レスト' in m.group(0) else '등장시킨다']})
    add(r'(?:各プレイヤーは)?自身の手札が(?P<n>\d+)枚になるように引' + V('く', 'き') + END, lambda m: [{'op': 'drawTo', 'n': int(m.group('n'))}, {'op': 'drawTo', 'n': int(m.group('n')), 'who': 'opp'}])
    add(r'あなたの、?色を持たないエナジー(?P<k>\d+)枚につき、(?P<x>[^。]+)' + END,
        lambda m: (lambda r: r is not None and [dict(st, per={'zone': 'energyDown', 'k': int(m.group('k')), 'side': 'own'}) if st.get('op') not in ('tgt', 'if') else st for st in r])(parse_effects(m.group('x'))))
    add(r'相手は自身の手札を全て公開し、あなたはその中の(?P<d>[^、。]+?)を(?P<n>\d+)枚選び、ドロップさせ' + V('る', '') + END,
        lambda m: (lambda f: f is not None and {'op': 'pick', 'from': 'hand', 'to': 'drop', 'f': dict(f, side='opp'), 'n': int(m.group('n')), 'upto': 0})(_zdesc(m.group('d'))))
    add(r'このユニットを含むあなたのユニットを(?P<n>\d+)枚ドロップ' + V('する', 'し') + MAY + END,
        lambda m: ([{'op': 'confirm', 'text': '이 효과를 쓸까요?', 'alt': 1, 'no': [{'op': 'stop'}]}] if m.group('may') else []) + [{'op': 'tgt', 'f': {'side': 'own', 'type': 'unit', 'notSelf': 1}, 'n': int(m.group('n')) - 1, 'upto': 0}, {'op': 'drop', 'to': 'T'}, {'op': 'drop', 'to': 'self'}])
    add(r'あなたのスタンドしているエナジーを(?P<n>\d+)枚(?P<up>まで)?リムーブ' + V('する', 'し') + END, lambda m: {'op': 'pick', 'from': 'energy', 'to': 'remove', 'f': {'standE': 1}, 'n': int(m.group('n')), 'upto': 1 if m.group('up') else 0})
    add(r'あなたはテリトリーを閉じ、追加の1ターンを行' + V('う', 'い') + END, lambda m: [{'op': 'closeTerr'}, {'op': 'extraTurn'}])
    add(r'ドロップしたカードそれぞれと同じコストのユニット全てをドロップさせ' + V('る', '') + END, lambda m: {'op': 'dropCostMatchMilled'})
    add(r'対象を山札に戻し、山札をシャッフル' + V('する', 'し') + END, lambda m: [{'op': 'deckTop', 'to': 'T'}, {'op': 'shuffleT'}])
    add(r'(?:そのユニット|対象)のヒット(?P<k>\d+)につき、(?P<x>[^。]+)' + END,
        lambda m: (lambda r: r is not None and [dict(st, per={'tHit': 1}) if st.get('op') not in ('tgt', 'if') else st for st in r])(parse_effects(m.group('x'))))
    add(r'各プレイヤーは自身のドロップゾーンの(?P<d>[^、。]+?)を(?P<n>\d+)枚(?P<up>まで)?手札に戻' + V('す', 'し') + END,
        lambda m: (lambda f: f is not None and [{'op': 'pick', 'from': 'drop', 'to': 'hand', 'f': f, 'n': int(m.group('n')), 'upto': 1 if m.group('up') else 0}, {'op': 'asOpp', 'do': [{'op': 'pick', 'from': 'drop', 'to': 'hand', 'f': f, 'n': int(m.group('n')), 'upto': 1 if m.group('up') else 0}]}])(_zdesc(m.group('d'))))
    add(r'あなたのエナジーゾーンの(?P<d>[^、。]+?)を(?P<n>\d+)枚(?:まで)?対象とし、対象をコストを払わずプレイ' + V('する', 'し') + MAY + END,
        lambda m: (lambda f: f is not None and {'op': 'playFree', 'from': 'energy', 'f': f, 'may': 1})(_zdesc(m.group('d'))))
    add(r'あなたの伏せたカードを(?P<n>\d+)枚(?P<up>まで)?対象とし、対象を(?P<v>エナジーゾーンに置|手札に戻|ドロップさせ)' + V('く', 'す', 'る', 'き', 'し', '') + END,
        lambda m: {'op': 'pick', 'from': 'set', 'to': 'energy' if 'エナジー' in m.group('v') else 'hand' if '手札' in m.group('v') else 'drop', 'f': {}, 'n': int(m.group('n')), 'upto': 1 if m.group('up') else 0})
    add(r'(?:あなたの)?山札を上から(?P<n>\d+)枚見て、それ(?:ら)?を(?P<w>望む枚数)?フィールドに伏せ(?:る|、残りを(?:望む順で)?山札の上に(?:望む順で)?置く)' + END,
        lambda m: {'op': 'look', 'n': int(m.group('n')), 'f': {}, 'k': int(m.group('n')) if not m.group('w') else int(m.group('n')), 'to': 'set', 'rest': 'top', **({} if m.group('w') else {})} if m.group('w') else {'op': 'look', 'n': int(m.group('n')), 'f': {}, 'k': 99, 'to': 'set', 'rest': 'top'})
    add(r'あなたは(?P<n>\d+)枚引いて手札を(?P<k>\d+)枚(?P<v>リムーブ|ドロップ)' + V('する', 'し') + END,
        lambda m: [{'op': 'draw', 'n': int(m.group('n'))}, {'op': 'pick', 'from': 'hand', 'to': 'remove', 'f': {}, 'n': int(m.group('k')), 'upto': 0} if m.group('v') == 'リムーブ' else {'op': 'discard', 'n': int(m.group('k'))}])
    # --- 14차 ---
    add(r'この【夢を?見ない】でドロップした(?P<d>[^、。]*?)を(?P<r>レストで)?登場させ' + V('る', '') + END,
        lambda m: (lambda f: f is not None and {'op': 'summonRested' if m.group('r') else 'summon', 'to': 'ycard', 'f': f})(_zdesc(m.group('d'))))
    add(r'あなたの山札を上から(?P<n>\d+)枚、表を見ずに裏(?:向き)?のままテリトリーにログとしてつけ' + V('る', '') + MAY + END,
        lambda m: [{'op': 'logAttach'} for _ in range(int(m.group('n')))])
    add(r'あなたのつけたログを(?P<n>\d+)枚(?P<v>リムーブ|ドロップ)' + V('する', 'し') + MAY + END, lambda m: {'op': 'logMove', 'n': int(m.group('n')), 'to': 'remove' if m.group('v') == 'リムーブ' else 'drop'})
    add(r'あなたのつけたログ(?:全てを|を全て)(?P<v>リムーブ|ドロップ)' + V('する', 'し') + MAY + END, lambda m: {'op': 'logMove', 'n': 99, 'to': 'remove' if m.group('v') == 'リムーブ' else 'drop'})
    add(r'あなたのつけたログを全て公開' + V('する', 'し') + MAY + END, lambda m: {'op': 'logReveal'})
    add(r'ドロップしたログ(?P<k>\d+)枚につき、(?P<x>[^。]+)' + END,
        lambda m: (lambda r: r is not None and [dict(st, per={'milled': 1, 'k': int(m.group('k'))}) if st.get('op') not in ('tgt', 'if') else st for st in r])(parse_effects(m.group('x'))))
    add(r'ドロップしたカードのコスト(?P<k>\d+)につき、(?P<x>[^。]+)' + END,
        lambda m: (lambda r: r is not None and [dict(st, per={'milledCost': 1, 'k': int(m.group('k'))}) if st.get('op') not in ('tgt', 'if') else st for st in r])(parse_effects(m.group('x'))))
    add(r'ドロップした(?P<d>[^、。]*?)(?P<k>\d+)枚につき、(?P<x>[^。]+)' + END,
        lambda m: (lambda f, r: f is not None and r is not None and [dict(st, per={'milled': 1, 'f': f, 'k': int(m.group('k'))}) if st.get('op') not in ('tgt', 'if') else st for st in r])(_zdesc(m.group('d')), parse_effects(m.group('x'))))
    add(r'レストしたエナジー(?P<k>\d+)枚につき、(?P<x>[^。]+)' + END,
        lambda m: (lambda r: r is not None and [dict(st, per={'milled': 1, 'k': int(m.group('k'))}) if st.get('op') not in ('tgt', 'if') else st for st in r])(parse_effects(m.group('x'))))
    add(r'相手の手札(?P<k>\d+)枚につき、(?P<x>[^。]+)' + END,
        lambda m: (lambda r: r is not None and [dict(st, per={'side': 'opp', 'zone': 'hand', 'k': int(m.group('k'))}) if st.get('op') not in ('tgt', 'if') else st for st in r])(parse_effects(m.group('x'))))
    add(r'あなたは(?P<x>ユニットを\d+枚(?:まで)?対象とし、[^。]+)' + END, lambda m: parse_effects(m.group('x')))
    add(r'あなたの(?P<c>黒|白|青|赤)のエナジーを望む枚数レスト' + V('する', 'し') + MAY + END,
        lambda m: {'op': 'pick', 'from': 'energy', 'to': 'rest', 'f': {'color': [{'黒': 'black', '白': 'white', '青': 'blue', '赤': 'red'}[m.group('c')]], 'standE': 1}, 'n': 99, 'upto': 1})
    add(r'(?P<to>このユニット|対象|そのユニット)は、?(?:相手の)?コマンドの対象になら(?:ない|ず)' + END, lambda m: {'op': 'kw', 'kw': 'cmdImmune', 'to': subj(m.group('to'))})
    add(r'対象とこの(?P<w>カード|ユニット)を(?P<v>エナジーゾーンに置|手札に戻|リムーブ|山札の下に置|ドロップさせ)' + V('く', 'す', 'する', 'る', '') + END,
        lambda m: (lambda op: [{'op': op, 'to': 'T'}, {'op': op, 'to': 'card' if m.group('w') == 'カード' else 'self'}])({'エナジーゾーンに置': 'energy', '手札に戻': 'bounce', 'リムーブ': 'remove', '山札の下に置': 'deckBottom', 'ドロップさせ': 'drop'}[m.group('v')]))
    add(r'あなたの山札を上から1枚見て、(?:それを)?(?:山札の上に置くかドロップ|ドロップするか山札の上に置)' + V('する', 'く') + END,
        lambda m: [{'op': 'look', 'n': 1, 'f': {}, 'k': 0, 'to': 'hand', 'rest': 'top'}, {'op': 'choose', 'opts': [[], [{'op': 'mill', 'n': 1}]], 'labels': ['덱 위에 그대로 둔다', '드롭한다']}])
    add(r'あなたの山札を上から1枚見て、それをフィールドに伏せるか山札の上に置' + V('く') + END,
        lambda m: [{'op': 'look', 'n': 1, 'f': {}, 'k': 0, 'to': 'hand', 'rest': 'top'}, {'op': 'choose', 'opts': [[{'op': 'look', 'n': 1, 'f': {}, 'k': 1, 'to': 'set', 'rest': 'top'}], []], 'labels': ['필드에 엎어 둔다', '덱 위에 그대로 둔다']}])
    add(r'相手は自身のライフの先頭をドロップ' + V('する', 'し') + r'てよい' + END,
        lambda m: {'op': 'choose', 'who': 'opp', 'opts': [[{'op': 'lifeDrop', 'n': 1, 'who': 'opp'}], []], 'labels': ['라이프 맨 앞을 드롭한다', '드롭하지 않는다']})
    add(r'相手は自身の山札を上から(?P<n>\d+)枚リムーブすることで、このアタックを中止できる' + END,
        lambda m: {'op': 'choose', 'who': 'opp', 'opts': [[{'op': 'asOpp', 'do': [{'op': 'deckRemove', 'n': int(m.group('n'))}]}, {'op': 'cancelAttack'}], []], 'labels': [f'덱 위 {m.group("n")}장을 리무브하고 공격을 중지시킨다', '그대로 둔다'], 'dis': {'k': 0, 'c': [{'oppDeckLT': int(m.group('n'))}]}})
    add(r'このアタックを中止' + V('する', 'し') + END, lambda m: {'op': 'cancelAttack'})
    add(r'あなたはゲームに勝利' + V('する', 'し') + END, lambda m: {'op': 'winGame'})
    add(r'相手のライフの先頭から(?P<n>\d+)枚をリムーブ' + V('する', 'し') + END, lambda m: {'op': 'asOpp', 'do': [{'op': 'lifeRemove', 'n': int(m.group('n'))}]})
    add(r'あなたの(?P<d>[^、。]*?)を(?P<n>\d+)枚望む順で山札の下に置' + V('く', 'き', 'い') + MAY + END,
        lambda m: (lambda f: f is not None and [{'op': 'tgt', 'f': dict(f, side='own'), 'n': int(m.group('n')), 'upto': 0}, {'op': 'deckBottom', 'to': 'T'}])(_zdesc(m.group('d'))))
    add(r'次のエンドフェイズ開始時に?、?(?P<x>[^。]+)' + END,
        lambda m: (lambda r: r is not None and {'op': 'delay', 'at': 'endStart', 'do': r})(parse_effects(m.group('x').replace('そのユニット', '対象').replace('登場させたユニット全て', '対象'))))
    add(r'あなたの(?P<d>[^、。]*?)のエース(?P<n>\d+)枚と、手札かフィールドの(?P<e>[^、。]*?)エースカード(?P<k>\d+)枚をそれぞれドロップ' + V('する', 'し') + MAY + END,
        lambda m: None)
    # --- 15차 ---
    add(r'相手は手札を(?P<n>\d+)枚ドロップ' + V('する', 'し') + r'てよい' + END,
        lambda m: {'op': 'choose', 'who': 'opp', 'opts': [[{'op': 'asOpp', 'do': [{'op': 'discard', 'n': int(m.group('n'))}]}], []], 'labels': [f'패 {m.group("n")}장을 드롭한다', '드롭하지 않는다']})
    add(r'(?P<to>その登場させたユニット|登場させたユニット全て|登場させたユニット|その登場したユニット|登場した対象)を(?P<v>ドロップ|手札に戻|リムーブ|山札の下に置)' + V('する', 'す', 'く', 'し', 'き') + END,
        lambda m: {'op': {'ドロップ': 'drop', '手札に戻': 'bounce', 'リムーブ': 'remove', '山札の下に置': 'deckBottom'}[m.group('v')], 'to': 'summoned'})
    add(r'(?:そのターン中、)?(?P<to>その登場させたユニット|登場させたユニット全て|登場させたユニット)のパワーを(?P<n>[+-]\d+)' + END, lambda m: {'op': 'pow', 'n': int(m.group('n')), 'to': 'summoned'})
    add(r'相手の、?(?:パワーが)?(?P<w>このユニット|対象)(?:のパワー)?以下のパワーの、?ユニット全てを(?P<v>手札に戻|ドロップさせ)' + V('す', 'る', 'し', '') + END,
        lambda m: {'op': 'bounce' if m.group('v') == '手札に戻' else 'drop', 'to': {'all': {'side': 'opp', 'type': 'unit', ('powLE_self' if m.group('w') == 'このユニット' else 'powLE_T'): 1}}})
    add(r'対象のパワー以下のパワーの、相手のユニット全てを(?P<v>手札に戻|ドロップさせ)' + V('す', 'る', 'し', '') + END,
        lambda m: {'op': 'bounce' if m.group('v') == '手札に戻' else 'drop', 'to': {'all': {'side': 'opp', 'type': 'unit', 'powLE_T': 1}}})
    add(r'相手の、パワーがこのユニットのパワー以下のユニット全てを(?P<v>手札に戻|ドロップさせ)' + V('す', 'る', 'し', '') + END,
        lambda m: {'op': 'bounce' if m.group('v') == '手札に戻' else 'drop', 'to': {'all': {'side': 'opp', 'type': 'unit', 'powLE_self': 1}}})
    add(r'相手の、?対象と同じカード名のユニット全てを(?P<v>手札に戻|ドロップさせ)' + V('す', 'る', 'し', '') + END,
        lambda m: {'op': 'bounce' if m.group('v') == '手札に戻' else 'drop', 'to': {'all': {'side': 'opp', 'type': 'unit', 'sameNameT': 1}}})
    add(r'あなたのユニットを1枚と相手のユニットを1枚対象とし、対象を(?P<v>手札に戻|ドロップさせ)' + V('す', 'る', 'し', '') + END,
        lambda m: [{'op': 'tgt', 'f': {'side': 'own', 'type': 'unit'}, 'n': 1, 'upto': 0, 'save': 'A'}, {'op': 'tgt', 'f': {'side': 'opp', 'type': 'unit'}, 'n': 1, 'upto': 0, 'save': 'B', 'add': 1}, {'op': 'bounce' if m.group('v') == '手札に戻' else 'drop', 'to': 'T'}])
    add(r'あなたの山札をシャッフルして上から1枚見て、手札に加えるかライフの先頭に置' + V('く', 'き') + END,
        lambda m: [{'op': 'shuffle'}, {'op': 'peekTop', 'n': 1}, {'op': 'choose', 'opts': [[{'op': 'draw', 'n': 1}], [{'op': 'lifeTop', 'n': 1}]], 'labels': ['패에 넣는다', '라이프 맨 앞에 놓는다']}])
    # --- 16차 ---
    add(r'(?:そのターン中、)?このユニットのヒットをその[^、。]*?のヒット分、増や' + V('す', 'し') + END, lambda m: {'op': 'hitByMilled', 'to': 'self'})
    # --- 17차 ---
    add(r'(?P<i>\d)枚目の対象に(?P<n>\d+)ダメージ' + END, lambda m: {'op': 'dmg', 'n': int(m.group('n')), 'to': 'T' + str(int(m.group('i')) - 1)})
    add(r'(?:そのターン中、)?(?P<i>\d)枚目の対象のパワーを(?P<n>[+-]\d+)' + END, lambda m: {'op': 'pow', 'n': int(m.group('n')), 'to': 'T' + str(int(m.group('i')) - 1)})
    add(r'そのバトル終了時、(?P<x>[^。]+)' + END, lambda m: (lambda r: r is not None and {'op': 'delay', 'at': 'attackEnd', 'do': r})(parse_effects(m.group('x'))))
    add(r'そのブロックしたユニットとこのユニットを(?P<v>手札に戻|ドロップさせ|リムーブ)' + V('す', 'る', 'する', '') + END,
        lambda m: (lambda op: [{'op': op, 'to': 'vs'}, {'op': op, 'to': 'self'}])({'手札に戻': 'bounce', 'ドロップさせ': 'drop', 'リムーブ': 'remove'}[m.group('v')]))
    add(r'コスト(?P<n>\d+)以下のバトル相手に(?P<d>\d+)ダメージ' + END, lambda m: {'op': 'if', 'c': [{'vsF': {'costLE': int(m.group('n'))}}], 'then': [{'op': 'dmg', 'n': int(m.group('d')), 'to': 'vs'}]})
    add(r'あなたは(?P<n>\d+)枚引き、手札を(?P<k>\d+)枚山札の上か下に置' + V('く', 'き') + END,
        lambda m: [{'op': 'draw', 'n': int(m.group('n'))}, {'op': 'choose', 'opts': [[{'op': 'pick', 'from': 'hand', 'to': 'top', 'f': {}, 'n': int(m.group('k')), 'upto': 0}], [{'op': 'pick', 'from': 'hand', 'to': 'bottom', 'f': {}, 'n': int(m.group('k')), 'upto': 0}]], 'labels': ['덱 위에 놓는다', '덱 아래에 놓는다']}])
    # --- 18차 ---
    add(r'あなたの(?P<a>黒|白|青|赤)と(?P<b>黒|白|青|赤)のエナジーをそれぞれ1枚ずつドロップ' + V('する', 'し') + MAY + END,
        lambda m: ([{'op': 'confirm', 'text': '이 효과를 쓸까요?', 'alt': 1, 'no': [{'op': 'stop'}]}] if m.group('may') else []) + [{'op': 'pick', 'from': 'energy', 'to': 'drop', 'f': {'color': [{"黒": "black", "白": "white", "青": "blue", "赤": "red"}[m.group(x)]]}, 'n': 1, 'upto': 0} for x in ('a', 'b')])
    add(r'あなたの、ユニット、手札、テリトリー全てをリムーブ' + V('する', 'し') + END, lambda m: {'op': 'removeAllOwn'})
    add(r'あなたのエナジーを望む枚数裏に' + V('する', 'し') + END, lambda m: {'op': 'pick', 'from': 'energy', 'to': 'flip', 'f': {'faceUp': 1}, 'n': 99, 'upto': 1})
    add(r'裏にしたエナジー(?P<k>\d+)枚につき、(?P<x>[^。]+)' + END,
        lambda m: (lambda r: r is not None and [dict(st, per={'milled': 1, 'k': int(m.group('k'))}) if st.get('op') not in ('tgt', 'if') else st for st in r])(parse_effects(m.group('x'))))
    add(r'あなたは手札を(?P<n>\d+)枚公開' + V('する', 'し') + END, lambda m: {'op': 'revealHand', 'n': int(m.group('n'))})
    add(r'あなたの手札の(?P<d>[^、。]*?)を(?P<n>\d+)枚(?P<up>まで)?公開' + V('する', 'し') + END,
        lambda m: (lambda f: f is not None and {'op': 'revealHand', 'n': int(m.group('n')), 'f': f, **({'upto': 1} if m.group('up') else {})})(_zdesc(m.group('d'))))
    add(r'公開されたカードと同じコストの相手のユニット全てを(?P<v>手札に戻|ドロップさせ)' + V('す', 'る', 'し', '') + END,
        lambda m: {'op': 'bounce' if m.group('v') == '手札に戻' else 'drop', 'to': {'all': {'side': 'opp', 'type': 'unit', 'costEqMilled': 1}}})
    add(r'あなたのドロップゾーンを(?P<n>\d+)枚リムーブ' + V('する', 'し') + MAY + END, lambda m: {'op': 'pick', 'from': 'drop', 'to': 'remove', 'f': {}, 'n': int(m.group('n')), 'upto': 0})
    add(r'(?:次のエンドフェイズ開始時、)?相手のテリトリーを開放' + V('する', 'し') + END, lambda m: {'op': 'delay', 'at': 'endStart', 'do': [{'op': 'openTerrFree', 'who': 'opp'}]} if m.group(0).startswith('次') else {'op': 'openTerrFree', 'who': 'opp'})
    add(r'あなたの「(?P<nm>[^」]+)」を開放' + V('する', 'し') + END, lambda m: {'op': 'openTerrFree', 'name': m.group('nm')})
    add(r'その追加ターン中、あなたは「(?P<nm>[^」]+)」を含むユニットでしかアタックできない' + END, lambda m: {'op': 'restrict', 'r': {'kind': 'attackerName', 'name': m.group('nm'), 'who': 'me', 'dur': 'nextTurnOnly'}})
    # --- 19차: 神衣 ---
    add(r'このカードをその(?:登場させた|登場した)?ユニットに(?:重ねて)?着せ' + V('る', '') + END, lambda m: {'op': 'dressTo', 'to': 'summoned'})
    add(r'このカードをあなたの(?P<d>[^、。]*?)ユニットに(?:重ねて)?着せ' + V('る', '') + MAY + END,
        lambda m: (lambda f: f is not None and [{'op': 'tgt', 'f': dict(f, side='own', type='unit'), 'n': 1, 'upto': 1}, {'op': 'dressTo', 'to': 'T'}])(parse_desc(m.group('d')) if m.group('d') else {}))
    add(r'あなたの(?P<d>[^、。]*?)ユニット1枚をこのユニットに(?:重ねて)?着せ' + V('る', '') + MAY + END,
        lambda m: (lambda f: f is not None and [{'op': 'tgt', 'f': dict(f, side='own', type='unit', notSelf=1), 'n': 1, 'upto': 1}, {'op': 'dressUnitOnto', 'from': 'T'}])(parse_desc(m.group('d')) if m.group('d') else {}))
    # --- 20차 ---
    add(r'相手は対象を山札に戻してシャッフル' + V('する', 'し') + END, lambda m: [{'op': 'deckTop', 'to': 'T'}, {'op': 'shuffle', 'who': 'opp'}])
    add(r'対象をこのユニットに(?:重ねて)?(?:着せ|つけ)' + V('る', '') + END, lambda m: {'op': 'attachT', 'to': 'self'})
    add(r'あなたの伏せたカードを全て公開' + V('する', 'し') + END, lambda m: {'op': 'revealSet'})
    add(r'相手は自身のライフの先頭を公開' + V('する', 'し') + END, lambda m: {'op': 'revealLifeTop', 'who': 'opp'})
    add(r'(?:対象に)?このユニットのパワー分のダメージを与え' + V('る', '') + END, lambda m: {'op': 'dmgPow', 'from': 'self', 'to': 'T'})
    add(r'(?:そのターン中、)?対象のパワー分、このユニットのパワーを増加させ' + V('る', '') + END, lambda m: {'op': 'powByT', 'to': 'self'})
    add(r'あなたの称号「(?P<t>[^」]+)」のテリトリーを開放' + V('する', 'し') + MAY + END, lambda m: {'op': 'openTerrFree', 'title': m.group('t')})
    # --- 21차 ---
    add(r'対象を山札の上に(?:望む順で)?置き、このカードをリムーブ' + V('する', 'し') + END, lambda m: [{'op': 'deckTop', 'to': 'T'}, {'op': 'remove', 'to': 'card'}])
    add(r'対象にこのカードを(?:重ねて)?(?:つけ|着せ)' + V('る', '') + END, lambda m: {'op': 'dressTo', 'to': 'T'})
    add(r'あなたの手札を(?P<n>\d+)枚、あなたの(?P<z>ドロップゾーン|エナジーゾーン)の(?P<d>[^、。]+?)(?P<k>\d+)枚と入れ替え' + V('る', '') + MAY + END,
        lambda m: (lambda f, z: f is not None and [{'op': 'pick', 'from': z, 'to': 'hand', 'f': f, 'n': int(m.group('k')), 'upto': 0},
                                                   {'op': 'if', 'c': [{'did': 1}], 'then': [{'op': 'discard', 'n': int(m.group('n'))} if z == 'drop' else {'op': 'pick', 'from': 'hand', 'to': 'energy', 'f': {}, 'n': int(m.group('n')), 'upto': 0}]}])(_zdesc(m.group('d')), 'drop' if m.group('z') == 'ドロップゾーン' else 'energy'))
    # --- 22차: それぞれ1枚まで ---
    add(r'あなたの山札を上から(?P<n>\d+)枚見て、その中の、?(?P<d>.+?)をそれぞれ1枚まで(?:公開して)?(?P<v>手札に加え|登場させ)、残りを(?:望む順で)?山札の(?P<r>下|上)に置' + V('く', 'き') + END,
        lambda m: (lambda fs: fs and {'op': 'look', 'n': int(m.group('n')), 'f': {'or': fs}, 'k': len(fs), 'each': fs, 'to': 'hand' if m.group('v') == '手札に加え' else 'field', 'rest': 'bottom' if m.group('r') == '下' else 'top'})(_each_filters(m.group('d'))))
    add(r'あなたの(?P<z>手札|ドロップゾーン|エナジーゾーン|エナジー)(?:から|の)、?(?P<d>.+?)をそれぞれ1枚まで(?P<r>レストで)?(?P<v>登場させ|手札に戻|手札に加え)' + V('る', 'す', '') + END,
        lambda m: (lambda fs: fs and {'op': 'pick', 'from': {'手札': 'hand', 'ドロップゾーン': 'drop'}.get(m.group('z'), 'energy'), 'to': 'field' if m.group('v') == '登場させ' else 'hand', 'f': {'or': fs}, 'n': len(fs), 'upto': 1, 'each': fs, **({'rested': 1} if m.group('r') else {})})(_each_filters(m.group('d'))))
    add(r'あなたのドロップゾーンの、?(?P<d>.+?)をそれぞれ1枚まで対象と' + V('し', 'する') + END,
        lambda m: (lambda fs: fs and {'op': 'tgt', 'zone': 'drop', 'f': {'or': fs}, 'n': len(fs), 'upto': 1, 'each': fs})(_each_filters(m.group('d'))))
    # --- 23차 ---
    add(r'相手は自身のドロップゾーンの(?P<d>[^、。]+?)を(?P<n>\d+)枚(?P<up>まで)?山札の(?P<w>上|下)に置' + V('く', 'き') + END,
        lambda m: (lambda f: f is not None and {'op': 'asOpp', 'do': [{'op': 'pick', 'from': 'drop', 'to': 'top' if m.group('w') == '上' else 'bottom', 'f': f, 'n': int(m.group('n')), 'upto': 1 if m.group('up') else 0}]})(_zdesc(m.group('d'))))
    add(r'相手は自身の(?P<d>[^、。]*?)ユニット全てを(?:望む順で)?山札の下に置' + V('く', 'き') + END,
        lambda m: (lambda f: f is not None and {'op': 'deckBottom', 'to': {'all': dict(f, side='opp', type='unit')}})(parse_desc(m.group('d')) if m.group('d') else {}))
    add(r'あなたは手札が(?P<n>\d+)枚になるように引' + V('く', 'き') + END, lambda m: {'op': 'drawTo', 'n': int(m.group('n'))})
    # --- 24차: 카드별 특수 효과 ---
    OPPU = {'side': 'opp', 'type': 'unit'}
    add(r'それが持つアイコン能力(?P<k>\d+)つにつき、(?:そのターン中、)?そのユニットのパワーを(?P<n>[+-]\d+)' + END, lambda m: {'op': 'pow', 'n': int(m.group('n')), 'to': 'evt', 'per': {'cnt': 'evIcons', 'k': int(m.group('k'))}})
    add(r'そのユニットと共通の属性を持つ、あなたのドロップゾーン(?P<k>\d+)枚につき、(?:そのターン中、)?そのユニットのパワーを(?P<n>[+-]\d+)' + END,
        lambda m: {'op': 'pow', 'n': int(m.group('n')), 'to': 'evt', 'per': {'cnt': 'dropShareAttrEvt', 'k': int(m.group('k'))}})
    add(r'(?P<k>\d+)枚以上あるなら、さらにヒットを(?P<n>[+-]\d+)' + END, lambda m: {'op': 'if', 'c': [{'dropShareAttrEvtGE': int(m.group('k'))}], 'then': [{'op': 'hit', 'n': int(m.group('n')), 'to': 'evt'}]})
    add(r'あなたの手札から、アタックしたユニットより総コストが小さい、共通の属性を持つユニットカードを(?P<n>\d+)枚まで登場させ' + V('る', '') + END,
        lambda m: {'op': 'pick', 'from': 'hand', 'to': 'field', 'f': {'type': 'unit', 'costLTevt': 1, 'shareAttrEvt': 1}, 'n': int(m.group('n')), 'upto': 1})
    add(r'あなたの手札の、?アタックしたユニットより総コストが小さい、共通の属性を持つユニットカードを(?P<n>\d+)枚まで登場させ' + V('る', '') + END,
        lambda m: {'op': 'pick', 'from': 'hand', 'to': 'field', 'f': {'type': 'unit', 'costLTevt': 1, 'shareAttrEvt': 1}, 'n': int(m.group('n')), 'upto': 1})
    add(r'その(?:ドロップした)?(?P<d>[^、。]*?)ユニットカードを(?P<r>レストで)?登場させ' + V('る', '') + END,
        lambda m: (lambda f: f is not None and {'op': 'summonRested' if m.group('r') else 'summon', 'to': 'evtCard', 'f': f})(parse_desc(m.group('d')) if m.group('d') else {}))
    add(r'あなたの山札を上から1枚公開し、それがドロップしたカードと同じ称号なら登場させ、違うなら手札に加え' + V('る', '') + END, lambda m: {'op': 'revealTop', 'f': {'sameTitleEvt': 1}, 'yes': 'field', 'no': 'hand'})
    add(r'あなたのライフの先頭を見' + V('る', '') + END, lambda m: {'op': 'peekLife'})
    add(r'それをドロップしこれをライフの先頭に置' + V('く', 'き', 'い') + MAY + END, lambda m: [{'op': 'confirm', 'text': '라이프 맨 앞을 드롭하고 이 카드를 놓을까요?', 'alt': 1, 'no': [{'op': 'stop'}]}, {'op': 'lifeDrop', 'n': 1}, {'op': 'life', 'to': 'card'}])
    add(r'⁅怪異(?P<a>(?:⁅[^⁆]+⁆)+)⁆(?:\([^)]*\))?(?P<x>[^。]+)' + END,
        lambda m: (lambda r: r is not None and {'op': 'if', 'c': [{'droppedAttr': re.findall(r'⁅([^⁆]+)⁆', m.group('a'))}], 'then': r})(parse_effects(re.sub(r'^さらに', '', m.group('x')))))
    add(r'あなたのフィールドの、「(?P<nm>[^」]+)」かこのユニットをドロップ' + V('する', 'し') + END,
        lambda m: [{'op': 'tgt', 'f': {'side': 'own', 'type': 'unit', 'or': [{'nameEq': m.group('nm')}, {'selfOnly': 1}]}, 'n': 1, 'upto': 0}, {'op': 'drop', 'to': 'T'}])
    add(r'それら(?:全て)?を手札に戻' + V('す', 'し') + END, lambda m: {'op': 'milledToHand'})
    add(r'あなたのエナジーゾーンの、?総コストが対象の総コスト以下のユニットカードを(?P<n>\d+)枚(?P<up>まで)?登場させ' + V('る', '') + END,
        lambda m: {'op': 'pick', 'from': 'energy', 'to': 'field', 'f': {'type': 'unit', 'costLE_T': 1}, 'n': int(m.group('n')), 'upto': 1 if m.group('up') else 0})
    add(r'(?:そのターン中、)?(?:あなたは)?次の相手(?:の)?ターン中、そのユニットに【(?P<k>[^】]+)】を与え' + V('る', '') + END,
        lambda m: m.group('k') in KWMAP and {'op': 'kw', 'kw': KWMAP[m.group('k')], 'to': 'summoned', 'dur': 'duringOpp'})
    add(r'(?:次の相手(?:の)?ターン中、)?相手は追加で手札を(?P<n>\d+)枚ドロップしない限りアタックができない' + END,
        lambda m: {'op': 'restrict', 'r': {'kind': 'attackTax', 'n': int(m.group('n')), 'who': 'opp', 'dur': 'nextOppOnly'}})
    add(r'相手は自身のユニットで最もパワーの高いユニットから1枚選ぶ。あなたは自身のユニットで最もパワーの低いユニットから1枚選ぶ。各プレイヤーの選ばれなかったユニット全てを手札に戻' + V('す', 'し') + END,
        lambda m: [{'op': 'asOpp', 'do': [{'op': 'tgt', 'f': {'side': 'own', 'type': 'unit', 'powMax': 1}, 'n': 1, 'upto': 0}, {'op': 'markKeep'}, {'op': 'bounceUnkept'}]},
                   {'op': 'tgt', 'f': {'side': 'own', 'type': 'unit', 'powMin': 1}, 'n': 1, 'upto': 0}, {'op': 'markKeep'}])
    add(r'相手のテリトリーを閉じ' + V('る', '') + END, lambda m: {'op': 'closeTerr', 'who': 'opp'})
    add(r'(?:そのターン中、)?対象はブロックができず、パワーを(?P<n>\d+)になるよう増減させ' + V('る', '') + END, lambda m: [{'op': 'kw', 'kw': 'noBlock', 'to': 'T'}, {'op': 'powSet', 'n': int(m.group('n')), 'to': 'T'}])
    add(r'あなたの山札をシャッフルし、それらを全てライフの先頭に置' + V('く', 'き') + END, lambda m: {'op': 'deckAllToLife'})
    add(r'あなたの山札を上から(?P<n>\d+)枚見て、対象とコスト差が(?P<d>\d+)のユニットカードを(?P<k>\d+)枚まで登場させ、山札をシャッフル' + V('する', 'し') + END,
        lambda m: {'op': 'look', 'n': int(m.group('n')), 'f': {'type': 'unit', 'costDiffT': int(m.group('d'))}, 'k': int(m.group('k')), 'to': 'field', 'rest': 'shuffle'})
    add(r'次の相手のターン中にそのユニットがドロップした時、(?P<x>[^。]+)' + END,
        lambda m: (lambda r: r is not None and {'op': 'watchU', 'on': 'leave', 'to': 'summoned', 'dur': 'duringOpp', 'do': r})(parse_effects(m.group('x'))))
    add(r'(?:そのターン中、)?そのユニットがバトルに勝利した時、(?P<x>[^。]+)' + END,
        lambda m: (lambda r: r is not None and {'op': 'watchU', 'on': 'win', 'to': 'summoned', 'do': r})(parse_effects(m.group('x').replace('そのユニット', 'このユニット'))))
    add(r'相手の、?エースと⁅B⁆のユニット全てを手札に戻し、次の相手のターン中、エースと⁅B⁆のユニットはレストで登場す' + V('る', '') + END,
        lambda m: [{'op': 'bounce', 'to': {'all': {'side': 'opp', 'type': 'unit', 'or': [{'ace': 1}, {'icon': 'buster'}]}}}, {'op': 'restrict', 'r': {'kind': 'enterRested', 'f': {'or': [{'ace': 1}, {'icon': 'buster'}]}, 'who': 'opp', 'dur': 'nextOppOnly'}}])
    add(r'あなたのドロップゾーンの(?P<l>(?:【[^】]+】、?)+)を望む枚数、このユニットに重ねて着せ' + V('る', '') + END,
        lambda m: [{'op': 'tgt', 'zone': 'drop', 'f': {'or': [{'name': x} for x in re.findall(r'【([^】]+)】', m.group('l'))]}, 'n': 99, 'upto': 1}, {'op': 'attachT', 'to': 'self'}])
    add(r'このユニットとそれら全てをリムーブ' + V('する', 'し') + END, lambda m: {'op': 'remove', 'to': 'self'})
    add(r'あなたのドロップゾーンの共通の色を持たないカードを(?P<n>\d+)枚対象とし、その中から1枚をフィールドに伏せ、残りを山札の下に望む順で置' + V('く', 'き') + END,
        lambda m: [{'op': 'tgt', 'zone': 'drop', 'f': {}, 'n': int(m.group('n')), 'upto': 0, 'distinct': 'color'}, {'op': 'tSplit', 'first': 'set', 'rest': 'bottom'}])
    add(r'あなたのドロップゾーンの、互いに同じカード名の(?P<d>[^、。]*?)を(?P<n>\d+)枚対象とし、対象を手札に戻' + V('す', 'し') + END,
        lambda m: (lambda f: f is not None and [{'op': 'tgt', 'zone': 'drop', 'f': f, 'n': int(m.group('n')), 'upto': 0, 'same': 'name'}, {'op': 'bounce', 'to': 'T'}])(_zdesc(m.group('d'))))
    add(r'あなたの伏せたカードを1枚まで対象とし、相手はそのカードがユニットカードかコマンドカードかを予想し、あなたは対象を公開' + V('する', 'し') + END,
        lambda m: [{'op': 'tgt', 'zone': 'set', 'f': {}, 'n': 1, 'upto': 1}, {'op': 'choose', 'who': 'opp', 'opts': [[{'op': 'setCtx', 'k': 'guess', 'v': 'unit'}], [{'op': 'setCtx', 'k': 'guess', 'v': 'command'}]], 'labels': ['유닛 카드라고 예상', '커맨드 카드라고 예상'], 'text': '상대가 엎어 둔 카드의 종류를 예상하세요'}, {'op': 'revealT'}])
    add(r'あなたの山札を上から、あなたのエナジーの色の数だけ見て、それらを全てフィールドに伏せ' + V('る', '') + END,
        lambda m: {'op': 'look', 'n': 1, 'per': {'zone': 'colors', 'side': 'own', 'k': 1}, 'f': {}, 'k': 99, 'to': 'set', 'rest': 'top'})
    add(r'次のあなたのターンの開始時、あなたの伏せたカード全てをドロップさせ' + V('る', '') + END, lambda m: {'op': 'delay', 'at': 'myStart', 'do': [{'op': 'dropSetAll'}]})
    add(r'(?:さらに)?対象はリムーブしたカードの能力を全て得' + V('る', '') + END, lambda m: {'op': 'copyAbil', 'from': 'milled', 'to': 'T'})
    add(r'(?:そのターン中、)?このユニットは(?:対象の)?(?P<p>パワーと)?能力を全て得(?:て|る)' + END, lambda m: ([{'op': 'powByT', 'to': 'self'}] if m.group('p') else []) + [{'op': 'copyAbil', 'from': 'T', 'to': 'self'}])
    add(r'(?:そのターン中、)?このユニットは対象のパワーと能力を全て得' + V('る', '') + END, lambda m: [{'op': 'powByT', 'to': 'self'}, {'op': 'copyAbil', 'from': 'T', 'to': 'self'}])
    add(r'(?:そのターン中、)?このユニットは対象が持つ【(?P<k>[^】]+)】を全て得' + V('る', '') + END, lambda m: {'op': 'copyAbil', 'from': 'T', 'to': 'self', 'kwOnly': m.group('k')})
    add(r'(?:そのターン中、)?このユニットはそのエースカードの【(?P<k>[^】]+)】を全て得' + V('る', '') + END, lambda m: {'op': 'copyAbil', 'from': 'milled', 'to': 'self', 'kwOnly': m.group('k')})
    add(r'称号を無視して発動でき' + V('る', '') + END, lambda m: {'op': 'noop'})
    add(r'ユニット全てとドロップしたこのカードをリムーブ' + V('する', 'し') + END, lambda m: [{'op': 'remove', 'to': {'all': {'type': 'unit'}}}, {'op': 'remove', 'to': 'card'}])
    add(r'あなたのドロップゾーンの(?P<a>[^、。]+?)か、相手のドロップゾーンの(?P<b>[^、。]+?)を合計(?P<n>\d+)枚(?P<up>まで)?対象とし、対象をリムーブ' + V('する', 'し') + END,
        lambda m: (lambda fa, fb: fa is not None and fb is not None and [{'op': 'tgt', 'zone': 'drop', 'f': {'orSide': [dict(fa, side='own'), dict(fb, side='opp')]}, 'n': int(m.group('n')), 'upto': 1 if m.group('up') else 0}, {'op': 'remove', 'to': 'T'}])(_zdesc(m.group('a')), _zdesc(m.group('b'))))
    add(r'あなたのテリトリーゾーンの「(?P<nm>[^」]+)」を1枚、ユニット面で登場させ' + V('る', '') + END, lambda m: {'op': 'summonFromTerr', 'name': m.group('nm')})
    add(r'(?:そのターン中、)?ヒットを(?P<n>[+-]\d+)' + END, lambda m: {'op': 'hit', 'n': int(m.group('n')), 'to': '$prev'})
    add(r'次のエンドフェイズ開始時、そのユニットをドロップさせ' + V('る', '') + END, lambda m: {'op': 'delay', 'at': 'endStart', 'do': [{'op': 'drop', 'to': 'summoned'}]})
    add(r'このユニットが持っていたクラスカード(?P<k>\d+)枚につき、(?P<n>\d+)枚引' + V('く', 'き') + END, lambda m: {'op': 'draw', 'n': int(m.group('n')), 'per': {'cnt': 'evtClass', 'k': int(m.group('k'))}})
    add(r'ユニットを1枚対象とし、対象のヒット(?P<k>\d+)につき、相手は自身のドロップゾーンを(?P<n>\d+)枚リムーブ' + V('する', 'し') + END,
        lambda m: [{'op': 'tgt', 'f': {'type': 'unit'}, 'n': 1, 'upto': 0}, {'op': 'oppDropRemove', 'n': int(m.group('n')), 'per': {'tHit': 1}}])
    add(r'相手のユニット全てに、このユニットのパワーと同じダメージを与え' + V('る', '') + END, lambda m: {'op': 'dmgPow', 'from': 'self', 'to': {'all': OPPU}})
    add(r'次の相手ターン中、相手はコスト(?P<n>\d+)のカードをプレイできない' + END, lambda m: {'op': 'restrict', 'r': {'kind': 'noPlayCostEq', 'n': int(m.group('n')), 'who': 'opp', 'dur': 'nextOppOnly'}})
    add(r'ドロップした際、対象が持つ能力は全て発動しない' + END, lambda m: {'op': '_attach', 'silent': 1})
    add(r'相手は自身のライフを前から(?P<n>\d+)枚公開し、その中の(?P<d>[^、。]+?)を(?P<k>\d+)枚ドロップし、残りを望む順でライフの先頭に置' + V('く', 'き') + END,
        lambda m: (lambda f: f is not None and {'op': 'asOpp', 'do': [{'op': 'lifeLookDrop', 'n': int(m.group('n')), 'f': f, 'k': int(m.group('k'))}]})(_zdesc(m.group('d'))))
    add(r'あなたの、フィールドの(?P<a>[^、。]+?)(?P<n>\d+)枚と、手札かフィールドの(?P<b>[^、。]+?)(?P<k>\d+)枚をそれぞれドロップ' + V('する', 'し') + MAY + END,
        lambda m: (lambda fa, fb: fa is not None and fb is not None and [{'op': 'confirm', 'text': '이 효과를 쓸까요?', 'alt': 1, 'no': [{'op': 'stop'}]},
            {'op': 'tgt', 'f': dict(fa, side='own', type='unit'), 'n': 1, 'upto': 0}, {'op': 'drop', 'to': 'T'},
            {'op': 'choose', 'opts': [[{'op': 'pick', 'from': 'hand', 'to': 'drop', 'f': fb, 'n': 1, 'upto': 0}], [{'op': 'tgt', 'f': dict(fb, side='own', type='unit'), 'n': 1, 'upto': 0}, {'op': 'drop', 'to': 'T'}]], 'labels': ['패에서 드롭', '필드에서 드롭']}])(_zdesc(m.group('a')), _zdesc(m.group('b'))))
    add(r'対象とこのユニットを(?P<st>スタンドで|レストで)?入れ替え' + V('る', '') + MAY + END, lambda m: {'op': 'swapT', **({'stand': 1} if m.group('st') == 'スタンドで' else {'rested': 1} if m.group('st') else {})})
    add(r'あなたの(?P<z>エナジーゾーンの)?(?P<d>[^、。]+?)(?:のエナジー|ユニットカード)(?P<n>\d+)枚をこのユニットと(?P<st>スタンドで|レストで)?入れ替え' + V('る', '') + END,
        lambda m: (lambda f: f is not None and [{'op': 'tgt', 'zone': 'energy', 'f': dict(f, **({'type': 'unit'} if 'ユニットカード' in m.group(0) else {})), 'n': int(m.group('n')), 'upto': 0}, {'op': 'swapT', **({'stand': 1} if m.group('st') == 'スタンドで' else {})}])(parse_desc(m.group('d')) or parse_desc(m.group('d') + 'の')))
    add(r'(?:あなたは)?山札をシャッフルし' + V('', 'て') + END, lambda m: {'op': 'shuffle'})
    add(r'それが(?P<a>[^、。]+?)ならドロップゾーンから登場させ、(?:それが)?(?P<b>[^、。]+?)なら、?コストを払わずに?プレイ' + V('する', 'し') + MAY + END,
        lambda m: (lambda fa, fb: fa is not None and fb is not None and [{'op': 'if', 'c': [{'milledF': fa}], 'then': [{'op': 'summonMilled'}]}, {'op': 'if', 'c': [{'milledF': fb}], 'then': [{'op': 'playMilled', **({'may': 1} if m.group('may') else {})}]}])(_cdesc(m.group('a')), _cdesc(m.group('b'))))
    add(r'相手は(?P<n>\d+)枚引き、自身の手札を全て公開' + V('する', 'し') + END, lambda m: [{'op': 'draw', 'n': int(m.group('n')), 'who': 'opp'}, {'op': 'revealOppHand'}])
    add(r'対象はこのユニットがフィールドにいる間、アタックされず、他の効果の対象にならず、【デコイ】を失い、スタンドフェイズにスタンドしない' + END,
        lambda m: [{'op': 'kw', 'kw': k, 'to': 'T', 'dur': 'whileSrc'} for k in ('noBeAttacked', 'fxImmune', 'loseDecoy', 'noStand')])
    add(r'対象は次の相手のターン中、アタックされず、他の効果の対象にならず、【デコイ】を失' + V('う', 'い') + END,
        lambda m: [{'op': 'kw', 'kw': k, 'to': 'T', 'dur': 'duringOpp'} for k in ('noBeAttacked', 'fxImmune', 'loseDecoy')])
    add(r'エナジーのこのカードを登場させ' + V('る', '') + MAY + END, lambda m: {'op': 'summon', 'to': 'card'})
    add(r'次のエンドフェイズ開始時、(?:登場させたこのユニット|このユニット)をエナジーゾーンに置' + V('く', 'き') + END, lambda m: {'op': 'delay', 'at': 'endStart', 'do': [{'op': 'energy', 'to': 'self'}]})
    add(r'次のエンドフェイズ開始時、それらをエナジーゾーンに置' + V('く', 'き') + END, lambda m: {'op': 'delay', 'at': 'endStart', 'do': [{'op': 'energy', 'to': 'summoned'}]})
    add(r'あなたの山札を上から(?P<n>\d+)枚公開してよい。その中の(?P<d>.+?)を全てエナジーゾーンに置き、残りをドロップ' + V('する', 'し') + END,
        lambda m: (lambda fs: fs and [{'op': 'confirm', 'text': '덱 위를 공개할까요?', 'alt': 1, 'no': [{'op': 'stop'}]}, {'op': 'look', 'n': int(m.group('n')), 'f': {'or': fs}, 'k': 99, 'to': 'energy', 'rest': 'drop', 'auto': 1}])(_each_filters(m.group('d'))))
    add(r'相手は自身のユニットで最もパワーの高いユニットから1枚をドロップ' + V('する', 'し') + END,
        lambda m: {'op': 'asOpp', 'do': [{'op': 'tgt', 'f': {'side': 'own', 'type': 'unit', 'powMax': 1}, 'n': 1, 'upto': 0}, {'op': 'drop', 'to': 'T'}]})
    add(r'(?:そのターン中、)?このユニットのパワーとヒットを対象のパワーとヒット分だけそれぞれ増加させ' + V('る', '') + END, lambda m: [{'op': 'powByT', 'to': 'self'}, {'op': 'hitByT', 'to': 'self'}])
    add(r'あなたの裏のエナジー全てを表にし、表にした(?P<k>\d+)枚につき、(?P<x>[^。]+)' + END,
        lambda m: (lambda r: r is not None and [{'op': 'flipAll'}] + [dict(st, per={'milled': 1, 'k': int(m.group('k'))}) if st.get('op') not in ('tgt', 'if') else st for st in r])(parse_effects(m.group('x'))))
    add(r'(?:そのターン中、)?対象がドロップする際、代わりにエナジーゾーンに置' + V('く', 'き') + END, lambda m: {'op': 'toEnergyOnDrop', 'to': 'T'})
    add(r'あなたの手札かエナジーゾーンから、?(?P<d>[^、。]+?)を(?P<n>\d+)枚(?P<up>まで)?(?P<r>レストで)?登場させ' + V('る', '') + MAY + END,
        lambda m: (lambda f: f is not None and {'op': 'pick', 'from': 'handOrEnergy', 'to': 'field', 'f': f, 'n': int(m.group('n')), 'upto': 1 if (m.group('up') or m.group('may')) else 0, **({'rested': 1} if m.group('r') else {})})(_zdesc(m.group('d'))))
    add(r'あなたの手札の、?対象よりコストが(?P<a>\d+)または(?P<b>\d+)高いユニットカード1枚と、対象をスタンドで入れ替え' + V('る', '') + MAY + END,
        lambda m: [{'op': 'pick', 'from': 'hand', 'to': 'field', 'f': {'type': 'unit', 'costTplus': [int(m.group('a')), int(m.group('b'))]}, 'n': 1, 'upto': 1}, {'op': 'if', 'c': [{'did': 1}], 'then': [{'op': 'bounce', 'to': 'T'}]}])
    add(r'あなたの(?P<d>[^、。]+?)のエナジーを1枚、?コストを払わずに?プレイ' + V('する', 'し') + MAY + END,
        lambda m: (lambda f: f is not None and {'op': 'playFree', 'from': 'energy', 'f': f, 'may': 1})(parse_desc(m.group('d')) or _zdesc(m.group('d'))))
    add(r'このカードをあなたのユニット1枚につけ' + V('る', '') + MAY + END, lambda m: [{'op': 'tgt', 'f': {'side': 'own', 'type': 'unit'}, 'n': 1, 'upto': 1}, {'op': 'dressTo', 'to': 'T'}])
    add(r'(?:相手のユニットの枚数があなたのユニット以上なら、)?手札に戻す代わりに(?P<r>レストで)?登場させてよい' + END, lambda m: {'op': '$altSummon', **({'rested': 1} if m.group('r') else {})})
    add(r'代わりに(?P<r>レストで)?登場させてよい' + END, lambda m: {'op': '$altSummon', **({'rested': 1} if m.group('r') else {})})
    add(r'\+(?P<a>\d+)の代わりに\+(?P<b>\d+)' + END, lambda m: {'op': '$altN', 'a': int(m.group('a')), 'b': int(m.group('b'))})
    add(r'(?:山札を上から)?(?P<a>\d+)枚見る代わりに(?P<b>\d+)枚見る' + END, lambda m: {'op': '$altN', 'a': int(m.group('a')), 'b': int(m.group('b'))})
    add(r'対象を望む順でプレイ' + V('する', 'し') + END, lambda m: {'op': 'playFreeT'})
    add(r'この効果でドロップした相手のユニット(?P<k>\d+)枚につき、相手に(?P<n>\d+)ダメージ' + END, lambda m: {'op': 'lifeDmg', 'n': int(m.group('n')), 'who': 'opp', 'per': {'cnt': 'droppedOpp', 'k': int(m.group('k'))}})
    add(r'あなたのエナジーゾーンにない色のカードを(?P<n>\d+)枚、あなたのドロップゾーンからエナジーゾーンに置' + V('く', 'き', 'い') + MAY + END,
        lambda m: {'op': 'pick', 'from': 'drop', 'to': 'energy', 'f': {'colorNotInEnergy': 1}, 'n': int(m.group('n')), 'upto': 1})
    add(r'(?:そのターン中、)?あなたの(?P<d>[^、。]+?)全てのヒットは減少しない' + END,
        lambda m: (lambda f: f is not None and {'op': 'kw', 'kw': 'noHitDown', 'to': {'all': dict(f, side='own', type='unit')}})(_zdesc(m.group('d'))))
    add(r'(?:そのターン中、)?あなたの、ショットアイコンでないカードがライフからダメージでドロップする際、代わりに手札に戻' + V('す', 'し') + END, lambda m: {'op': 'turnFlag', 'flag': 'lifeToHandNonShot'})
    add(r'あなたの、(?P<a>[^、。]+?)のユニット(?P<n>\d+)枚と(?P<b>[^、。]+?)のエナジーを(?P<k>\d+)枚対象とし、対象を入れ替え' + V('る', '') + END,
        lambda m: (lambda fa, fb: fa is not None and fb is not None and [{'op': 'tgt', 'f': dict(fa, side='own', type='unit'), 'n': 1, 'upto': 0}, {'op': 'tgt', 'zone': 'energy', 'f': dict(fb, side='own'), 'n': 1, 'upto': 0, 'add': 1}, {'op': 'swapUnitEnergy'}])(parse_desc(m.group('a') + 'の') or parse_desc(m.group('a')), parse_desc(m.group('b') + 'の') or parse_desc(m.group('b'))))
    add(r'相手の、?コストがあなたの裏のエナジーの枚数以下のユニットを(?P<n>\d+)枚(?P<up>まで)?対象とし、(?:対象を)?ドロップさせ' + V('る', '') + END,
        lambda m: [{'op': 'tgt', 'f': {'side': 'opp', 'type': 'unit', 'costLEdownE': 1}, 'n': int(m.group('n')), 'upto': 1 if m.group('up') else 0}, {'op': 'drop', 'to': 'T'}])
    add(r'エナジーが(?P<n>\d+)枚以上の各プレイヤーは、自身のテリトリーを閉じ' + V('る', '') + END, lambda m: {'op': 'closeTerrIf', 'energyGE': int(m.group('n'))})
    add(r'エンドフェイズに移行し、(?:そのターン中、)?相手のユニット全てのヒットを0になるよう増減させ' + V('る', '') + END, lambda m: [{'op': 'hitSet', 'n': 0, 'to': {'all': OPPU}}, {'op': 'toEndPhase'}])
    add(r'対象とライフの先頭を入れ替え' + V('る', '') + END, lambda m: {'op': 'swapTLife'})
    add(r'相手はこの効果でエナジーゾーンに置いたユニットカードをレストで登場させ' + V('る', '') + END, lambda m: {'op': 'summonTcard', 'rested': 1})
    add(r'レストしているユニットを(?P<n>\d+)枚対象とし、互いのパワー分、ダメージを与えあ' + V('う', 'い') + END, lambda m: [{'op': 'tgt', 'f': {'type': 'unit', 'rested': 1}, 'n': int(m.group('n')), 'upto': 0}, {'op': 'mutualDmg'}])
    add(r'それがコスト(?P<n>\d+)以下のコマンドカードなら、手札に戻すかコストを払わずプレイ' + V('する', 'し') + END,
        lambda m: {'op': 'if', 'c': [{'milledF': {'costLE': int(m.group('n')), 'type': 'command'}}], 'then': [{'op': 'choose', 'opts': [[{'op': 'milledToHand'}], [{'op': 'playMilled'}]], 'labels': ['패로 되돌린다', '코스트 없이 플레이한다']}]})
    add(r'それを、?コストを払わずプレイ' + V('する', 'し') + MAY + END, lambda m: {'op': 'playMilled', **({'may': 1} if m.group('may') else {})})
    add(r'(?:そのターン中、)?他のユニット全ては「(?P<nm>[^」]+)」として扱う' + END, lambda m: {'op': 'kw', 'kw': 'nameAs:' + m.group('nm'), 'to': {'all': {'type': 'unit', 'notSelf': 1}}})
    add(r'(?:そのターン中、)?このユニットは【デコイ】を得て、カード名を「(?P<nm>[^」]+)」として扱う' + END, lambda m: [{'op': 'kw', 'kw': 'decoy', 'to': 'self'}, {'op': 'kw', 'kw': 'nameAs:' + m.group('nm'), 'to': 'self'}])
    add(r'その公開したカード(?P<k>\d+)枚につき、このユニットにクラスカードを(?P<n>\d+)枚生成してつけ' + V('る', '') + END, lambda m: {'op': 'genClass', 'n': int(m.group('n')), 'to': 'self', 'per': {'milled': 1, 'k': int(m.group('k'))}})
    add(r'あなたのクラスカードのエナジーを(?P<n>\d+)枚までそのユニットにつけ' + V('る', '') + END, lambda m: {'op': 'classEnergyAttach', 'n': int(m.group('n')), 'to': 'summoned'})
    add(r'相手のユニットから、パワーの合計がこのユニットのパワー以下になるように(?P<n>\d+)枚まで対象と' + V('し', 'する') + END,
        lambda m: {'op': 'tgt', 'f': {'side': 'opp', 'type': 'unit'}, 'n': int(m.group('n')), 'upto': 1, 'sumPowLEself': 1})
    add(r'対象は次の相手のスタンドフェイズにスタンドしない' + END, lambda m: {'op': 'noStandNext', 'to': 'T'})
    add(r'あなたのつけた契約書(?:の中)?から、?(?P<d>[^、。]+?)を(?P<n>\d+)枚(?P<up>まで)?対象と' + V('し', 'する') + END,
        lambda m: (lambda f: f is not None and {'op': 'tgt', 'zone': 'contract', 'f': f, 'n': int(m.group('n')), 'upto': 1 if m.group('up') else 0})(_zdesc(m.group('d'))))
    add(r'あなたのつけた契約書から(?P<d>[^、。]+?)を(?P<n>\d+)枚、?コストを払わずに?プレイ' + V('する', 'し') + MAY + END,
        lambda m: (lambda f: f is not None and {'op': 'playFree', 'from': 'contract', 'f': f, 'may': 1})(_zdesc(m.group('d'))))
    add(r'対象をレストでエナジーゾーンに置' + V('く', 'き') + END, lambda m: {'op': 'energy', 'to': 'T', 'rested': 1})
    add(r'相手は自身の手札を全て公開し、あなたはその中の(?P<d>[^、。]+?)を(?P<n>\d+)枚選び、そのカードと同じコストの相手の手札を全てドロップさせ' + V('る', '') + END,
        lambda m: (lambda f: f is not None and [{'op': 'revealOppHand'}, {'op': 'pick', 'from': 'hand', 'to': 'select', 'f': dict(f, side='opp'), 'n': int(m.group('n')), 'upto': 0}, {'op': 'dropOppHandCostEqMilled'}])(_zdesc(m.group('d'))))
    add(r'あなたの、山札を上から(?P<n>\d+)枚までドロップ' + V('し', 'する') + END, lambda m: {'op': 'choose', 'opts': [[{'op': 'mill', 'n': k}] for k in range(int(m.group('n')), -1, -1)], 'labels': [f'{k}장 드롭' for k in range(int(m.group('n')), -1, -1)]})
    add(r'(?:あなたの)?ドロップゾーンから、?(?P<d>[^、。]+?)を(?P<n>\d+)枚(?P<up>まで)?(?P<r>レストで)?登場させ' + V('る', '') + END,
        lambda m: (lambda f: f is not None and {'op': 'pick', 'from': 'drop', 'to': 'field', 'f': f, 'n': int(m.group('n')), 'upto': 1 if m.group('up') else 0, **({'rested': 1} if m.group('r') else {})})(_zdesc(m.group('d'))))
    add(r'相手は自身の手札を全て公開し、その中からコストが最も高いか最も低いカードを(?P<n>\d+)枚ドロップ' + V('する', 'し') + END,
        lambda m: [{'op': 'revealOppHand'}, {'op': 'asOpp', 'do': [{'op': 'pick', 'from': 'hand', 'to': 'drop', 'f': {'costExtreme': 1}, 'n': int(m.group('n')), 'upto': 0}]}])
    add(r'あなたの(?P<d>[^、。]+?)ユニット全ては、次の相手ターン中、レストしていてもブロックができ' + V('る', '') + END,
        lambda m: (lambda f: f is not None and {'op': 'kw', 'kw': 'blockRested', 'to': {'all': dict(f, side='own', type='unit')}, 'dur': 'duringOpp'})(parse_desc(m.group('d')) or _zdesc(m.group('d'))))
    add(r'その登場したユニットが持つアイコン能力の【スカウト(?P<n>\d+):登場時】は(?P<k>\d+)回発動' + V('する', 'し') + END, lambda m: [{'op': 'scout', 'n': int(m.group('n'))} for _ in range(int(m.group('k')) - 1)])
    add(r'(?:このターン|そのターン中、)あなたのカードがどこからでもドロップする際、代わりにそれをリムーブ' + V('する', 'し') + END, lambda m: {'op': 'turnFlag', 'flag': 'dropToRemove'})
    add(r'(?:そのターン中、)?あなたは、あなたのドロップゾーンのカードを、手札にあるかのように、エナジーに置いたりプレイでき' + V('る', '') + END, lambda m: {'op': 'turnFlag', 'flag': 'dropAsHand'})
    add(r'あなたのライフの枚数を数え' + V('る', '') + END, lambda m: {'op': 'saveLifeN'})
    add(r'あなたの山札とライフを全て見て、その中から(?P<d>[^、。]+?)を(?P<n>\d+)枚まで公開して手札に加え' + V('る', '') + END,
        lambda m: (lambda f: f is not None and {'op': 'pick', 'from': 'deckLife', 'to': 'hand', 'f': f, 'n': int(m.group('n')), 'upto': 1})(_zdesc(m.group('d'))))
    add(r'あなたのライフを全て山札に戻してシャッフルし、山札を上から、数えたライフの枚数と同じ枚数ライフに置' + V('く', 'き') + END, lambda m: {'op': 'lifeReset'})
    add(r'ユニットを1枚対象とし、エナジーゾーンに置' + V('く', 'き') + END, lambda m: [{'op': 'tgt', 'f': {'type': 'unit'}, 'n': 1, 'upto': 0}, {'op': 'energy', 'to': 'T'}])
    add(r'そのカードが置かれたエナジーゾーンから、コストがそのエナジーゾーンの枚数以下のユニットカードを1枚対象とし、そのエナジーのプレイヤーは対象を登場させ' + V('る', '') + END, lambda m: {'op': 'energyOwnerSummon'})
    add(r'相手ターンなら、そのターン中、そのユニットではアタックできない' + END, lambda m: {'op': 'if', 'c': [{'oppTurn': 1}], 'then': [{'op': 'kw', 'kw': 'noAttack', 'to': 'summoned'}]})
    add(r'このゲーム中、ずっとあなたの追加ターンを行' + V('う', 'い') + END, lambda m: {'op': 'extraForever'})
    add(r'その効果をこのカードの効果として使' + V('う', 'い', 'っ') + MAY + END, lambda m: {'op': 'useMilledEffect', 'may': 1})
    add(r'あなたの、フィールドとドロップゾーンのユニットカードをそれぞれ1枚対象と' + V('し', 'する') + END,
        lambda m: [{'op': 'tgt', 'f': {'side': 'own', 'type': 'unit'}, 'n': 1, 'upto': 0}, {'op': 'tgt', 'zone': 'drop', 'f': {'type': 'unit'}, 'n': 1, 'upto': 0, 'add': 1}])
    add(r'それらを入れ替え' + V('る', '') + MAY + END, lambda m: {'op': 'swapFieldDrop'})
    add(r'相手は自身のドロップゾーンの、?(?P<l>[^、。]+?)全てを山札に戻してシャッフル' + V('する', 'し') + END,
        lambda m: (lambda fs: fs and {'op': 'oppDropToDeck', 'f': {'or': fs}})(_each_filters(m.group('l')) or ([_zdesc(m.group('l'))] if _zdesc(m.group('l')) else None)))
    add(r'あなたの山札を上から1枚、表でテリトリーに契約書としてつけ' + V('る', '') + MAY + END, lambda m: {'op': 'contract', 'n': 1})
    # --- 25차 ---
    add(r'あなたのつけたログを全て見て、その中の(?P<d>[^、。]+?)を(?P<n>\d+)枚まで登場させ' + V('る', '') + END,
        lambda m: (lambda f: f is not None and {'op': 'pick', 'from': 'log', 'to': 'field', 'f': f, 'n': int(m.group('n')), 'upto': 1})(_zdesc(m.group('d'))))
    # --- 26차 ---
    add(r'あなたの手札(?:の|から)、?対象よりコストが(?P<a>\d+)または(?P<b>\d+)高いユニットカード1枚と、対象をスタンドで入れ替え' + V('る', '') + MAY + END,
        lambda m: [{'op': 'pick', 'from': 'hand', 'to': 'field', 'f': {'type': 'unit', 'costTplus': [int(m.group('a')), int(m.group('b'))]}, 'n': 1, 'upto': 1}, {'op': 'if', 'c': [{'did': 1}], 'then': [{'op': 'bounce', 'to': 'T'}]}])
    add(r'手札に戻すかコストを払わずプレイ' + V('する', 'し') + END, lambda m: {'op': 'choose', 'opts': [[{'op': 'milledToHand'}], [{'op': 'playMilled'}]], 'labels': ['패로 되돌린다', '코스트 없이 플레이한다']})
    add(r'(?:あなたの、?)?山札を上から(?P<n>\d+)枚までドロップ' + V('し', 'する') + END, lambda m: {'op': 'choose', 'opts': [[{'op': 'mill', 'n': k}] for k in range(int(m.group('n')), -1, -1)], 'labels': [f'{k}장 드롭' for k in range(int(m.group('n')), -1, -1)]})
    add(r'あなたの(?P<d>[^。]+?)エナジーを(?P<n>\d+)枚(?P<up>まで)?(?P<r>レストで)?登場させ' + V('る', '') + END,
        lambda m: (lambda f: f is not None and {'op': 'pick', 'from': 'energy', 'to': 'field', 'f': dict(f, type='unit'), 'n': int(m.group('n')), 'upto': 1 if m.group('up') else 0, **({'rested': 1} if m.group('r') else {})})(parse_desc(m.group('d')) or parse_desc(re.sub(r'の$', '', m.group('d')) + 'の')))
    add(r'あなたの(?P<d>[^、。]+?)エナジー(?P<n>\d+)枚とこのカードを入れ替え' + V('る', '') + MAY + END,
        lambda m: (lambda f: f is not None and [{'op': 'tgt', 'zone': 'energy', 'f': dict(f, side='own'), 'n': 1, 'upto': 1}, {'op': 'swapT'}])(parse_desc(m.group('d')) or parse_desc(re.sub(r'の$', '', m.group('d')) + 'の')))
    add(r'相手は自身のユニットで最もパワーの高いユニットから1枚選' + V('ぶ', 'び') + END,
        lambda m: {'op': 'asOpp', 'do': [{'op': 'tgt', 'f': {'side': 'own', 'type': 'unit', 'powMax': 1}, 'n': 1, 'upto': 0}, {'op': 'markKeep'}, {'op': 'bounceUnkept'}]})
    add(r'あなたは自身のユニットで最もパワーの低いユニットから1枚選' + V('ぶ', 'び') + END, lambda m: [{'op': 'tgt', 'f': {'side': 'own', 'type': 'unit', 'powMin': 1}, 'n': 1, 'upto': 0}, {'op': 'markKeep'}])
    add(r'あなたの(?:自身の)?ユニットで最もパワーの低いユニットから1枚選' + V('ぶ', 'び') + END, lambda m: [{'op': 'tgt', 'f': {'side': 'own', 'type': 'unit', 'powMin': 1}, 'n': 1, 'upto': 0}, {'op': 'markKeep'}])
    add(r'各プレイヤーの選ばれなかったユニット全てを手札に戻' + V('す', 'し') + END, lambda m: {'op': 'noop'})
    add(r'次の相手ターンまで、各プレイヤーは以下の規則を厳守す' + V('る', '') + r'(?:。・[^。]+。?)?' + END, lambda m: {'op': 'restrict', 'r': {'kind': 'secondUnitDrop', 'who': 'both', 'dur': 'nextOpp'}})
    add(r'(?:そのターン中、)?あなたのユニットが次に【スキル】を発動する際、そのスキルコスト全てを払わずに発動でき' + V('る', '') + END, lambda m: {'op': 'turnFlag', 'flag': 'freeSkill'})
    add(r'相手は自身のドロップゾーンを(?P<n>\d+)枚リムーブ' + V('する', 'し') + END, lambda m: {'op': 'oppDropRemove', 'n': int(m.group('n'))})
    add(r'あなたの山札を上から1枚、表で契約書としてこのテリトリーにつけ' + V('る', '') + MAY + END, lambda m: {'op': 'contract', 'n': 1, 'may': 1})
    add(r'あなたの山札を上から(?P<n>\d+)枚公開し、その中の(?P<d>.+?)を全てエナジーゾーンに置き、残りをドロップ' + V('する', 'し') + END,
        lambda m: (lambda fs: fs and {'op': 'look', 'n': int(m.group('n')), 'f': {'or': fs}, 'k': 99, 'to': 'energy', 'rest': 'drop'})(_each_filters(m.group('d'))))
    add(r'(?:そのターン1回だけ、)?あなたはエナジーを手札にあるかのように【ブライト】でドロップするカードに選べ' + V('る', '') + END, lambda m: {'op': 'turnFlag', 'flag': 'brightEnergy'})
    add(r'あなたの(?P<z>手札|ドロップゾーン|エナジーゾーン)の(?P<d>[^、。]+?)を(?P<n>\d+)枚(?:まで)?コストを払わずに?プレイ' + V('する', 'し') + MAY + END,
        lambda m: (lambda f: f is not None and {'op': 'playFree', 'from': {'手札': 'hand', 'ドロップゾーン': 'drop', 'エナジーゾーン': 'energy'}[m.group('z')], 'f': f, 'may': 1})(_zdesc(m.group('d'))))
    # --- 27차 ---
    add(r'(?:そのターン中、)?対象は『(?P<q>[^』]+)』を得(?:て、パワーを(?P<n>[+-]\d+)|る)' + END,
        lambda m: (lambda ab: ab and [{'op': 'grantT', 'ab': ab, 'to': 'T'}] + ([{'op': 'pow', 'n': int(m.group('n')), 'to': 'T'}] if m.group('n') else []))(parse_body(m.group('q'), {'type': 'unit'}, None)))
    add(r'(?:そのターン中、)?このユニットは『⁅永続⁆このユニットの与えたダメージで⁅バスターアイコン⁆が出た際、追加ダメージの代わりにあなたはゲームに勝利する。?』を得' + V('る', '') + END, lambda m: {'op': 'kw', 'kw': 'busterWin', 'to': 'self'})
    add(r'あなたは手札を望む枚数ドロップ' + V('する', 'し') + r'てよい' + END, lambda m: {'op': 'pick', 'from': 'hand', 'to': 'drop', 'f': {}, 'n': 99, 'upto': 1})
    add(r'(?:そのターン中、)?次に対象がアタックした時、(?P<x>[^。]+)' + END,
        lambda m: (lambda r: r is not None and {'op': 'watchU', 'on': 'attack', 'to': 'T', 'once': 1, 'do': r})(parse_effects(m.group('x'))))
    add(r'あなたの、?手札かドロップゾーンの(?P<d>[^、。]+?)を(?P<n>\d+)枚(?P<up>まで)?テリトリーゾーンに置' + V('く', 'き') + END,
        lambda m: (lambda f: f is not None and {'op': 'pick', 'from': 'handOrDrop', 'to': 'terrZone', 'f': f, 'n': int(m.group('n')), 'upto': 1 if m.group('up') else 0})(_zdesc(m.group('d'))))
    add(r'あなたのつけた契約書の中から(?P<d>[^、。]+?)を(?P<n>\d+)枚(?P<up>まで)?登場させ' + V('る', '') + END,
        lambda m: (lambda f: f is not None and {'op': 'pick', 'from': 'contract', 'to': 'field', 'f': f, 'n': int(m.group('n')), 'upto': 1 if m.group('up') else 0})(_zdesc(m.group('d'))))
    add(r'あなたのつけた契約書の中から(?P<d>[^、。]+?)を(?P<n>\d+)枚、?コストを払わずに?プレイ' + V('する', 'し') + MAY + END,
        lambda m: (lambda f: f is not None and {'op': 'playFree', 'from': 'contract', 'f': f, 'may': 1})(_zdesc(m.group('d'))))
    add(r'相手は公開したカードをドロップし、自身の山札を上から1枚ライフの先頭に置' + V('く', 'き') + END, lambda m: {'op': 'oppLifeDropTopReplace'})
    add(r'相手は自身のライフの先頭を公開' + V('し', 'する') + END, lambda m: {'op': 'revealLifeTop', 'who': 'opp'})
    add(r'自身のエナジーで最もコストの高いカードから1枚を手札に戻' + V('す', 'し') + END, lambda m: {'op': 'pick', 'from': 'energy', 'to': 'hand', 'f': {'costMaxEnergy': 1}, 'n': 1, 'upto': 0})
    add(r'あなたの山札を上から(?P<n>\d+)枚見て、その中の1枚を手札に加え、1枚をエナジーゾーンに置き、残りをリムーブ' + V('する', 'し') + END,
        lambda m: [{'op': 'look', 'n': int(m.group('n')), 'f': {}, 'k': 1, 'min1': 1, 'to': 'hand', 'rest': 'top'}, {'op': 'look', 'n': int(m.group('n')) - 1, 'f': {}, 'k': 1, 'min1': 1, 'to': 'energy', 'rest': 'remove'}])
    add(r'あなたの山札を上から(?P<n>\d+)枚見て、その中の1枚をライフの先頭に置き、残りをドロップ' + V('する', 'し') + END,
        lambda m: {'op': 'look', 'n': int(m.group('n')), 'f': {}, 'k': 1, 'min1': 1, 'to': 'life', 'rest': 'drop'})
    add(r'そのユニットをレストし、このユニットをエナジーゾーンに置' + V('く', 'き') + END, lambda m: [{'op': 'rest', 'to': 'evt'}, {'op': 'energy', 'to': 'self'}])
    add(r'(?:あなたの)?(?P<d>[^、。]+?)のエナジーを(?P<n>\d+)枚(?P<up>まで)?対象とし、対象をレストで登場させ' + V('る', '') + END,
        lambda m: (lambda f: f is not None and [{'op': 'tgt', 'zone': 'energy', 'f': dict(f, side='own'), 'n': int(m.group('n')), 'upto': 1 if m.group('up') else 0}, {'op': 'summonTcard', 'rested': 1}])(parse_desc(m.group('d')) or parse_desc(m.group('d') + 'の')))
    add(r'ドロップしたカードをエナジーゾーンに置' + V('く', 'き') + END, lambda m: {'op': 'energy', 'to': 'evtCard'})
    add(r'、?カード名を「(?P<nm>[^」]+)」として扱う' + END, lambda m: {'op': 'kw', 'kw': 'nameAs:' + m.group('nm'), 'to': '$prev'})
    add(r'レストする際、(?P<c>[^。]+?)なら、代わりに登場させ、(?:そのターン中、)?その登場させたユニットのパワーを(?P<n>[+-]\d+)' + END,
        lambda m: (lambda c: c is not None and {'op': '$altEvt', 'c': c, 'n': int(m.group('n'))})(parse_cond(m.group('c'))))
    add(r'(?:あなたの)?手札からこのカードを登場させ' + V('る', '') + END, lambda m: {'op': 'summon', 'to': 'card'})
    add(r'(?:そのターン中、)?このユニットは他の能力を全て失' + V('う', 'い') + END, lambda m: {'op': 'kw', 'kw': 'blank', 'to': 'self'})
    add(r'次のエンドフェイズ開始時、そのユニットをスタンド' + V('する', 'し') + END, lambda m: {'op': 'delay', 'at': 'endStart', 'do': [{'op': 'stand', 'to': 'evt'}]})
    add(r'対象のコスト(?P<k>\d+)につき、あなたのエナジーを(?P<n>\d+)枚スタンド' + V('する', 'し') + END, lambda m: {'op': 'standEnergy', 'n': int(m.group('n')), 'per': {'tCost': 1, 'k': int(m.group('k'))}})
    add(r'あなたの伏せたカードの中から、(?P<d>[^。]+?)を(?P<n>\d+)枚(?P<up>まで)?登場させ' + V('る', '') + END,
        lambda m: (lambda f: f is not None and {'op': 'pick', 'from': 'set', 'to': 'field', 'f': f, 'n': int(m.group('n')), 'upto': 1 if m.group('up') else 0})(_zdesc(m.group('d'))))
    add(r'あなたのユニットがアタックしたターンのエンドフェイズ開始時、(?P<x>[^。]+)' + END, lambda m: None)
    MV = {'手札に戻': 'bounce', '山札の下に置': 'deckBottom', '山札の上に置': 'deckTop', 'ライフの先頭に置': 'life', 'エナジーゾーンに置': 'energy', 'ドロップさせ': 'drop', 'リムーブ': 'remove'}
    LB = {'bounce': '패로 되돌림', 'deckBottom': '덱 맨 아래', 'deckTop': '덱 맨 위', 'life': '라이프 맨 앞', 'energy': '에너지 존', 'drop': '드롭', 'remove': '리무브'}
    def or_move(m):
        a, b = MV[m.group('a')], MV[m.group('b')]
        return {'op': 'choose', 'opts': [[{'op': a, 'to': 'T'}], [{'op': b, 'to': 'T'}]], 'labels': [LB[a], LB[b]]}
    alts = '|'.join(MV)
    add(r'対象を、?(?P<a>' + alts + r')(?:す|く|る|)か(?P<b>' + alts + r')' + V('す', 'く', 'る', 'する', '') + END, or_move)
    add(r'(?P<to>対象|このユニット)に(?P<src>このユニット|対象)のパワー(?:分の|と同じ)ダメージを与え' + V('る', '') + END,
        lambda m: {'op': 'dmgPow', 'to': subj(m.group('to')), 'from': subj(m.group('src'))})
    add(r'(?:あなたは)?(?P<n>\d+)枚引いて(?P<k>\d+)枚ドロップ' + V('する', 'し') + END, lambda m: [{'op': 'draw', 'n': int(m.group('n'))}, {'op': 'discard', 'n': int(m.group('k'))}])
    add(r'(?P<d>[^、。]*?)ユニットを望む枚数対象と' + V('し', 'する') + END,
        lambda m: (lambda f: f is not None and {'op': 'tgt', 'f': {**f, 'type': 'unit'}, 'n': 99, 'upto': 1})(parse_desc(m.group('d'))))
    add(r'(?P<d>[^、。]*?)ユニットを望む枚数対象とし、(?P<n>\d+)ダメージ' + END,
        lambda m: (lambda f: f is not None and [{'op': 'tgt', 'f': {**f, 'type': 'unit'}, 'n': 99, 'upto': 1}, {'op': 'dmg', 'n': int(m.group('n')), 'to': 'T'}])(parse_desc(m.group('d'))))
    add(r'レストで登場させ' + V('る', '') + END, lambda m: {'op': 'summonRested', 'to': 'T'})
    add(r'対象は互いのパワー分、ダメージを与えあう' + END, lambda m: {'op': 'fight'})
    add(r'(?P<n>[+-]\d+)' + END, lambda m: {'op': '$prevop', 'n': int(m.group('n')), 'to': '$prev'})
    # 라이프 맨 앞 보기 / 공개
    add(r'あなたのライフの先頭を見る' + END, lambda m: {'op': 'peekLife'})
    # 배틀 상대 중 조건에 맞으면 드롭
    add(r'(?P<d>[^、。]*?)バトル相手をドロップさせ' + V('る', '') + END,
        lambda m: (lambda f: f is not None and {'op': 'drop', 'to': 'vs', 'vf': f})(parse_desc(m.group('d'))))
    # 이 카드를 (드롭 존/에너지에서) 코스트 없이 플레이
    add(r'(?P<z>ドロップゾーン|エナジー|手札)のこのカードをコストを払わず(?:に)?プレイ' + V('する', 'し') + MAY + END,
        lambda m: {'op': 'playSelf', 'from': {'ドロップゾーン': 'drop', 'エナジー': 'energy', '手札': 'hand'}[m.group('z')], 'may': 1})
    add(r'あなたのライフの先頭をドロップ' + V('する', 'し') + MAY + END, lambda m: {'op': 'lifeDrop', 'n': 1, **({'may': 1} if m.group('may') else {})})
    add(r'相手は自身のユニットを(?P<n>\d+)枚ドロップさせ' + V('る', '') + END, lambda m: {'op': 'sacrifice', 'who': 'opp', 'n': int(m.group('n'))})
    add(r'(?:次のエンドフェイズ開始時、)?あなたのテリトリーを閉じ' + V('る', '') + END, lambda m: {'op': 'closeTerr'})
    for rx, op in [(r'スタンド' + V('する', 'し', 'させる', 'させ'), 'stand'), (r'レスト' + V('する', 'し', 'させる', 'させ'), 'rest')]:
        add(rx + END, lambda m, op=op: {'op': op, 'to': 'T'})
    # 서로 파워만큼 데미지
    add(r'あなたのユニット1枚と相手のユニット1枚を対象とし、それらは互いのパワー分、ダメージを与えあう' + END,
        lambda m: [{'op': 'tgt', 'f': {'side': 'own', 'type': 'unit'}, 'n': 1, 'upto': 0, 'save': 'A'}, {'op': 'tgt', 'f': {'side': 'opp', 'type': 'unit'}, 'n': 1, 'upto': 0, 'save': 'B'}, {'op': 'fight'}])
    add(r'(?:レストしている)?ユニットを2枚対象とし、(?:それらは)?互いのパワー分、ダメージを与えあう' + END,
        lambda m: [{'op': 'tgt', 'f': {'type': 'unit'}, 'n': 2, 'upto': 0}, {'op': 'fight'}])
    # 필드에 뒷면으로 두기 (かぐや様)
    add(r'(?:自分|あなた)の手札を(?P<n>\d+)枚(?P<upto>まで)?フィールドに伏せ' + V('る', '') + MAY + END, lambda m: {'op': 'setHand', 'n': int(m.group('n')), **({'may': 1} if m.group('upto') or m.group('may') else {})})
    add(r'このユニットを(?:裏にして)?フィールドに伏せ' + V('る', '') + MAY + END, lambda m: {'op': 'setSelf', **({'may': 1} if m.group('may') else {})})
    add(r'対象をフィールドに伏せ' + V('る', '') + END, lambda m: {'op': 'setT'})
    add(r'あなたの伏せたカードの中から、?' + DESC + r'(?:' + NOUN[:-1] + r'))?を(?P<n>\d+)枚(?P<upto>まで)?(?P<rest>レストで)?登場させ' + V('る', '') + END,
        lambda m: (lambda f: f is not None and {'op': 'pick', 'from': 'set', 'to': 'field', 'f': noun_filter(f, m.group('noun')), 'n': int(m.group('n')), 'upto': 1 if m.group('upto') else 0, **({'rested': 1} if m.group('rest') else {})})(parse_desc(m.group('d'))))
    add(r'あなたの伏せたカード(?P<n>\d+)枚をドロップ' + V('する', 'し') + MAY + END, lambda m: {'op': 'pick', 'from': 'set', 'to': 'drop', 'f': {}, 'n': int(m.group('n')), 'upto': 1, 'rec': 1})
    add(r'あなたの伏せたカード(?:を)?全てをドロップ' + V('する', 'し') + MAY + END, lambda m: {'op': 'setDropAll', **({'may': 1} if m.group('may') else {})})
    add(r'あなたの伏せたカードを全てドロップ' + V('する', 'し') + MAY + END, lambda m: {'op': 'setDropAll', **({'may': 1} if m.group('may') else {})})
    add(r'相手の伏せたカード全てを手札に戻' + V('す', 'し') + END, lambda m: {'op': 'setBounceOpp'})
    add(r'あなたの裏のエナジーを(?P<n>\d+)枚(?:まで)?表に' + V('する', 'し') + END, lambda m: {'op': 'unflipEnergy', 'n': int(m.group('n'))})
    def at_end(m):
        sub = parse_effects(m.group('x'))
        return sub and {'op': 'delay', 'at': 'attackEnd', 'do': sub}
    add(r'このアタック(?:の)?終了時、(?P<x>[^。]+)(?:。|$)', at_end)
    add(r'(?:そのターン中、)?あなたはダメージで(?:は)?敗北せず' + END, lambda m: {'op': 'turnFlag', 'flag': 'noLoseDmg'})
    add(r'(?:そのターン中、)?あなたはダメージで(?:は)?敗北しない' + END, lambda m: {'op': 'turnFlag', 'flag': 'noLoseDmg'})
    add(r'各プレイヤーは(?P<n>\d+)枚引(?:く|き|いて(?P<may>(?:も)?よい))' + END,
        lambda m: [{'op': 'draw', 'n': int(m.group('n')), **({'may': 1} if m.group('may') else {})}, {'op': 'draw', 'n': int(m.group('n')), 'who': 'opp', **({'may': 1} if m.group('may') else {})}])
    add(_DUR + r'(?P<to>[^、。]*?)のパワーを0になるよう(?:減少|増減)させ' + V('る', '') + END, lambda m: subj(m.group('to')) and {'op': 'powZero', 'to': subj(m.group('to'))})
    add(r'このターンあなたの手札上限は(?P<n>\d+)枚になる' + END, lambda m: {'op': 'turnFlag', 'flag': 'hand' + m.group('n')})
    # 클래스 카드 (Fate/Grand Order)
    add(r'(?:あなたは)?クラスカードを(?P<n>\d+)枚生成してエナジーゾーンに置' + V('く', 'き', 'い') + END, lambda m: {'op': 'genClass', 'n': int(m.group('n')), 'to': 'energy'})
    def gen_att(m):
        t = m.group('t')
        if t in ('このユニット', 'そのユニット', 'このテリトリー'):
            return {'op': 'genClass', 'n': int(m.group('n')), 'to': {'このユニット': 'self', 'そのユニット': 'T', 'このテリトリー': 'terr'}[t]}
        if 'エースか⁅バスターアイコン⁆' in t:
            return [{'op': 'tgt', 'f': {'side': 'own', 'type': 'unit', 'aceOrBuster': 1}, 'n': 1, 'upto': 0}, {'op': 'genClass', 'n': int(m.group('n')), 'to': 'T'}]
        f = parse_desc(re.sub(r'^あなたの、?', 'あなたの', t).replace('ユニット', '').replace('エース', '') or '')
        if f is None:
            return None
        if 'エース' in t and 'エースか' not in t:
            f['ace'] = 1
        f.setdefault('side', 'own')
        f['type'] = 'unit'
        return [{'op': 'tgt', 'f': f, 'n': 1, 'upto': 0}, {'op': 'genClass', 'n': int(m.group('n')), 'to': 'T'}]
    add(r'(?:あなたは)?(?P<t>このユニット|そのユニット|このテリトリー|エース|あなたの[^。]*?ユニット(?:1枚)?)にクラスカードを(?P<n>\d+)枚生成してつけ' + V('る', '') + END, gen_att)
    add(r'(?:あなたは)?クラスカードを(?P<n>\d+)枚生成して(?P<t>このユニット|そのユニット)につけ' + V('る', '') + END,
        lambda m: {'op': 'genClass', 'n': int(m.group('n')), 'to': 'self' if m.group('t') == 'このユニット' else 'T'})
    add(r'あなたのドロップゾーンのクラスカードを(?P<n>\d+)枚(?P<upto>まで)?エナジーゾーンに置' + V('く', 'き', 'い') + MAY + END,
        lambda m: {'op': 'classFromDrop', 'n': int(m.group('n')), 'to': 'energy', **({'may': 1} if m.group('may') else {})})
    add(r'あなたのドロップゾーンのクラスカードを1枚、あなたの(?P<d>[^、。]*?)ユニットにつけ(?:る|(?=てよい)|て)' + MAY + END,
        lambda m: (lambda f: f is not None and [{'op': 'tgt', 'f': {**f, 'side': 'own', 'type': 'unit'}, 'n': 1, 'upto': 1}, {'op': 'classFromDrop', 'n': 1, 'to': 'T'}])(parse_desc(m.group('d'))))
    # 「生成」 없이 「つける」여도 게임 밖에서 붙임 (FAQ 赤く染まる大平原)
    add(r'あなたの(?P<d>[^、。]*?)ユニット1枚にクラスカードを1枚つけ' + V('る', '') + END,
        lambda m: (lambda f: f is not None and [{'op': 'tgt', 'f': {**f, 'side': 'own', 'type': 'unit'}, 'n': 1, 'upto': 0}, {'op': 'genClass', 'n': 1, 'to': 'T'}])(parse_desc(m.group('d'))))
    add(r'このテリトリーにつけたクラスカードを(?P<n>\d+)枚ドロップ' + V('する', 'し') + MAY + END,
        lambda m: {'op': 'classTerrDrop', 'n': int(m.group('n')), **({'may': 1} if m.group('may') else {})})
    add(r'次の相手ターンまで、クラスカードであなたのユニットのパワーが増加する際、\+1000の代わりに\+3000される' + END, lambda m: {'op': 'classBoost'})
    add(_DUR + r'(?P<to>このユニット|対象)はヒット(?P<n>[+-]\d+)' + END, lambda m: {'op': 'hit', 'n': int(m.group('n')), 'to': subj(m.group('to'))})
    # 코스프레 관련
    add(_DUR + r'(?P<to>このユニット|そのユニット|対象)は【コスプレ(?P<n>\d+)】を得(?:る|て)(?:、(?P<mods>(?:パワー|ヒット)を[+-]\d+))?' + END,
        lambda m: [{'op': 'kw', 'kw': 'cos' + m.group('n'), 'to': subj(m.group('to'))}] + ([{'op': 'pow' if m.group('mods').startswith('パワー') else 'hit', 'n': int(re.search(r'[+-]\d+', m.group('mods')).group()), 'to': subj(m.group('to'))}] if m.group('mods') else []))
    add(r'(?:そのターン中、)?あなたのユニットの【コスプレ】は手札とエナジーから選べる' + END, lambda m: {'op': 'turnFlag', 'flag': 'cosEnergy'})
    add(r'このターンに【コスプレ】で登場するあなたのユニットはスタンドで登場する' + END, lambda m: {'op': 'turnFlag', 'flag': 'cosStand'})
    add(r'その【コスプレ】で登場するバスターアイコンはスタンドで登場する' + END, lambda m: {'op': 'turnFlag', 'flag': 'cosBusterStand'})
    add(r'このユニットは【コスプレ】' + V('する', 'し') + MAY + END, lambda m: {'op': 'cosplayNow', 'may': 1})
    # 붙이기
    add(r'このカードを(?:対象|そのユニット)につけ' + V('る', '') + END, lambda m: {'op': 'attachSelf'})
    add(r'このカードをあなたのユニット1枚につけ(?:る|て)' + MAY + END,
        lambda m: [{'op': 'tgt', 'f': {'side': 'own', 'type': 'unit'}, 'n': 1, 'upto': 0, **({'may': 1} if m.group('may') else {})}, {'op': 'attachSelf'}])
    add(r'(?:相手の)?ライフの先頭をドロップさせ' + V('る', '') + END, lambda m: {'op': 'lifeDrop', 'n': 1, 'who': 'opp'})
    # 지연: 다음 엔드 페이즈 시작 시
    def delay(m):
        sub = parse_effects(m.group('x'))
        return sub and {'op': 'delay', 'at': 'endStart', 'do': sub}
    add(r'次の(?:あなたの)?エンドフェイズ開始時、(?P<x>[^。]+)(?:。|$)', delay)
    add(r'相手は手札を全て公開' + V('する', 'し') + END, lambda m: {'op': 'reveal'})
    # 드로우
    add(r'(?:あなたは)?(?P<n>\d+)枚引' + V('く', 'き', 'いて') + MAY + END,
        lambda m: {'op': 'draw', 'n': int(m.group('n')), **({'may': 1} if m.group('may') else {})})
    add(r'相手は(?P<n>\d+)枚引' + V('く', 'き', 'い') + END, lambda m: {'op': 'draw', 'n': int(m.group('n')), 'who': 'opp'})
    # 스카웃
    add(r'(?:あなたは)?スカウト(?P<n>\d+)(?:する|し|を行う)?' + END, lambda m: {'op': 'scout', 'n': int(m.group('n'))})
    # 패 버리기
    add(r'(?:あなたは)?(?:あなたの)?手札(?:から|を)(?P<n>\d+)枚(?:選んで)?ドロップ' + V('する', 'し') + MAY + END,
        lambda m: {'op': 'discard', 'n': int(m.group('n')), **({'may': 1} if m.group('may') else {})})
    add(r'相手は(?:自身の)?手札を(?P<n>\d+)枚(?:選んで)?ドロップ' + V('する', 'し') + END,
        lambda m: {'op': 'discard', 'n': int(m.group('n')), 'who': 'opp'})
    # 덱 위에서 드롭
    add(r'(?:その後、)?あなたの山札(?:を|の)上から(?P<n>\d+)枚(?:を)?ドロップ' + V('する', 'し') + MAY + END,
        lambda m: {'op': 'mill', 'n': int(m.group('n')), **({'may': 1} if m.group('may') else {})})
    # 라이프 추가
    add(r'あなたの山札をシャッフル(?:して|し、)(?:山札を|その)?上から(?P<n>\d+)枚(?:を)?ライフ(?:ゾーン)?の先頭に置' + V('く', 'き', 'い') + END,
        lambda m: {'op': 'lifeTop', 'n': int(m.group('n')), 'shuffle': 1})
    add(r'あなたの山札(?:を|の)上から(?P<n>\d+)枚(?:を)?ライフ(?:ゾーン)?の先頭に置' + V('く', 'き', 'い') + END,
        lambda m: {'op': 'lifeTop', 'n': int(m.group('n'))})
    add(r'あなたの山札をシャッフル' + V('する', 'し') + END, lambda m: {'op': 'shuffle'})
    # 덱 위에서 에너지
    add(r'あなたの山札(?:を|の)上から(?P<n>\d+)枚(?:を)?エナジーゾーンに置' + V('く', 'き', 'い') + END,
        lambda m: {'op': 'deckEnergy', 'n': int(m.group('n'))})
    # 라이프 맨 앞 -> 에너지 / 패
    add(r'あなたのライフの先頭(?:の(?P<n>\d+)枚)?をエナジーゾーンに置' + V('く', 'き', 'い') + END,
        lambda m: {'op': 'lifeEnergy', 'n': int(m.group('n') or 1)})
    add(r'あなたのライフの先頭(?:の(?P<n>\d+)枚)?を手札に加え' + V('る', '') + END,
        lambda m: {'op': 'lifeHand', 'n': int(m.group('n') or 1)})
    # 에너지 스탠드
    add(r'あなたのエナジーを(?P<n>\d+)枚(?:まで)?スタンド' + V('する', 'し') + END,
        lambda m: {'op': 'energyStand', 'n': int(m.group('n'))})

    # 존에서 골라 패/필드로
    def pick(m):
        f = parse_desc(m.group('d') or '')
        if f is None:
            return None
        if m.group('noun') == 'バスターアイコン':
            f['icon'] = 'buster'
        elif m.group('noun'):
            noun_filter(f, m.group('noun'))
        dest = 'field' if '登場' in m.group('v') else 'life' if 'ライフ' in m.group('v') else 'energy' if 'エナジー' in m.group('v') else 'remove' if 'リムーブ' in m.group('v') else 'hand'
        zone = {'ドロップゾーン': 'drop', '手札': 'hand', 'エナジーゾーン': 'energy', 'エナジー': 'energy'}[m.group('zone')]
        if zone == dest:
            return None
        st = {'op': 'pick', 'from': zone, 'to': dest, 'f': f, 'n': int(m.group('n')), 'upto': 1 if m.group('upto') else 0}
        if m.group('rest'):
            st['rested'] = 1
        if m.group('may'):
            st['upto'] = 1
        return st
    add(r'(?:あなたの)?(?P<zone>ドロップゾーン|手札|エナジーゾーン|エナジー)(?:の|から)(?P<d>(?:[^。を]|を持つ|を含む)*?)(?:' + NOUN[:-1] + r'|バスターアイコン))?を(?P<n>\d+)枚(?P<upto>まで)?(?:選んで)?(?:公開して)?(?P<rest>レストで)?(?P<v>手札に加え(?:る|)|登場させ(?:る|)|ライフの先頭に置(?:く|き|い)|エナジーゾーンに置(?:く|き|い)|リムーブ(?:する|し))' + MAY + END, pick)

    # 덱 위 N장 보고 고르기
    def look(m):
        f = parse_desc(m.group('d') or '')
        if f is None:
            return None
        if m.group('noun'):
            noun_filter(f, m.group('noun'))
        dest = 'field' if '登場' in m.group('v') else 'energy' if 'エナジー' in m.group('v') else 'hand'
        r = m.group('r') or m.group('r2') or ''
        rest = 'drop' if 'ドロップ' in r else 'top' if '上' in r else 'shuffle' if 'シャッフル' in r else 'energy' if 'エナジー' in r else 'bottom'
        k = 99 if m.group('all') else int(m.group('k'))
        return {'op': 'look', 'n': int(m.group('n')), 'f': f, 'k': k, 'to': dest, 'rest': rest, **({'rested': 1} if m.group('rst') else {})}
    add(r'あなたの山札(?:を|の)上から(?P<n>\d+)枚(?:見て|公開し)、(?:その中(?:から|の)、?)?(?P<d>(?:[^。を]|を持つ|を含む)*?)(?:' + NOUN + r')?(?:を(?P<k>\d+)枚まで|(?P<all>全て)を)(?:公開して)?(?P<rst>レストで)?(?P<v>手札に加え|登場させ|エナジーゾーンに置き)、(?:残りを(?P<r>ドロップ|望む順で山札の下に置|山札の下に置|望む順で山札の上に置|山札の上に置|エナジーゾーンに置)' + V('する', 'く', 'し', 'き') + r'|(?P<r2>山札をシャッフル)' + V('する', 'し') + r')' + END,
        lambda m: look(m) if m.group('r') or True else None)
    return P


EFF = eff_patterns()

# ---------- 조건 ----------
def _histc(m, base):
    """기록 조건: 「このターン(このゲーム中)、あなた/相手の~が…」"""
    d = m.group('d')
    d = re.sub(r'^(?:⁅([^⁆]+)⁆)$', r'⁅\1⁆', d)
    f = _zdesc(d) if d else {}
    if f is None and d:
        f = _zdesc(d + 'カード')
    if f is None:
        return None
    if base['k'] == 'mv' and base.get('to') == 'field' and 'type' not in f:
        f = dict(f, type='unit')
    return {'hist': dict(base, scope='turn' if m.group('sc').startswith('このターン') else 'game', side='own' if m.group('w') == 'あなた' else 'opp', **({'f': f} if f else {}))}


def _pair(a, b):
    """「「日向」を含むカードと「ユイ」を含むカード」 / 「青と赤のエースカード」 -> 두 묘사"""
    noun = re.search(r'(エースカード|ユニットカード|コマンドカード|カード)$', b)
    if noun and not re.search(r'(カード)$', a):
        return a + 'の' + noun.group(1), b
    return a, b


def _zdesc(d):
    """장수 조건의 카드 묘사 -> 필터 (없으면 전부)"""
    if not d:
        return {}
    d = d.strip()
    m = re.fullmatch(r'「([^」]+)」', d)
    if m:
        return {'name': m.group(1)}
    r = _zdesc0(d)
    if r is not None or 'か' not in d:
        return r
    for i in _top_ka(d):
        fl, fr = _zdesc0(d[:i]), _zdesc0(d[i + 1:])
        if fl is not None and fr is not None and fl and fr:
            side = fl.pop('side', None) or fr.pop('side', None)
            return {**({'side': side} if side else {}), 'or': [fl, fr]}
    return None


_ITEM = r'(?:⁅[^⁆]+⁆|黒|青|白|赤|ハート|スペード|ダイヤ|クラブ)'


def _each_filters(d):
    """「AとBをそれぞれ」「A、B、CのXをそれぞれ」 → 조건 목록"""
    d = d.strip('、')
    m = re.fullmatch(r'(?P<pre>.*?)(?P<items>(?:' + _ITEM + r'、)+' + _ITEM + r')の(?P<noun>.+)', d)
    if m:
        fs = [_zdesc(m.group('pre') + it + 'の' + m.group('noun')) for it in m.group('items').split('、')]
        return fs if all(f is not None for f in fs) else None
    m = re.fullmatch(r'(?P<pre>.*?)(?P<items>(?:「[^」]+」、)+「[^」]+」)いずれかを含む(?P<noun>.+)', d)
    if m:
        fs = [_zdesc(m.group('pre') + it + 'を含む' + m.group('noun')) for it in m.group('items').split('、')]
        return fs if all(f is not None for f in fs) else None
    ks = [i for i in range(len(d)) if d[i] == 'と' and d[:i].count('「') == d[:i].count('」')]
    for i in ks:
        L, R = d[:i], d[i + 1:]
        fl, fr = _zdesc(L), _zdesc(R)
        if fl is None or fr is None:
            # 공통 앞부분(「コスト5以下の、カード名に、」)이 왼쪽에만 붙은 경우
            mm = re.match(r'(.*、)(?=[^、]*$)', L)
            if mm and fr is not None:
                fl = _zdesc(L)
            continue
        for k, v in fl.items():
            if k not in fr and k not in ('name', 'attr', 'color', 'type', 'ace', 'or'):
                fr[k] = v
        return [fl, fr]
    return None


KWMAP = {'デコイ': 'decoy', 'バーサーク': 'berserk', 'ブリッツ': 'blitz'}


def _cdesc(d):
    """「それが~なら」의 카드 묘사"""
    if _zdesc(d) is not None:
        return _zdesc(d)
    d = re.sub(r'(?:の)?カード$', '', d)
    return _zdesc(d) if _zdesc(d) is not None else parse_desc(d) or parse_desc(d + 'の')


def _zdesc0(d):
    m = re.fullmatch(r'「([^」]+)」', d)
    if m:
        return {'name': m.group(1)}
    noun = re.search(r'(エースカード|エース|ユニットカード|ユニット|コマンドカード|カード)$', d)
    core = d[:noun.start()] if noun else d
    f = parse_desc(core) if core else {}
    if f is None and core and not core.endswith('の'):
        f = parse_desc(core + 'の')
    if f is None:
        return None
    return noun_filter(f, noun.group(1) if noun else '')


_ORCOND = {}


def parse_cond(t):
    """'あなたのライフがレッドゾーン' 같은 조건문 (なら/中/で 앞부분) -> dict | None"""
    t = t.strip('、')
    if t.endswith('てい'):
        t += 'る'
    t = re.sub(r'ていた$', 'ている', t)
    if re.search(r'てい$', t):
        t += 'る'
    elif re.search(r'(?:し|引い|置い|加え|つけ|着せ|戻し|かっ|させ|入れ替え)$', t) and not t.endswith('ない'):
        t += 'た'   # 「~したら」의 어간
    t = re.sub(r'していて、', 'しているかつ', t)
    t = re.sub(r'(?<=に)いて、', 'いるかつ', t)
    t = re.sub(r'着ていて', '着ているかつこのユニットが', t)
    t = re.sub(r'クラスカードが(\d+)枚以上ついたこのユニットがレストしている', r'このユニットにつけたクラスカードが\1枚以上かつこのユニットがレストしている', t)
    if t == '__ORCOND__' and _ORCOND.get('c'):
        return list(_ORCOND['c'])
    t = t.replace('「エースか「', '「エース」か「')
    mm = re.search(r'(?:かつ|、)(?=あなたの、)', t)
    if mm and mm.start() > 0:   # 「このユニットがレストしていて、あなたの、テリトリー開放中で…」: 앞뒤를 따로 읽어 합침
        a_t = re.sub(r'(が|し)(い)て$', r'\1\2る', t[:mm.start()])
        a_, b_ = parse_cond(a_t), parse_cond(t[mm.end():])
        return None if a_ is None or b_ is None else a_ + b_
    mte = re.fullmatch(r'あなたの、テリトリー開放中で(?P<d>.+?)がいる', t)
    if mte and _zdesc(mte.group('d')) is not None:
        return [{'terr': 1}, {'exists': dict(_zdesc(mte.group('d')), side='own', type='unit')}]
    mte = re.fullmatch(r'あなたの、テリトリー開放中で(?P<x>.+)', t)
    if mte and parse_cond('あなたの' + mte.group('x')) is not None:
        return [{'terr': 1}] + parse_cond('あなたの' + mte.group('x'))
    t = re.sub(r'^あなたの、(称号「[^」]+」か(?:称号)?「[^」]+」のテリトリー開放中)', r'あなたの\1', t)
    if t.startswith('あなたの、') and not re.match(r'あなたの、称号「[^」]+」か', t):   # 「あなたの、手札が1枚以下でテリトリー開放中」
        xs = re.split(r'で(?=テリトリー|ライフ|手札|ドロップ|エナジー|称号|リムーブ|フィールド|コスト\d)|(?<=がい)て、?(?=テリトリー|あなた)|(?<=てい)て(?=テリトリー)', t[5:])
        xs = [x + 'る' if x.endswith('がい') or x.endswith('てい') else x for x in xs]
        t = 'かつ'.join('あなたの' + x if not x.startswith(('あなた', '相手')) else x for x in xs)
    t = re.sub(r'が開放されていて、', 'が開放されているかつ', t)
    t = re.sub(r'引いていた$', '引いている', t)
    t = re.sub(r'(ユニット|エース)がいて、?', r'\1がいるかつ', t)
    _LAST.setdefault('cond', None)
    C = [
        (r'あなたの山札が(?P<n>\d+)枚', lambda m: {'deckEq': int(m.group('n'))}),
        (r'あなたの裏のエナジーが(?P<n>\d+)枚以上', lambda m: {'downEnergyGE': int(m.group('n'))}),
        (r'このターン(?:に)?あなたがコマンドをプレイしてい(?:る|た)', lambda m: {'cmdTurn': 1}),
        (r'このターン(?:に)?あなたのユニットが卒業してい(?:る|た)', lambda m: {'hist': {'scope': 'turn', 'k': 'grad', 'side': 'own'}}),
        (r'相手のエナジーがあなたのエナジーより多い', lambda m: {'cmp': {'a': {'k': 'oppEnergy'}, 'op': 'gt', 'b': {'k': 'myEnergy'}}}),
        (r'このターン(?:に)?あなたがダメージを受けていない', lambda m: {'not': {'meDmgTurn': 1}}),
        (r'このターン(?:に)?相手がダメージを受けていない', lambda m: {'not': {'oppDmgTurn': 1}}),
        # 수치 비교 (대상·공개/드롭한 카드·배틀 상대·에너지 장수)
        (r'対象のコストが公開したカードのコスト(?P<o>以下|以上)', lambda m: {'cmp': {'a': {'k': 'T', 'what': 'cost'}, 'op': 'le' if m.group('o') == '以下' else 'ge', 'b': {'k': 'milled', 'what': 'cost', 'agg': 'last'}}}),
        (r'対象がバトル相手(?:のユニット)?と同じコスト', lambda m: {'cmp': {'a': {'k': 'T', 'what': 'cost'}, 'op': 'eq', 'b': {'k': 'vs', 'what': 'cost'}}}),
        (r'それらのコストの合計が、?対象のコストの合計(?P<o>以上|以下)', lambda m: {'cmp': {'a': {'k': 'milled', 'what': 'cost', 'agg': 'sum'}, 'op': 'ge' if m.group('o') == '以上' else 'le', 'b': {'k': 'T', 'what': 'cost', 'agg': 'sum'}}}),
        (r'そのカードのコストが(?P<n>\d+)(?P<o>以上|以下)', lambda m: {'cmp': {'a': {'k': 'milled', 'what': 'cost', 'agg': 'last'}, 'op': 'ge' if m.group('o') == '以上' else 'le', 'b': {'k': 'const', 'n': int(m.group('n'))}}}),
        (r'対象がドロップしたカード以下のコスト', lambda m: {'cmp': {'a': {'k': 'T', 'what': 'cost'}, 'op': 'le', 'b': {'k': 'milled', 'what': 'cost', 'agg': 'last'}}}),
        (r'対象のコストがドロップしたカードのコストの合計(?P<o>以下|以上)', lambda m: {'cmp': {'a': {'k': 'T', 'what': 'cost'}, 'op': 'le' if m.group('o') == '以下' else 'ge', 'b': {'k': 'milled', 'what': 'cost', 'agg': 'sum'}}}),
        (r'対象の(?P<w>パワー|コスト)の合計が(?P<n>\d+)(?P<o>以下|以上)', lambda m: {'cmp': {'a': {'k': 'T', 'what': 'power' if m.group('w') == 'パワー' else 'cost', 'agg': 'sum'}, 'op': 'le' if m.group('o') == '以下' else 'ge', 'b': {'k': 'const', 'n': int(m.group('n'))}}}),
        (r'相手のエナジーの枚数が対象のコスト(?P<o>以上|以下)', lambda m: {'cmp': {'a': {'k': 'oppEnergy'}, 'op': 'ge' if m.group('o') == '以上' else 'le', 'b': {'k': 'T', 'what': 'cost'}}}),
        (r'対象のコストより、?相手のエナジーの枚数が少ない', lambda m: {'cmp': {'a': {'k': 'oppEnergy'}, 'op': 'lt', 'b': {'k': 'T', 'what': 'cost'}}}),
        (r'対象のコスト差が1で共通の属性を持つ', lambda m: {'tPairDiff1Attr': 1}),
        (r'対象と共通の色を持つ、?相手のエナジーが(?P<n>\d+)枚以下', lambda m: {'oppEnergyTColorLE': int(m.group('n'))}),
        (r'それが対象と共通の色を持っていない', lambda m: {'milledColorNotT': 1}),
        (r'(?:ドロップしたカード|それら)が持つ称号が合計(?P<n>\d+)種類以上', lambda m: {'milledTitlesGE': int(m.group('n'))}),
        (r'あなたのドロップしたユニットのパワーがバトル相手のパワー以上だった', lambda m: {'evPowGEvs': 1}),
        (r'公開したログの総コストが合計(?P<n>\d+)以上', lambda m: {'logCostGE': int(m.group('n'))}),
        (r'【(?P<k>[^】]+)】以外をドロップした', lambda m: {'milledNot': {'kwText': m.group('k')}}),
        (r'コスト(?P<n>\d+)(?P<o>以上|以下)', lambda m: {'milled': {'costGE' if m.group('o') == '以上' else 'costLE': int(m.group('n'))}}),
        (r'このユニットかバトル相手が(?P<c>赤|青|白|黒)', lambda m: {'selfOrVsColor': {'赤': 'red', '青': 'blue', '白': 'white', '黒': 'black'}[m.group('c')]}),
        (r'対象がこのターン(?:に)?効果でスタンドしていない', lambda m: {'tEffStoodNot': 1}),
        (r'しない', lambda m: {'did': 0}),
        # 여러 조건 묶음
        (r'あなたの(?P<z>ドロップゾーン|リムーブゾーン)に(?P<l>(?:⁅(?:スペード|ハート|ダイヤ|クラブ)⁆、?)+)がそれぞれ別に(?P<n>\d+)枚以上ある', lambda m: {'attrsEachN': {'zone': 'drop' if m.group('z') == 'ドロップゾーン' else 'remove', 'attrs': re.findall(r'スペード|ハート|ダイヤ|クラブ', m.group('l')), 'n': int(m.group('n'))}}),
        (r'あなたのドロップゾーンにコスト(?P<a>\d+)[~～](?P<b>\d+)のカードがそれぞれある', lambda m: {'costsEach': list(range(int(m.group('a')), int(m.group('b')) + 1))}),
        (r'あなたの(?P<o>他の)?、?(?P<l>(?:(?:ハート|スペード|ダイヤ|クラブ)と?)+)のユニットがそれぞれ別に1枚以上いる', lambda m: {'existsEach': [{'attr': [a], 'type': 'unit', 'side': 'own', **({'notSelf': 1} if m.group('o') else {})} for a in re.findall('ハート|スペード|ダイヤ|クラブ', m.group('l'))]}),
        (r'あなたの(?P<a>[^、。]+?)を含むエナジーと(?P<b>[^、。]+?)を含むエナジーがそれぞれ別に1枚以上ある', lambda m: {'all': [{'zc': {'side': 'own', 'zone': 'エナジー', 'f': {'name': m.group(x).strip('「」')}, 'n': 1, 'cmp': 'ge'}} for x in ('a', 'b')]}),
        (r'あなたの、?(?P<a>[^、。]+?)ユニットか(?P<b>[^、。]+?)ユニットがいる', lambda m: (lambda fa, fb: fa is not None and fb is not None and {'any': [{'exists': dict(fa, side='own', type='unit')}, {'exists': dict(fb, side='own', type='unit')}]})(parse_desc(m.group('a')), parse_desc(m.group('b')))),
        (r'あなたの(?P<d>[^、。]+?)がいない', lambda m: (lambda f: f is not None and {'none': dict(f, side='own', type='unit')})(_zdesc(m.group('d')))),
        (r'あなたの(?P<d>「[^」]+」)がリムーブされている', lambda m: {'zc': {'side': 'own', 'zone': 'リムーブゾーン', 'f': {'name': m.group('d').strip('「」')}, 'n': 1, 'cmp': 'ge'}}),
        # 이번 판 기록으로 판단하는 조건
        (r'(?P<sc>このターン(?:に)?|このゲーム中(?:に)?)(?P<w>あなた|相手)のライフから(?P<d>[^、。]*?)が(?:ドロップされ|ドロップし|出)てい(?:る|た)', lambda m: _histc(m, {'k': 'dmg'})),
        (r'(?P<sc>このターン(?:に)?|このゲーム中(?:に)?)(?P<w>あなた|相手)の(?P<d>[^、。]*?)が(?P<z>ドロップゾーン|リムーブゾーン|エナジーゾーン|手札|ライフ(?:ゾーン)?)に置かれてい(?:る|た)',
         lambda m: _histc(m, {'k': 'mv', 'to': {'ドロップゾーン': 'drop', 'リムーブゾーン': 'remove', 'エナジーゾーン': 'energy', '手札': 'hand'}.get(m.group('z'), 'life')})),
        (r'(?P<sc>このターン(?:に)?|このゲーム中(?:に)?)(?P<w>あなた|相手)の(?P<d>[^、。]*?)が(?:フィールドから)?ドロップされてい(?:る|た)', lambda m: _histc(m, {'k': 'mv', 'from': 'field', 'to': 'drop'})),
        (r'(?P<sc>このターン(?:に)?|このゲーム中(?:に)?)(?P<w>あなた|相手)の(?P<d>[^、。]*?)が登場してい(?:る|た)', lambda m: _histc(m, {'k': 'mv', 'notFrom': 'field', 'to': 'field'})),
        (r'(?P<sc>このターン(?:に)?|このゲーム中(?:に)?)(?P<w>あなた|相手)の(?P<d>[^、。]*?)がリムーブされてい(?:る|た)', lambda m: _histc(m, {'k': 'mv', 'to': 'remove'})),
        (r'(?P<sc>このターン(?:に)?|このゲーム中(?:に)?)(?P<w>あなた|相手)が(?P<d>[^、。]*?)をプレイしてい(?:る|た)', lambda m: _histc(m, {'k': 'play'})),
        (r'このコマンドがこのターン初めてプレイされたコマンド', lambda m: {'hist': {'scope': 'turn', 'k': 'play', 'side': 'own', 'f': {'type': 'command'}, 'n': 1, 'cmp': 'eq'}}),
        (r'(?P<w>あなた|相手)の、?パワーが元々のパワーより高いユニットがいる', lambda m: {'oppAbovePrinted': 'own' if m.group('w') == 'あなた' else 'opp'}),
        (r'表にしたいずれかのエナジーと共通の色を持つあなたのユニットがいる', lambda m: {'milledColorUnit': 1}),
        (r'あなたのつけたログが(?P<n>\d+)枚より少ない', lambda m: {'logLT': int(m.group('n'))}),
        (r'対象がフィールドにいる', lambda m: {'tOnField': 1}),
        (r'このターン(?:に)?対象が相手プレイヤーにダメージを与えてい(?:る|た)', lambda m: {'tDealtPlayer': 1}),
        (r'(?:それ|そのカード)が(?P<d>[^、。]+?)(?:カード)?', lambda m: (lambda f: f is not None and {'milled': f})(_zdesc(m.group('d')) if _zdesc(m.group('d')) is not None else _zdesc(m.group('d') + 'カード'))),
        (r'(?:ドロップし|引い|手札に加え|加え|置い|つけ|リムーブし|公開し|登場させ|戻し|入れ替え|着せ|開放し|プレイし|レストし|あなたのユニットをレストし)た', lambda m: {'did': 1}),
        (r'(?:リムーブ|公開|ドロップ)しない|(?:戻さ|引か|公開し)なかった|的中しなかった', lambda m: {'did': 0}),
        (r'(?P<c>赤|青|白|黒)のカードを(?P<n>\d+)枚ドロップした', lambda m: {'milledN': {'f': {'color': [{'赤': 'red', '青': 'blue', '白': 'white', '黒': 'black'}[m.group('c')]]}, 'n': int(m.group('n'))}}),
        (r'(?P<l>(?:(?:赤|青|白|黒)、?)+)のカードをそれぞれ別にドロップした', lambda m: {'milledEach': [{'赤': 'red', '青': 'blue', '白': 'white', '黒': 'black'}[c] for c in re.findall('[赤青白黒]', m.group('l'))]}),
        (r'(?P<d>[^、。]+?)を(?P<n>\d+)枚以上公開した', lambda m: (lambda f: f is not None and {'milledN': {'f': f, 'n': int(m.group('n'))}})(_zdesc(m.group('d')))),
        (r'(?P<n>\d+)色リムーブした', lambda m: {'milledColorsGE': int(m.group('n'))}),
        (r'このユニットがこのターン(?:に)?アタックしている', lambda m: {'selfAttackedTurn': 1}),
        (r'このターン(?:に)?あなたのエースが登場している', lambda m: {'aceEnteredTurn': 1}),
        (r'このターン(?:に)?あなたのユニットが登場していない', lambda m: {'ownEnteredTurnNot': 1}),
        (r'このターン(?:に)?あなたの他のユニットが登場している', lambda m: {'otherEntered': 1}),
        (r'このターン(?:に)?相手のユニットがドロップされている', lambda m: {'oppDroppedTurn': 1}),
        (r'そのターンに相手のユニットが(?P<n>\d+)枚以上登場している', lambda m: {'oppEnteredGE': int(m.group('n'))}),
        (r'このターン(?:に)?あなたのライフ(?:ゾーン)?から(?:ドロップゾーンに)?(?:⁅バスターアイコン⁆|⁅B⁆)が(?:ドロップされ|ドロップし|置かれ)てい(?:る|た)', lambda m: {'lifeBusterTurn': 1}),
        (r'(?:このターン(?:に)?)?あなたのユニットが【ブライト】してい(?:る|た)', lambda m: {'brightTurn': 1}),
        (r'このターン(?:に)?あなたが[【⁅]結束[】⁆]でカードを引いてい(?:る|た)', lambda m: {'kessoDrew': 1}),
        (r'(?:あなたの)?ドロップゾーンが(?P<n>\d+)枚以上', lambda m: {'dropGE': int(m.group('n'))}),
        (r'バトル相手が⁅(?P<i>バスター|ショット)アイコン⁆', lambda m: {'vsF': {'icon': 'buster' if m.group('i') == 'バスター' else 'shot'}}),
        (r'相手のユニットの枚数があなたのユニットより(?P<n>\d+)枚以上多い', lambda m: {'oppMoreBy': int(m.group('n'))}),
        (r'(?:そのターン中、)?あなたの(?P<d>[^、。]*?)(?:ユニット)?がいる', lambda m: (lambda f: f is not None and {'exists': dict(f, side='own', type='unit')})(_zdesc(m.group('d')) if m.group('d') else {})),
        (r'(?P<w>あなた|相手)の(?P<d>[^、。]+?)ユニットが(?:合計)?(?P<n>\d+)枚以上', lambda m: (lambda f: f is not None and {'unitCountGE': {'f': dict(f, side='opp' if m.group('w') == '相手' else 'own', type='unit'), 'n': int(m.group('n'))}})(parse_desc(m.group('d')))),
        (r'あなたの、?このユニットと共通の称号を持つテリトリー開放中', lambda m: {'hold': 1}),
        (r'これが手札からプレイされた', lambda m: {'fromHand': 1}),
        (r'対象が(?P<k>スタンド|レスト)している', lambda m: {'tRested': 1 if m.group('k') == 'レスト' else 0}),
        (r'このターン(?:に)?あなたがカードを(?P<n>\d+)枚以上プレイしている', lambda m: {'playedGE': int(m.group('n'))}),
        (r'あなたがこのターン(?:に)?コマンドを解決している', lambda m: {'cmdTurn': 1}),
        (r'(?:この|あなたの)テリトリーがこのターン(?:に)?開放されていない', lambda m: {'terrOpenedTurnNot': 1}),
        (r'このコマンドが【CAD】でプレイされ(?:た|ている)', lambda m: {'cadPlay': 1}),
        (r'このコマンドをあなたのメインフェイズにプレイした', lambda m: {'playedMain': 1}),
        (r'あなたのクラスカードのエナジーが(?P<n>\d+)枚以上', lambda m: {'classEnergyGE': int(m.group('n'))}),
        (r'あなたの(?P<z>ドロップゾーン|リムーブゾーン)の(?P<d>[^、。]+?)が(?P<n>\d+)種類以上', lambda m: (lambda f: f is not None and {'zc': {'side': 'own', 'zone': m.group('z'), 'f': f, 'n': int(m.group('n')), 'cmp': 'ge', 'kinds': 1}})(_zdesc(m.group('d')))),
        (r'(?P<l>(?:(?:ハート|スペード|ダイヤ|クラブ)か?)+)を1枚以上ドロップした', lambda m: {'milled': {'attr': re.findall('ハート|スペード|ダイヤ|クラブ', m.group('l'))}}),
        (r'この効果であなたのユニットを1枚以上レストした', lambda m: {'tAnyOwn': 1}),
        (r'ドロップさせた', lambda m: {'did': 1}),
        (r'(?P<n>\d+)枚(?:登場させ|ドロップし|以上表にし|以上戻し)た|合計(?P<n2>\d+)枚以上戻した', lambda m: {'didN': int(m.group('n') or m.group('n2'))}),
        (r'(?P<d>[^、。]+?)をリムーブした', lambda m: (lambda f: f is not None and {'milled': f})(_zdesc(m.group('d')))),
        (r'対象が(?P<d>[^、。]+)', lambda m: (lambda f: f is not None and {'tF': f})(_zdesc(m.group('d')) if _zdesc(m.group('d')) is not None else parse_desc(m.group('d')))),
        (r'(?:エースに)?つけた', lambda m: {'did': 1}),
        (r'(?P<d>[^、。]+?)を置いた', lambda m: (lambda f: f is not None and {'milled': f})(_zdesc(m.group('d')))),
        (r'相手ターン', lambda m: {'oppTurn': 1}),
        (r'このターン(?:に)?あなたがテリトリーを開放している', lambda m: {'terrOpenedTurn': 1}),
        (r'各プレイヤーのテリトリーが開放されている', lambda m: {'bothTerr': 1}),
        (r'このユニットが手札から登場している', lambda m: {'fromHand': 1}),
        (r'このターンこのユニットが効果でスタンドしていない', lambda m: {'notEffStood': 1}),
        (r'相手の、?手札とユニットが合計(?P<n>\d+)枚以上', lambda m: {'oppHandUnitsGE': int(m.group('n'))}),
        (r'あなたの、?(?P<l>(?:(?:赤|青|白|黒)と?)+)のエナジーが(?:それぞれ)?ある', lambda m: {'energyEach': {'colors': [{'赤': 'red', '青': 'blue', '白': 'white', '黒': 'black'}[c] for c in re.findall('[赤青白黒]', m.group('l'))], 'n': 1}}),
        (r'あなたのリムーブゾーンに(?P<l>(?:⁅(?:スペード|ハート|ダイヤ|クラブ)⁆、?)+)がある', lambda m: {'removeAttrsEach': re.findall(r'スペード|ハート|ダイヤ|クラブ', m.group('l'))}),
        (r'このカードと共通の称号を持つ(?:あなたの)?テリトリー(?:が)?開放中', lambda m: {'hold': 1}),
        (r'このターン(?:に)?あなたがコマンドをプレイしていない', lambda m: {'cmdTurnNot': 1}),
        (r'各プレイヤーのユニットが合計(?P<n>\d+)枚以上いる', lambda m: {'allUnitsGE': int(m.group('n'))}),
        (r'それぞれカード名が同じ相手のユニットが(?P<n>\d+)枚以上いる', lambda m: {'oppSameNameGE': int(m.group('n'))}),
        (r'あなたのテリトリーゾーンに(?P<d>[^、。]+?)がある', lambda m: (lambda f: f is not None and {'terrZoneHas': f})(_zdesc(m.group('d')))),
        (r'このターン(?:に)?あなたのカードがリムーブされてい(?:る|た)', lambda m: {'removedTurn': 1}),
        (r'あなたのユニットが合計(?P<n>\d+)色(?:以上)?', lambda m: {'unitColorsGE': int(m.group('n'))}),
        (r'相手のメインフェイズ(?:中)?', lambda m: {'oppTurn': 1, 'phase': 'main'}),
        (r'あなたのメインフェイズ(?:中)?', lambda m: {'myTurn': 1, 'phase': 'main'}),
        (r'このユニットがエースとバトルする', lambda m: {'battleVsAce': 1}),
        (r'あなたの「(?P<n>[^」]+)」が開放中', lambda m: {'terrName': m.group('n')}),
        (r'あなたのドロップゾーンにある称号が合計(?P<n>\d+)種類以上', lambda m: {'dropTitlesGE': int(m.group('n'))}),
        (r'あなたの(?P<z>ドロップゾーン|リムーブゾーン)に(?:カード名に、)?(?P<a>[^、。]+?)と(?P<b>[^、。]+?)がそれぞれある',
         lambda m: (lambda Z, fa, fb: fa is not None and fb is not None and {'zcAll': [{'side': 'own', 'zone': Z, 'f': fa, 'n': 1, 'cmp': 'ge'}, {'side': 'own', 'zone': Z, 'f': fb, 'n': 1, 'cmp': 'ge'}]})(
             m.group('z'), _zdesc(_pair(m.group('a'), m.group('b'))[0]), _zdesc(_pair(m.group('a'), m.group('b'))[1]))),
        (r'あなたのフィールドかドロップゾーンに(?P<d>[^、。]+?)がある', lambda m: (lambda f: f is not None and {'zc': {'side': 'own', 'zones': ['field', 'drop'], 'f': f, 'n': 1, 'cmp': 'ge'}})(_zdesc(m.group('d')))),
        (r'あなたの(?P<z>ドロップゾーン|リムーブゾーン)に(?P<d>[^、。]+?)が(?P<n>\d+)(?P<k>枚|種類)(?:以上)?ある', lambda m: (lambda f: f is not None and {'zc': {'side': 'own', 'zone': m.group('z'), 'f': f, 'n': int(m.group('n')), 'cmp': 'ge', **({'kinds': 1} if m.group('k') == '種類' else {})}})(_zdesc(m.group('d')))),
        (r'あなたの(?P<d>[^、。]+?)エナジーが(?:合計)?(?P<n>\d+)枚以上', lambda m: (lambda f: f is not None and {'zc': {'side': 'own', 'zone': 'エナジー', 'f': f, 'n': int(m.group('n')), 'cmp': 'ge'}})(_zdesc(m.group('d')))),
        (r'(?:あなたの)?ライフがレッドゾーン', lambda m: {'red': 1}),
        (r'相手のユニットがあなたより多い', lambda m: {'oppMore': 1}),
        (r'相手のユニットの枚数があなたのユニット以上', lambda m: {'oppGE': 1}),
        (r'対象が【(?P<k>デコイ|ブリッツ|バーサーク)】を持つ', lambda m: {'tHasKw': {'デコイ': 'decoy', 'ブリッツ': 'blitz', 'バーサーク': 'berserk'}[m.group('k')]}),
        (r'山札から(?P<d>[^、。]*?)をドロップした?', lambda m: {'milled': parse_desc(m.group('d').replace('バスターアイコン', 'バスターの'))}),
        (r'(?:ドロップ|それ)しない|そうしない', lambda m: {'did': 0}),
        (r'あなたのドロップゾーンの(?P<d>[^、。]*?)(?:ユニットカード|カード)?が(?P<n>\d+)枚以上', 'count'),
        (r'(?:さらに)?(?P<n>\d+)(?:枚|種類)(?:以上|以下)?', 'again'),
        (r'相手のライフがレッドゾーン', lambda m: {'oppRed': 1}),
        (r'あなたのテリトリー(?:が開放されている|開放中)', lambda m: {'terr': 1}),
        (r'あなたの称号「(?P<t>[^」]+)」のテリトリー(?:が開放されている|開放中)', lambda m: {'terrTitle': m.group('t')}),
        (r'あなたのターン(?:中)?', lambda m: {'myTurn': 1}),
        (r'相手のターン(?:中)?', lambda m: {'oppTurn': 1}),
        (r'このユニットがレストしている', lambda m: {'selfRested': 1}),
        (r'このユニットがスタンドしている', lambda m: {'selfRested': 0}),
        (r'あなたのドロップゾーン(?:のカード)?が(?P<n>\d+)枚以上', lambda m: {'dropGE': int(m.group('n'))}),
        (r'あなたの手札が(?P<n>\d+)枚以下', lambda m: {'handLE': int(m.group('n'))}),
        (r'相手のターン中、このユニットがレストしている', lambda m: {'all': [{'oppTurn': 1}, {'selfRested': 1}]}),
        (r'あなたの、テリトリー開放中で(?P<d>.+?)がいる', lambda m: (lambda f: f is not None and {'all': [{'terr': 1}, {'exists': dict(f, side='own', type='unit')}]})(_zdesc(m.group('d')))),
        (r'あなたの手札が(?P<n>\d+)枚以上', lambda m: {'handGE': int(m.group('n'))}),
        (r'あなたのエナジーが(?P<n>\d+)枚以上', lambda m: {'energyGE': int(m.group('n'))}),
        (r'相手のエナジーが(?P<n>\d+)枚以上', lambda m: {'oppEnergyGE': int(m.group('n'))}),
        (r'あなたのライフが(?P<n>\d+)枚以下', lambda m: {'lifeLE': int(m.group('n'))}),
        (r'相手のライフが(?P<n>\d+)枚以下', lambda m: {'oppLifeLE': int(m.group('n'))}),
        (r'あなたのライフが相手(?:のライフ)?より少ない', lambda m: {'lifeLess': 1}),
        (r'このターン(?:に)?このユニットが登場している', lambda m: {'enteredThisTurn': 1}),
        (r'このユニットが【コスプレ】で登場した', lambda m: {'cos': 1}),
        (r'このユニットにクラスカードがついている', lambda m: {'selfHasClass': 1}),
        (r'あなたの他のユニットがいない', lambda m: {'noOther': 1}),
        (r'相手が引かなかった', lambda m: {'oppDeclined': 1}),
        (r'このターン(?:に)?相手がダメージを受けている', lambda m: {'oppDmgTurn': 1}),
        (r'対象がエース', lambda m: {'tF': {'ace': 1}}),
        (r'対象が(?P<d>[^、。]*?)(?:エースカード|ユニットカード|カード|ユニット)', lambda m: (lambda f: f is not None and {'tF': {**f, **({'ace': 1} if 'エース' in m.group(0) else {})}})(parse_desc(m.group('d')))),
        (r'各プレイヤーのライフの枚数が同じ', lambda m: {'lifeEq': 1}),
        (r'エースカードをドロップした', lambda m: {'milled': {'ace': 1}}),
        (r'相手のエナジーがあなたのエナジーより(?P<n>\d+)枚以上多い', lambda m: {'oppEnergyMore': int(m.group('n'))}),
        (r'あなたのユニットの枚数が相手のユニットの枚数以下', lambda m: {'unitsLE': 1}),
        (r'このユニットのパワーが(?P<n>\d+)以上', lambda m: {'selfPowGE': int(m.group('n'))}),
        (r'このユニットがレストしている', lambda m: {'selfRested': 1}),
        (r'あなたのドロップゾーンに(?P<l>(?:⁅(?:スペード|ハート|ダイヤ|クラブ)⁆、?)+)がある', lambda m: {'dropAttrsEach': re.findall(r'スペード|ハート|ダイヤ|クラブ', m.group('l'))}),
        (r'相手のエナジーが(?P<n>\d+)枚以下', lambda m: {'oppEnergyLE': int(m.group('n'))}),
        (r'あなたのつけたログが(?P<n>\d+)枚以上', lambda m: {'logGE': int(m.group('n'))}),
        (r'(?:このターン(?:に)?)?あなたのユニットが【ブライト】している', lambda m: {'brightTurn': 1}),
        (r'あなたのエナジーが(?P<n>\d+)色(?:以上)?', lambda m: {'energyColorsGE': int(m.group('n'))}),
        (r'このターン(?:に)?あなたが【結束】でカードを引いている', lambda m: {'kessoDrew': 1}),
        (r'このターン(?:に)?あなたのユニットが【ブライト】している', lambda m: {'brightTurn': 1}),
        (r'あなたのリムーブゾーンが(?P<n>\d+)枚以上', lambda m: {'removeGE': int(m.group('n'))}),
        (r'あなたのライフがイエローゾーン', lambda m: {'yellow': 1}),
        (r'相手の手札が(?P<n>\d+)枚以下', lambda m: {'oppHandLE': int(m.group('n'))}),
        (r'相手のユニットが(?P<n>\d+)枚以上', lambda m: {'oppUnitsGE': int(m.group('n'))}),
        (r'あなたの伏せたカードが(?:ない|無い)', lambda m: {'setCount': 0}),
        (r'あなたの伏せたカードがある', lambda m: {'setHas': 1}),
        (r'(?:ドロップした|それらの)カードのコストの合計が(?P<n>\d+)以上', lambda m: {'milledCostGE': int(m.group('n'))}),
        (r'(?P<d>(?:カード名に、)?[^、。]+?)を(?:手札から)?ドロップした', lambda m: (lambda f: f is not None and {'milled': f})(parse_desc(m.group('d').replace('ユニットカード', 'ユニット') + 'の') if not m.group('d').endswith('カード') else noun_filter(parse_desc(re.sub(r'(ユニット|コマンド)?カード$', '', m.group('d'))) or {}, re.search(r'(ユニットカード|コマンドカード|カード)$', m.group('d')).group(1)))),
        (r'このユニットが【(?P<n>[^】]+)】を着ている', lambda m: {'wearing': m.group('n').split('/')}),
        (r'このターン(?:に)?あなたがダメージを受けている', lambda m: {'meDmgTurn': 1}),
        (r'あなたの山札が(?P<n>\d+)枚以下', lambda m: {'deckLE': int(m.group('n'))}),
        (r'このターン(?:に)?あなたの他のユニットが登場している', lambda m: {'otherEntered': 1}),
        (r'(?:あなたの、?)?つけた契約書が(?P<n>\d+)枚以上', lambda m: {'contractGE': int(m.group('n'))}),
        (r'あなたのドロップゾーンに(?P<d>[^、。]+?)がある', lambda m: (lambda f: f is not None and {'zoneHas': {'zone': 'drop', 'f': f}})(parse_desc(m.group('d') + 'の') if parse_desc(m.group('d') + 'の') is not None else _zdesc(m.group('d')))),
        (r'バトル相手が(?P<c>赤|青|白|黒)', lambda m: {'vsF': {'color': [{'赤': 'red', '青': 'blue', '白': 'white', '黒': 'black'}[m.group('c')]]}}),
        (r'このユニットにつけたクラスカードが(?P<n>\d+)枚以上', lambda m: {'selfClassGE': int(m.group('n'))}),
        (r'あなたの(?:称号「(?P<t>[^」]+)」の)?テリトリーが開放(?:中|されている)?', lambda m: {'terrTitle': m.group('t')} if m.group('t') else {'terr': 1}),
        (r'あなたの(?:称号「(?P<t>[^」]+)」の)?テリトリー開放', lambda m: {'terrTitle': m.group('t')} if m.group('t') else {'terr': 1}),
        (r'あなたが「[^」]+」', lambda m: {'never': 1}),
        (r'このターン(?:に)?あなたが【スカウト】している', lambda m: {'scoutedTurn': 1}),
        (r'あなたのドロップゾーンに(?P<l>(?:⁅(?:スペード|ハート|ダイヤ|クラブ)⁆、?)+)がそれぞれ別に1枚以上ある', lambda m: {'dropAttrsEach': re.findall(r'スペード|ハート|ダイヤ|クラブ', m.group('l'))}),
        (r'あなたの、?称号「(?P<a>[^」]+)」か(?:称号)?「(?P<b>[^」]+)」のテリトリー開放中', lambda m: {'terrTitleAny': [m.group('a'), m.group('b')]}),
        # 일반 장수 조건: 「あなたのリムーブゾーンのエースカードが2枚以上」「相手の表のエナジーが3枚以下」
        (r'(?P<w>あなた|相手)の(?P<z>ドロップゾーン|リムーブゾーン|手札|ライフ|表のエナジー|裏のエナジー|エナジー|他のユニット|ユニット)(?:の(?P<d>[^、。]*?))?が(?:合計)?(?P<n>\d+)枚(?P<c>以上|以下)?',
         lambda m: (lambda f: f is not None and {'zc': {'side': 'opp' if m.group('w') == '相手' else 'own', 'zone': m.group('z'), 'f': f, 'n': int(m.group('n')), 'cmp': 'le' if m.group('c') == '以下' else 'ge' if m.group('c') else 'eq'}})(_zdesc(m.group('d')))),
        (r'(?P<w>あなた|相手)の(?P<z>ドロップゾーン|リムーブゾーン|手札|エナジーゾーン|フィールド)に(?P<d>[^、。]+?)がある',
         lambda m: (lambda f: f is not None and {'zc': {'side': 'opp' if m.group('w') == '相手' else 'own', 'zone': m.group('z'), 'f': f, 'n': 1, 'cmp': 'ge'}})(_zdesc(m.group('d')))),
        (r'(?P<w>あなた|相手)の(?P<z>ドロップゾーン|リムーブゾーン|手札|エナジーゾーン|フィールド)に(?P<d>[^、。]+?)がない',
         lambda m: (lambda f: f is not None and {'zc': {'side': 'opp' if m.group('w') == '相手' else 'own', 'zone': m.group('z'), 'f': f, 'n': 0, 'cmp': 'le'}})(_zdesc(m.group('d')))),
        (r'あなたのテリトリーが(?:無い|ない)', lambda m: {'noTerr': 1}),
        (r'あなたのテリトリーが開放されていない', lambda m: {'terr': 0}),
        (r'(?P<d>[^、。]*?)' + NOUN + r'がいる', None),
        (r'(?P<d>[^、。]*?)' + NOUN + r'がいない', 'none'),
        (r'あなたの(?:エナジーゾーンに)?(?P<d>[^、。]*?)(?:エースカード|カード|エナジー)が(?:エナジーゾーンに)?ある', 'zone'),
        (r'このコマンドが手札からプレイされた', lambda m: {'fromHand': 1}),
        (r'このコマンドがトリガーでプレイされた', lambda m: {'fromTrigger': 1}),
    ]
    t = re.sub(r'(開放中|開放されている|レッドゾーン|している|がある|がいる|以上|以下)で(?=あなた|この|相手|対象)', r'\1かつ', t)
    parts = re.split(r'(?:で、|かつ、|、かつ|かつ)', t)
    out = []
    for p in parts:
        for rx, fn in C:
            m = re.fullmatch(rx, p)
            if m:
                if fn == 'count':
                    f = parse_desc(m.group('d'))
                    if f is None:
                        f = _zdesc(re.match(r'あなたのドロップゾーンの(.*?)が\d+枚', p).group(1))
                    if f is None:
                        return None
                    if 'ユニット' in p:
                        f['type'] = 'unit'
                    c = {'countGE': {'zone': 'drop', 'f': f, 'n': int(m.group('n'))}}
                    _LAST['cond'] = c
                    out.append(c)
                    break
                if fn == 'again':
                    prev = _LAST.get('cond')
                    if not prev:
                        return None
                    k, v = next(iter(prev.items()))
                    if isinstance(v, dict):
                        c = {k: {**v, 'n': int(m.group('n'))}}
                    elif k.endswith('GE') or k.endswith('LE'):
                        c = {k: int(m.group('n'))}
                    else:
                        return None
                    out.append(c)
                    break
                if fn == 'zone':
                    f = parse_desc(m.group('d'))
                    if f is None:
                        return None
                    if 'エース' in p:
                        f['ace'] = 1
                    out.append({'zoneHas': {'zone': 'energy', 'f': f}})
                    break
                if fn is None or fn == 'none':
                    f = parse_desc(m.group('d'))
                    if f is None:
                        return None
                    f = noun_filter(f, m.group('noun'))
                    out.append({'exists': f} if fn is None else {'none': f})
                else:
                    c = fn(m)
                    if not c:
                        return None
                    if any(k.endswith('GE') or k.endswith('LE') for k in c):
                        _LAST['cond'] = c
                    out.append(c)
                break
        else:
            return None
    return out


_MAY = re.compile(r'(?:て|で)(?:も)?よい')


def _has_choice(steps):
    for st in steps:
        if st.get('may') or st.get('upto') or st.get('op') in ('confirm', 'choose'):
            return True
        if st.get('op') == 'if' and (_has_choice(st.get('then', [])) or _has_choice(st.get('else', []))):
            return True
    return False


def _mark_may(steps):
    st = steps[0]
    if st.get('op') == 'if' and st.get('then'):
        _mark_may(st['then'])
    else:
        st['may'] = 1


def parse_effects(t):
    """효과 문장들 -> 단계 목록 | None. 「~てよい」 문장은 실행 전에 쓸지 묻도록 may 표시"""
    t = re.sub(r'『[^』]*』', lambda m: m.group(0).replace('。', '＄'), t)
    t = re.sub(r'(ユニット)を全て', r'\1全てを', t)
    t = re.sub(r'(山札を上から\d+枚)公開してよい。公開したら、', r'\1公開し、', t)
    t = t.replace('シャッフルて', 'シャッフルして')
    t = re.sub(r'(^|、|。)あなたは自身の', r'\1あなたの', t)
    t = re.sub(r'(^|、|。|さらに)あなたは(ドロップゾーン|手札|エナジーゾーン)の', r'\1あなたの\2の', t)
    t = re.sub(r'相手ユニット', '相手のユニット', t)
    t = re.sub(r'^\{自動\}', '', t)
    t = t.replace('【夢を見ない】', '【夢見ない】')
    t = re.sub(r'を(\d+)枚(まで)?、コストを払わず', r'を\1枚\2コストを払わず', t)
    t = re.sub(r'(山札を上から\d+枚)公開してよい。その中の', r'\1公開し、その中の', t)
    t = re.sub(r'(山札を上から\d+枚)公開する。それが', r'\1公開し、それが', t)
    t = re.sub(r'(カード|ユニットカード)を全て(手札に加え|登場させ)', r'\1全てを\2', t)
    t = re.sub(r'(\d+)億', lambda m: str(int(m.group(1)) * 100000000), t)
    t = re.sub(r'(^|、)手札から', r'\1あなたの手札から', t)
    t = re.sub(r'を(\d+)枚(まで)?対象とし、対象をコストを払わずプレイ', r'を\1枚\2コストを払わずプレイ', t)
    t = re.sub(r'(相手|あなた)の、(?=[^、。]*?ユニット全て)', r'\1の', t)
    t = re.sub(r'あなたの(手札|ドロップゾーン|エナジーゾーン)から、?((?:[^、。を]|を含む|を持つ)+?)を(\d+)枚', r'あなたの\1の\2を\3枚', t)
    t = re.sub(r'(^|、|。)あなたは相手の', r'\1相手の', t)
    t = re.sub(r'対象とし、(手札に戻|登場させ|ドロップさせ|山札の下に置)', r'対象とし、対象を\1', t)
    t = re.sub(r'相手は対象を(?:望む順で)?山札の下に置く', '対象を山札の下に置く', t)
    t = re.sub(r'あなたのライフの先頭を見る。そのカードをドロップゾーンに置いてよい', 'あなたのライフの先頭をドロップしてよい', t)
    out = []
    sents = []
    for x in [x for x in t.split('。') if x.strip()]:
        if x.startswith('それが') and sents:
            sents[-1] += '。' + x
        else:
            sents.append(x)
    for sent in sents:
        sent = sent.replace('＄', '。')
        n0 = len(out)
        if _parse_seq(sent, out) is None:
            return None
        steps = out[max(0, n0 - 1):] if len(out) <= n0 else out[n0:]
        if steps and _MAY.search(sent) and not _has_choice(steps):
            _mark_may(steps)
    _resolve_repeat(out)
    for k, st in enumerate(out):   # 「~する際、~なら代わりに登場させ」: 앞의 에너지 존 이동을 바꿈
        if st.get('op') == '$altEvt':
            ph = out.pop(k)
            for prev in out[:k][::-1]:
                tgt = prev.get('then') if prev.get('op') == 'if' else None
                if tgt and tgt[-1] == {'op': 'energy', 'to': 'evtCard'}:
                    tgt[-1] = {'op': 'if', 'c': ph['c'], 'then': [{'op': 'summon', 'to': 'evtCard'}, {'op': 'pow', 'n': ph['n'], 'to': 'evt'}], 'else': [{'op': 'energy', 'to': 'evtCard'}]}
                    break
            else:
                return None
            break
    return out


def _perspec(sp):
    """「~N枚につき」의 앞부분 → 엔진이 세는 방법 (모르면 None)"""
    m = re.fullmatch(r'あなたの(?:フィールドにいる|フィールドの)?ユニットの色', sp)
    if m:
        return {'cnt': 'colorsField'}
    if sp == 'あなたのドロップゾーンの色':
        return {'cnt': 'colorsDrop'}
    if sp in ('ドロップしたカードの色', 'ドロップしたカードが持つ色'):
        return {'cnt': 'milledColors'}
    if sp in ('あなたのドロップゾーンにある称号', 'あなたのドロップゾーンの称号'):
        return {'cnt': 'dropTitles'}
    if sp in ('相手が公開したユニットカード',):
        return {'milled': 1, 'f': {'type': 'unit'}}
    m = re.fullmatch(r'(?P<w>あなた|相手)のドロップゾーンの「(?P<nm>[^」]+)」', sp)
    if m:
        return {'side': 'opp' if m.group('w') == '相手' else 'own', 'zone': 'drop', 'f': {'name': m.group('nm')}, 'notSrc': 1}
    m = re.fullmatch(r'あなたのドロップゾーンの(?P<d>.+?)カードの色', sp)
    if m and parse_desc(m.group('d')) is not None:
        return {'cnt': 'colorsDrop', 'f': parse_desc(m.group('d'))}
    m = re.fullmatch(r'(?P<w>あなた|相手)の(?P<z>ドロップゾーンの|エナジーゾーンの|手札の)?、?(?P<d>.*?)(?:の)?(?P<n>ユニット|エナジー|カード|エース)(?:合計)?', sp)
    if m:
        f = (parse_desc(m.group('d')) or parse_desc(m.group('d') + 'の')) if m.group('d') else {}
        if f is None:
            return None
        f = dict(f)
        f.pop('side', None)
        n = m.group('n')
        zone = {'ドロップゾーンの': 'drop', 'エナジーゾーンの': 'energy', '手札の': 'hand'}.get(m.group('z') or '', 'energy' if n == 'エナジー' else 'field')
        if n == 'エース':
            f['ace'] = 1
        if zone == 'field':
            f.setdefault('type', 'unit')
        return {'side': 'opp' if m.group('w') == '相手' else 'own', 'zone': zone, 'f': f}
    return None


def _resolve_repeat(seq):
    """「もう1回行う」「2回行う」「これを望む回数行う」: 앞 단계들을 다시"""
    def blk(st, before):
        b = [x for x in before if x.get('op') != '$repeat']
        if not b:
            return None
        if st.get('want'):
            out = []
            for _ in range(10):
                out.append({'op': 'confirm', 'text': '한 번 더 할까요?', 'alt': 1, 'no': [{'op': 'stop'}]})
                out += copy.deepcopy(b)
            return out
        k = st.get('n') or (st.get('total', 1) - 1)
        return sum((copy.deepcopy(b) for _ in range(k)), [])
    i = 0
    while i < len(seq):
        st = seq[i]
        if st.get('op') == '$repeat':
            b = blk(st, seq[:i])
            if b is None:
                return
            seq[i:i + 1] = b
            i += len(b)
            continue
        if st.get('op') == 'if':
            for br in ('then', 'else'):
                sq = st.get(br) or []
                for k2, x in enumerate(sq):
                    if x.get('op') == '$repeat':
                        b = blk(x, seq[:i])
                        if b is not None:
                            sq[k2:k2 + 1] = b
                        break
        i += 1


def _resolve_prev(seq, ctx):
    """'$prev'(앞의 수정 대상), '$prevop'(앞의 수정 종류)을 실제 값으로"""
    last = None
    for st in ctx:
        if st.get('op') in ('pow', 'hit', 'kw', 'dmg') and st.get('to') not in (None, '$prev'):
            last = st
    if last is None:   # 수정 단계가 없으면 앞에서 다룬 유닛 (例: 「このユニットをスタンドし、…さらにヒットを+1」)
        for st in ctx:
            if st.get('op') in ('stand', 'rest', 'tgt') and st.get('to') in ('self', 'T') or st.get('op') == 'tgt':
                last = {'op': 'pow', 'to': 'T' if st.get('op') == 'tgt' else st.get('to')}
            elif st.get('op') in ('summon', 'summonRested') and st.get('to') in ('card', 'self'):
                last = {'op': 'pow', 'to': 'self'}
            elif st.get('op') in ('summonFromTerr',):
                last = {'op': 'pow', 'to': 'summoned'}
    for st in seq:
        if st.get('op') == 'if':
            _resolve_prev(st.get('then', []), ctx + [x for x in seq if x is not st])
            _resolve_prev(st.get('else', []), ctx)
            continue
        if st.get('to') == '$prev':
            if not last:
                return False
            st['to'] = last['to']
            if st['op'] == '$prevop':
                st['op'] = last['op'] if last['op'] in ('pow', 'hit') else 'pow'
        if st.get('op') in ('pow', 'hit', 'kw', 'dmg'):
            last = st
    return True


_LEN = {'on': False}   # 못 읽은 부분을 '조건 묻기'·'처리 방법 고르기'로 바꿔서라도 자동 진행


def _infer_acts(frag):
    """못 읽은 효과 조각 -> [(표시 이름, 단계 목록)]: 글에 나온 동사로 그럴듯한 처리를 추려 사용자가 고르게"""
    acts = []
    fr = re.sub(r'\([^)]*\)', '', frag)
    mlook = re.search(r'山札を(?:上|下)から(\d+)枚(?:見|公開)', fr)
    if mlook:   # 덱 위 N장 보기 계열: 고른 카드를 어디로 보낼지
        k = int(mlook.group(1))
        rest = 'top' if re.search(r'残りを[^、。]*山札の上', fr) else 'drop' if re.search(r'残りを[^、。]*ドロップ', fr) else 'bottom'
        rk = {'top': '덱 맨 위', 'drop': '드롭 존', 'bottom': '덱 맨 아래'}[rest]
        if '手札に加え' in fr:
            acts.append((f'덱 위 {k}장을 보고 원하는 카드를 패에 넣기 (나머지 {rk})', [{'op': 'look', 'n': k, 'f': {}, 'k': k, 'to': 'hand', 'rest': rest}]))
        if '登場させ' in fr:
            acts.append((f'덱 위 {k}장을 보고 원하는 유닛을 등장시키기 (나머지 {rk})', [{'op': 'look', 'n': k, 'f': {'type': 'unit'}, 'k': k, 'to': 'field', 'rest': rest}]))
        if 'エナジー' in fr:
            acts.append((f'덱 위 {k}장을 보고 원하는 카드를 에너지로 (나머지 {rk})', [{'op': 'look', 'n': k, 'f': {}, 'k': k, 'to': 'energy', 'rest': rest}]))
        if 'ドロップ' in fr:
            acts.append((f'덱 위 {k}장을 보고 남길 카드를 고르기 (안 고른 카드는 드롭)', [{'op': 'look', 'n': k, 'f': {}, 'k': k, 'to': 'top', 'rest': 'drop'}]))
        if 'ライフ' in fr:
            acts.append((f'덱 위 1장을 라이프 맨 앞에', [{'op': 'lifeTop', 'n': 1}]))
        if not acts:
            acts.append((f'덱 위 {k}장을 보고 순서를 그대로 두기', [{'op': 'look', 'n': k, 'f': {}, 'k': 0, 'to': 'hand', 'rest': 'top'}]))
        return acts
    n = lambda rx, dflt=1: int(re.search(rx, fr).group(1)) if re.search(rx, fr) else dflt
    # 대상 묘사
    tg = None
    # 비용 조각 (「~ことで」): 내지 않으면 이후 효과 없음
    if re.search(r'ことで$', fr):
        cacts = []
        mm = re.search(r'手札[^、。]*?を(\d+)枚(?:ずつ)?ドロップ', fr)
        if mm:
            cacts.append((f'비용으로 패 {mm.group(1)}장 버리기', [{'op': 'discard', 'n': int(mm.group(1))}]))
        mm = re.search(r'エナジーを(\d+)枚裏に', fr)
        if mm:
            cacts.append((f'비용으로 에너지 {mm.group(1)}장 뒷면으로', [{'op': 'flipEnergy', 'n': int(mm.group(1))}]))
        mm = re.search(r'エナジーを(\d+)枚レスト', fr)
        if mm:
            cacts.append((f'비용으로 에너지 {mm.group(1)}장 레스트', [{'op': 'payEnergy', 'n': int(mm.group(1))}]))
        if re.search(r'テリトリーを閉じ', fr):
            cacts.append(('비용으로 내 테리토리 닫기', [{'op': 'closeTerr'}]))
        if re.search(r'このユニットをリムーブ', fr):
            cacts.append(('비용으로 이 유닛 리무브', [{'op': 'remove', 'to': 'self'}]))
        if re.search(r'このユニットをレスト', fr):
            cacts.append(('비용으로 이 유닛 레스트', [{'op': 'rest', 'to': 'self'}]))
        if re.search(r'ライフの先頭をドロップ', fr):
            cacts.append(('비용으로 내 라이프 맨 앞 드롭', [{'op': 'lifeDrop', 'n': 1}]))
        mm = re.search(r'山札を上から(\d+)枚(?:ドロップ|リムーブ)', fr)
        if mm:
            cacts.append((f'비용으로 덱 위 {mm.group(1)}장 {"리무브" if "リムーブ" in fr else "드롭"}', [{'op': 'mill', 'n': int(mm.group(1))}]))
        return [(a, b, 'cost') for a, b in cacts]
    m = re.search(r'(?P<d>[^、。]*?)(?P<noun>ユニットカード|ユニット|エースカード|エース|カード|⁅[^⁆]+⁆|ハート|スペード|ダイヤ|クラブ)(?:である)?(?P<en>のエナジー|エナジー)?を(?P<n>\d+)枚(?P<upto>まで)?対象と', fr)
    if m:
        dd = re.sub(r'^.*?(あなたの|相手の)', r'\1', m.group('d'))
        zone = 'energy' if m.group('en') or 'エナジー' in dd else 'drop' if 'ドロップゾーン' in dd else None
        dd2 = re.sub(r'^(あなたの|相手の)(?:ドロップゾーンの|エナジーゾーンの)?', r'\1', dd)
        f = parse_desc(dd2) or ({'side': 'opp'} if '相手の' in dd else {'side': 'own'} if 'あなたの' in dd else {})
        noun = m.group('noun')
        if noun.startswith('⁅') or noun in ('ハート', 'スペード', 'ダイヤ', 'クラブ'):
            f = dict(f, attr=[noun.strip('⁅⁆')]) if not noun.endswith('アイコン⁆') else f
            noun = 'カード'
        if zone:
            f = {k2: v for k2, v in f.items() if k2 != 'type'}
            f = noun_filter(f, noun) if noun != 'エナジー' else f
        tg = {'op': 'tgt', 'f': noun_filter(f, noun) if not zone else f, 'n': int(m.group('n')), 'upto': 1, **({'zone': zone} if zone else {})}
    elif 'このユニット' in fr and '対象' not in fr:
        tg = 'self'
    elif '対象' in fr or 'そのユニット' in fr:
        tg = 'T'
    else:
        tg = {'op': 'tgt', 'f': {'type': 'unit', **({'side': 'opp'} if '相手の' in fr else {'side': 'own'} if 'あなたの' in fr else {})}, 'n': 1, 'upto': 1}
    mall = re.search(r'(?P<d>[^。]*?)(?P<noun>ユニット|エース)全て(?:を|に|の)', fr)
    if mall and not (isinstance(tg, dict) and tg.get('op') == 'tgt' and m):
        dd = re.sub(r'^.*?(あなたの|相手の)、?', r'\1', mall.group('d')).replace('、', '')
        f = parse_desc(dd) if parse_desc(dd) is not None else ({'side': 'opp'} if '相手の' in dd else {'side': 'own'} if 'あなたの' in dd else {})
        tg = {'all': noun_filter(f, mall.group('noun'))}
    zn = {'energy': '에너지', 'drop': '드롭 존의 카드'}.get(tg.get('zone') if isinstance(tg, dict) else None, '유닛')
    side_ko = lambda f: '상대 ' if f.get('side') == 'opp' else '내 ' if f.get('side') == 'own' else ''
    who = '이 유닛' if tg == 'self' else '대상' if tg == 'T' else f"조건에 맞는 {side_ko(tg['all'])}유닛 전부" if 'all' in tg else f"{side_ko(tg.get('f', {}))}{zn} 1장" if tg['n'] == 1 else f"{side_ko(tg.get('f', {}))}{zn} {tg['n']}장까지"
    def unit(label, st):
        if tg == 'self':
            acts.append((f'{who}{label}', [dict(st, to='self')]))
        elif tg == 'T':
            acts.append((f'{who}{label}', [dict(st, to='T')]))
        elif 'all' in tg:
            acts.append((f'{who}{label.replace("하기", "")}{"하기" if label.endswith("하기") else ""}', [dict(st, to={'all': tg['all']})]))
        else:
            acts.append((f'{who}을 골라{label}', [dict(tg), dict(st, to='T')]))
    if re.search(r'手札に戻', fr) and not re.search(r'ドロップゾーン[^、。]*?手札に戻', fr):
        unit(' 패로 되돌리기', {'op': 'bounce'})
    if re.search(r'(?:ユニット|対象|それ|エース)[^、。]*?をドロップ(?:させ|する|し)|ドロップさせ', fr) and not re.search(r'手札を\d+枚ドロップ|ライフの先頭をドロップ|山札を上から', fr):
        unit(' 드롭시키기', {'op': 'drop'})
    m = re.search(r'(\d+)ダメージ', fr)
    if m:
        unit(f' {m.group(1)} 데미지 주기', {'op': 'dmg', 'n': int(m.group(1))})
    m = re.search(r'パワーを([+-]\d+)', fr)
    if m:
        unit(f' 파워 {m.group(1)} (이번 턴)', {'op': 'pow', 'n': int(m.group(1))})
    m = re.search(r'ヒットを([+-]\d+)', fr)
    if m:
        unit(f' 히트 {m.group(1)} (이번 턴)', {'op': 'hit', 'n': int(m.group(1))})
    if re.search(r'スタンド(?:する|させ|し|で)', fr) and 'スタンドで登場' not in fr:
        unit(' 스탠드하기', {'op': 'stand'})
    if re.search(r'をレスト(?:する|させ|し)', fr):
        unit(' 레스트하기', {'op': 'rest'})
    if re.search(r'山札の下に置', fr) and not re.search(r'残りを[^、。]*山札の下', fr):
        unit(' 덱 맨 아래에 놓기', {'op': 'deckBottom'})
    if re.search(r'山札の上に置', fr) and not re.search(r'残りを[^、。]*山札の上', fr):
        unit(' 덱 맨 위에 놓기', {'op': 'deckTop'})
    if re.search(r'(?:ユニット|対象|それ)[^、。]*?をエナジーゾーンに置', fr):
        unit(' 에너지 존에 놓기', {'op': 'energy'})
    if re.search(r'(?:ユニット|対象|それ)[^、。]*?をリムーブ', fr):
        unit(' 리무브하기', {'op': 'remove'})
    m = re.search(r'(\d+)枚引', fr)
    if m:
        acts.append((f'{m.group(1)}장 뽑기', [{'op': 'draw', 'n': int(m.group(1))}]))
    if re.search(r'手札[^。]*?登場させ', fr):
        acts.append(('패에서 유닛 1장 등장시키기', [{'op': 'pick', 'from': 'hand', 'to': 'field', 'f': {'type': 'unit'}, 'n': 1, 'upto': 1}]))
    if re.search(r'ドロップゾーン[^。]*?登場させ', fr):
        acts.append(('드롭 존에서 유닛 1장 등장시키기', [{'op': 'pick', 'from': 'drop', 'to': 'field', 'f': {'type': 'unit'}, 'n': 1, 'upto': 1}]))
    if re.search(r'エナジー[^。]*?登場させ', fr) and 'ドロップゾーン' not in fr:
        acts.append(('에너지에서 유닛 1장 등장시키기', [{'op': 'pick', 'from': 'energy', 'to': 'field', 'f': {'type': 'unit'}, 'n': 1, 'upto': 1}]))
    if re.search(r'ドロップゾーン[^。]*?手札に(?:加え|戻)', fr):
        acts.append(('드롭 존에서 카드 1장 패에 넣기', [{'op': 'pick', 'from': 'drop', 'to': 'hand', 'f': {}, 'n': 1, 'upto': 1}]))
    if re.search(r'山札[^。]*?(?:見|公開)[^。]*?手札に加え', fr):
        k = n(r'上から(\d+)枚', 3)
        acts.append((f'덱 위 {k}장을 보고 1장 패에 넣기 (나머지 덱 아래)', [{'op': 'look', 'n': k, 'f': {}, 'k': 1, 'to': 'hand', 'rest': 'bottom'}]))
    if re.search(r'ライフ[^。]*?手札に加え', fr):
        acts.append(('라이프 맨 앞 1장 패에 넣기', [{'op': 'lifeHand', 'n': 1}]))
    if re.search(r'手札を(\d+)枚ドロップ', fr):
        k = n(r'手札を(\d+)枚ドロップ')
        acts.append((f'패 {k}장 버리기', [{'op': 'discard', 'n': k}]))
    if re.search(r'山札を上から(\d+)枚ドロップ', fr):
        k = n(r'山札を上から(\d+)枚ドロップ')
        acts.append((f'덱 위 {k}장 드롭', [{'op': 'mill', 'n': k}]))
    if re.search(r'ライフの先頭をドロップ', fr):
        w = 'opp' if re.search(r'相手のライフ|相手は自身のライフ', fr) else 'me'
        acts.append(((('상대 ' if w == 'opp' else '내 ') + '라이프 맨 앞 드롭'), [{'op': 'lifeDrop', 'n': 1, **({'who': 'opp'} if w == 'opp' else {})}]))
    if re.search(r'上から(\d+)枚[^。]*?ライフ', fr):
        k = n(r'上から(\d+)枚')
        acts.append((f'덱 위 {k}장을 라이프 맨 앞에', [{'op': 'lifeTop', 'n': k}]))
    if re.search(r'上から(\d+)枚[^。]*?エナジー', fr):
        k = n(r'上から(\d+)枚')
        acts.append((f'덱 위 {k}장을 에너지로', [{'op': 'deckEnergy', 'n': k}]))
    if re.search(r'ライフの先頭をエナジー', fr):
        acts.append(('라이프 맨 앞을 에너지로', [{'op': 'lifeEnergy', 'n': 1}]))
    if re.search(r'(?:ユニット|対象|それ|カード)[^、。]*?をドロップゾーンに置', fr):
        unit(' 드롭 존에 놓기', {'op': 'drop'})
    if isinstance(tg, dict) and tg.get('zone') and re.search(r'登場させ', fr) and not any(l.endswith('등장시키기') for l, _ in acts):
        unit(' 등장시키기', {'op': 'summonRested' if 'レストで登場' in fr else 'summon'})
    if isinstance(tg, dict) and tg.get('zone') and re.search(r'手札に(?:加え|戻)', fr):
        unit(' 패에 넣기', {'op': 'bounce'})
    mm = re.search(r'手札の(?P<d>[^、。]*?)を(?P<n>\d+)枚公開', fr)
    if mm:
        acts.append((f'패에서 {mm.group("n")}장 공개하기', [{'op': 'revealHand', 'n': int(mm.group('n')), 'f': parse_desc(mm.group('d')) or {}}]))
    if re.search(r'テリトリーを閉じ', fr):
        acts.append(('내 테리토리 닫기', [{'op': 'closeTerr'}]))
    if re.search(r'追加の1ターンを行う', fr):
        acts.append(('추가 턴 진행', [{'op': 'extraTurn'}]))
    mm = re.search(r'手札が(\d+)枚になるように引', fr)
    if mm:
        acts.append((f'패가 {mm.group(1)}장이 되도록 뽑기', [{'op': 'drawTo', 'n': int(mm.group(1))}]))
    if re.search(r'山札をシャッフル', fr) and not re.search(r'上から\d+枚', fr):
        acts.append(('덱 섞기', [{'op': 'shuffle'}]))
    return acts


_CONDMARK = re.compile(r'(?:^|、)(?:(?P<c>(?:(?:あなたの|相手の)、)?(?:[^、。]*?いて、)?(?:[^、。]*?(?:⁅[^⁆]+⁆、)+)?[^、。]*?)(?:なら(?![なずば])|(?<!そうし)(?<=[しいっけえきせ])たら)、?|(?P<did>そうしたら)、)')


def _cond_split(seg):
    """조각 안의 첫 조건을 떼어 냄 -> (앞, 조건|None, 물어볼 조건문|None, 뒤) | None"""
    m = _CONDMARK.search(seg)
    if not m or not seg[m.end():].strip('、'):
        return None
    if m.group('did'):
        return seg[:m.start()], [{'did': 1}], None, seg[m.end():]
    c = m.group('c')
    if not c or re.search(r'対象と(?:し|する)$|ダメージを与え(?!てい)', c):
        return None
    ct = c + ('た' if re.search(r'たら、?$', m.group(0)) and re.search(r'[しいっけえきせ]$', c) else '')
    cc = parse_cond(ct)
    return seg[:m.start()], cc, (None if cc is not None else c), seg[m.end():]


def _guide(frag):
    """못 읽은 조각 -> 처리 방법을 고르는 단계 (추정할 처리가 없으면 None)"""
    acts = _infer_acts(frag)
    if not acts:
        return None
    if any(len(a) > 2 for a in acts):   # 비용: 안 내면 이후 효과 없음
        return {'op': 'choose', 'opts': [a[1] for a in acts] + [[{'op': 'stop'}]], 'labels': [a[0] for a in acts] + ['비용을 내지 않음 (효과 없음)'], 'guide': frag,
                'text': '이 능력의 비용을 자동으로 읽지 못했어요. 카드 문구대로 낼 비용을 고르세요'}
    labels = [a[0] for a in acts] + ['아무것도 하지 않음']
    return {'op': 'choose', 'opts': [a[1] for a in acts] + [[]], 'labels': labels, 'guide': frag,
            'text': '이 부분은 자동으로 읽지 못했어요. 카드 문구대로 처리할 방법을 고르세요'}


def _parse_seq(t, steps=None):
    """효과 문장 -> 단계 목록 | None (steps가 있으면 거기에 이어 붙임: '代わりに'가 앞 문장의 단계를 바꿀 수 있게)"""
    steps = [] if steps is None else steps
    t = t.strip()
    while t:
        t = t.lstrip('。、 ')
        if not t:
            break
        m = re.match(r'(?:そうしたら|つけたら|登場させたら|置いたら|戻したら|入れ替えたら|公開したら)、(?:その後、)?', t)
        if m:
            sub = []
            if _parse_seq(t[m.end():], sub) is None:
                return None
            steps.append({'op': 'if', 'c': [{'did': 1}], 'then': sub})
            break
        m = re.match(r'その後、|さらに(?![+-])|そのターン中、(?=(?:このユニット|対象|そのユニット)は、?(?:相手の)?コマンドの対象)', t)
        if m:
            t = t[m.end():]
            continue
        # 여러 턴 지속: 「次の相手ターンまで、」 등 → 파워·히트·키워드 단계에 기간 표시
        m = re.match(r'(?P<d>次の相手(?:の)?ターン(?:の)?(?:終了時)?まで|次の(?:あなたの)?ターン(?:の)?(?:開始時)?まで|次の相手(?:の)?ターン中|次のあなたのターン中)、', t)
        if m:
            j = t.find('。')
            inner, rest = (t[m.end():], '') if j < 0 else (t[m.end():j], t[j + 1:])
            sub = []
            if _parse_seq(inner, sub) is not None and sub and all(x.get('op') in ('pow', 'hit', 'kw') for x in sub):
                dd = m.group('d')
                dur = 'duringOpp' if dd.startswith('次の相手') and dd.endswith('中') else 'duringMy' if dd.endswith('中') else 'oppEnd' if dd.startswith('次の相手') else 'myNextStart'
                for x in sub:
                    x['dur'] = dur
                steps.extend(sub)
                t = rest
                continue
        m = re.match(r'『(?P<x>[^』]+)』を(?P<n>\d+)回行う(?:。|$)', t)
        if m:
            sub = parse_effects(m.group('x'))
            if sub is None:
                return None
            for _ in range(int(m.group('n'))):
                steps.extend(copy.deepcopy(sub))
            t = t[m.end():]
            continue
        m = re.match(r'(?:もう(?P<n>\d+)回|(?P<t>\d+)回|(?P<w>これを望む回数))行(?:う|ってよい)(?:。|$)', t)
        if m:
            steps.append({'op': '$repeat', **({'n': int(m.group('n'))} if m.group('n') else {'total': int(m.group('t'))} if m.group('t') else {'want': 1})})
            t = t[m.end():]
            continue
        # 일반 「(무엇)N枚/つ/種類につき、」
        m = re.match(r'(?P<sp>[^。]+?)(?P<k>\d+)(?:枚|つ|種類)につき、', t)
        if m and not re.match(r'(?:あなたの|相手の)(?:手札|エナジー|ドロップゾーン(?:のカード)?|ユニット|エナジーの色|リムーブゾーン|つけたログ)\d', t):
            per = _perspec(m.group('sp'))
            if per is not None:
                j = t.find('。')
                inner, rest = (t[m.end():], '') if j < 0 else (t[m.end():j], t[j + 1:])
                sub = []
                if _parse_seq(inner, sub) is not None and sub:
                    per['k'] = int(m.group('k'))
                    for st in sub:
                        if st.get('op') not in ('if', 'choose'):
                            st['per'] = dict(per)
                    steps.extend(sub)
                    t = rest
                    continue
        # 「~1枚につき、」: 다음 효과의 수치를 개수만큼 곱함
        m = re.match(r'(?P<w>あなたの|相手の)(?P<z>手札|エナジー|ドロップゾーン(?:のカード)?|ユニット|エナジーの色|リムーブゾーン|つけたログ)(?P<k>\d+)(?:枚|つ)につき、|対象のヒット(?P<h>\d+)につき、', t)
        if m:
            sub = []
            j = t.find('。')
            inner, rest = (t[m.end():], '') if j < 0 else (t[m.end():j], t[j + 1:])
            if _parse_seq(inner, sub) is None:
                m = None
        if m:
            sub2 = sub
            j = t.find('。')
            rest = '' if j < 0 else t[j + 1:]
            sub = sub2
            per = {'tHit': 1} if m.group('h') else {'side': 'opp' if m.group('w') == '相手の' else 'own', 'zone': {'手札': 'hand', 'エナジー': 'energy', 'ユニット': 'field', 'エナジーの色': 'colors', 'リムーブゾーン': 'remove', 'つけたログ': 'log'}.get(m.group('z'), 'drop'), 'k': int(m.group('k'))}
            for st in sub:
                if st.get('op') not in ('tgt', 'if', 'choose'):
                    st['per'] = per
            steps.extend(sub)
            t = rest
            continue
        # 둘 중 하나의 비용: 「あなたの、AするかBすることで、」
        m = re.match(r'(?:あなたの、?)?(?P<a>[^。、]+?(?:する|置く|戻す))か(?P<b>[^。、]+?)ことで、', t)
        if m:
            ca = parse_cost('あなたの' + re.sub(r'^あなたの', '', m.group('a')), _SKILL.get('s'))
            cb = parse_cost('あなたの' + re.sub(r'^あなたの', '', m.group('b')), _SKILL.get('s'))
            if ca and cb:
                steps.append({'op': 'choose', 'opts': [ca, cb, [{'op': 'stop'}]], 'labels': [_cost_label(ca), _cost_label(cb), '쓰지 않는다'], 'text': '어떤 비용을 낼까요?'})
                t = t[m.end():]
                continue
        # 비용을 내면 이어서: 「(비용)ことで、」
        m = re.match(r'(?P<c>[^。、]*(?:、[^。、]*)?)ことで、', t)
        if m:
            cost = parse_cost(m.group('c'), _SKILL.get('s'))
            if cost:
                steps.append({'op': 'confirm', 'text': '비용을 내고 효과를 쓸까요?', 'cost': 1, 'need': cost})
                steps.extend(cost)
                t = t[m.end():]
                continue
        # 조건 분기: 「Xなら、」
        m = re.match(r'(?P<c>[^。]*?)(?:なら|ならば|場合|(?<!そうし)たら)、', t)
        if m and not re.search(r'対象と(?:し|する)|ダメージを与え(?!てい)|\d+ダメージ|を\d+枚(?!以上|以下)', m.group('c')):
            ctext = m.group('c') + ('た' if m.group(0).endswith('たら、') and re.search(r'[しいっけえきせ]$', m.group('c')) else '')
            c = parse_cond(ctext)
            ask = False   # 조건을 못 읽으면 묻지 않고 이 문장은 못 읽은 것으로 둠
            if c is None and _LEN['on']:
                _FAIL['cond'] = m.group('c')
            if c is not None:
                rest = re.sub(r'^その後、', '', t[m.end():])
                # 같은 문장 끝(。)까지를 조건 안쪽으로
                j = rest.find('。')
                inner, t = (rest, '') if j < 0 else (rest[:j], rest[j + 1:])
                mrep = re.fullmatch(r'手札に加える代わりに(?P<r>レストで)?登場させてよい', inner)
                if mrep and not ask and steps and steps[-1].get('op') in ('look', 'pick') and steps[-1].get('to') == 'hand':
                    prev = steps.pop()
                    alt2 = dict(prev, to='field', **({'rested': 1} if mrep.group('r') else {}))
                    steps.append({'op': 'if', 'c': c, 'then': [{'op': 'confirm', 'text': '패에 넣는 대신 등장시킬까요?', 'alt': 1, 'no': [prev]}, alt2], 'else': [prev]})
                    continue
                alt = inner.startswith('代わりに')
                mel = re.search(r'、(?:違う|それ以外|[^、。]*でない)なら、?', inner) if not alt else None
                els = None
                if mel:
                    els = parse_effects(inner[mel.end():])
                    if els is not None:
                        inner = inner[:mel.start()]
                ma = re.fullmatch(r'(?P<r>レストで)?登場させてよい', inner[4:]) if alt else None
                sub = [{'op': '$altSummon', **({'rested': 1} if ma.group('r') else {})}] if ma else parse_effects(inner[4:] if alt else inner)
                if sub is None:
                    return None
                if len(sub) == 1 and sub[0].get('op') in ('$altSummon', '$altN') and steps:
                    prev = steps.pop()
                    ph = sub[0]
                    new2 = copy.deepcopy(prev)
                    if ph['op'] == '$altSummon':
                        if new2.get('op') in ('bounce',):
                            new2['op'] = 'summonRested' if ph.get('rested') else 'summon'
                        elif new2.get('op') in ('pick', 'look'):
                            new2['to'] = 'field'
                            if ph.get('rested'):
                                new2['rested'] = 1
                        else:
                            return None
                        then = [{'op': 'confirm', 'text': '대신 등장시킬까요?', 'alt': 1, 'no': [prev]}, new2]
                    else:
                        if new2.get('n') != ph['a']:
                            return None
                        new2['n'] = ph['b']
                        then = [new2]
                    steps.append({'op': 'if', 'c': c, 'then': then, 'else': [prev]})
                    continue
                _resolve_prev(sub, steps)
                if els is not None and not alt:
                    steps.append({'op': 'if', 'c': c, 'then': sub, 'else': els})
                    continue
                if alt:
                    if not steps:
                        return None
                    prev = steps.pop()
                    steps.append({'op': 'if', 'c': c, 'then': sub, 'else': [prev]})
                else:
                    steps.append({'op': 'if', 'c': c, 'then': sub})
                continue
        if t.startswith('その中') and steps and steps[-1].get('op') == 'if' and steps[-1].get('then') and steps[-1]['then'][-1].get('op') == 'look' and steps[-1]['then'][-1].get('k') == 0 and not steps[-1].get('else'):
            j = t.find('。')
            seg = t if j < 0 else t[:j]
            prev = steps[-1]['then'][-1]
            r = parse_effects(f'あなたの山札を上から{prev["n"]}枚見て、' + seg)
            if r and r[0].get('op') == 'look':
                if prev.get('per'):
                    r[0]['per'] = prev['per']
                steps[-1]['then'][-1:] = r
                t = '' if j < 0 else t[j + 1:]
                continue
        if t.startswith('その中') and steps and steps[-1].get('op') == 'look' and steps[-1].get('k') == 0:
            j = t.find('。')
            seg = t if j < 0 else t[:j]
            prev = steps[-1]
            r = parse_effects(f'あなたの山札を上から{prev["n"]}枚見て、' + seg)
            if r and r[0].get('op') == 'look':
                if prev.get('per'):
                    r[0]['per'] = prev['per']
                steps[-1:] = r
                t = '' if j < 0 else t[j + 1:]
                continue
        for rx, fn in EFF:
            m = rx.match(t)
            if m:
                r = fn(m)
                if r and isinstance(r, dict) and r.get('op') == '_attach':
                    if not steps:
                        continue
                    steps[-1].update({k: v for k, v in r.items() if k != 'op'})
                    t = t[m.end():]
                    break
                if r:
                    r = r if isinstance(r, list) else [r]
                    _resolve_prev(r, steps)   # 못 찾으면 바깥 문맥에서 다시
                    steps.extend(r)
                    t = t[m.end():]
                    break
        else:
            _FAIL['at'] = t
            if not _LEN['on']:
                return None
            # 못 읽은 조각: 뒤쪽에서 읽을 수 있는 곳까지만 잘라 '처리 방법 고르기'로
            j = t.find('。')
            seg = t if j < 0 else t[:j]
            cut = None
            for k in [i for i, ch in enumerate(seg) if ch == '、']:
                _LEN['on'] = False
                ok = _parse_seq(seg[k + 1:], []) is not None
                _LEN['on'] = True
                if ok:
                    cut = k
                    break
            frag = seg if cut is None else seg[:cut]
            # 고르기 전에 조각 안의 조건을 떼어 냄: 판단할 수 있으면 게임이 확인, 아니면 물어봄
            cs = _cond_split(seg)
            if cs:
                pre, cc, ask_c, post = cs
                if ask_c:
                    _FAIL['cond'] = ask_c
                    return None
                pre_steps = _parse_seq(pre, []) if pre.strip('、') else []
                mel = re.search(r'、(?:違う|それ以外|[^、。]*でない)なら、?', post)
                else_steps = None
                if mel:
                    else_steps = _parse_seq(post[mel.end():], [])
                    if else_steps is not None:
                        post = post[:mel.start()]
                post_steps = _parse_seq(post, []) if post.strip('、') else []
                if pre_steps is not None and post_steps:
                    steps.extend(pre_steps)
                    node = {'op': 'if', 'c': cc, 'then': post_steps}
                    if else_steps:
                        node['else'] = else_steps
                    steps.append(node)
                    t = t[len(seg):]
                    continue
            g = _guide(frag)
            if g is None and cut is not None:
                frag = seg
                g = _guide(frag)
            if g is None:
                return None
            if _MAY.search(frag):
                g['labels'][-1] = '쓰지 않음'
            steps.append(g)
            t = t[len(frag):]
    return steps


# ---------- 발동 시점 ----------
TRIGGERS = [
    (r'このユニットが手札から登場した時', ('enter', 'self', {'fromHand': 1})),
    (r'相手がコマンドをプレイした時', ('cmdResolved', 'opp', None)),
    (r'相手が手札をドロップした時', ('handDrop', 'opp', None)),
    (r'あなたが自分のターンに効果で手札をドロップした時', ('handDrop', 'me', {'myTurn': 1})),
    (r'あなたのエナジーが表から裏になった時', ('eFlip', 'me', None)),
    (r'このカードが【ブライト】でドロップされた時', ('brightDrop', 'self', None)),
    (r'あなたの効果でカードがリムーブされた時', ('removedAny', 'me', None)),
    (r'このユニットがフィールドから手札に戻った時', ('bounced', 'self', None)),
    (r'このユニットが(?:登場した|登場)時|このユニットの登場時', ('enter', 'self', None)),
    (r'このユニットがフィールドからドロップした時', ('leave', 'self', None)),
    (r'このユニットがアタックしてバトルに勝利した時', ('win', 'self', None)),
    (r'このユニットが(?:アタックした|アタック)時|このユニットのアタック時', ('attack', 'self', None)),
    (r'このユニットがバトルする時', ('battle', 'self', None)),
    (r'このユニットがバトルに勝利した時', ('win', 'self', {'any': 1})),
    (r'あなたのユニットがアタックしてバトルに勝利した時', ('win', 'own', None)),
    (r'あなたのエースがアタックした時', ('attack', 'ownAce', None)),
    (r'あなたのユニットがアタックした時', ('attack', 'own', None)),
    (r'あなたのユニットが登場した時', ('enter', 'own', None)),
    (r'あなたのユニットがフィールドからドロップした時', ('leave', 'own', None)),
    (r'相手のユニットが登場した時', ('enter', 'opp', None)),
    (r'相手のユニットがフィールドからドロップした時', ('leave', 'opp', None)),
    (r'あなたのターン開始時', ('turnStart', 'me', None)),
    (r'あなたのメインフェイズ開始時', ('mainStart', 'me', None)),
    (r'あなたのアタックフェイズ開始時', ('attackStart', 'me', None)),
    (r'あなたのエンドフェイズ開始時', ('endStart', 'me', None)),
    (r'相手のターン開始時', ('turnStart', 'opp', None)),
    (r'相手のアタックフェイズ開始時', ('attackStart', 'opp', None)),
    (r'相手のエンドフェイズ開始時', ('endStart', 'opp', None)),
    (r'このテリトリーが開放された時', ('terrOpen', 'me', None)),
    (r'このユニットが卒業した時', ('graduate', 'self', None)),
    (r'このユニットが【ブライト】して卒業した時', ('graduate', 'self', {'evBrighted': 1})),
    (r'このユニットがアタックしたアタック終了時', ('attackEnd', 'self', None)),
    (r'あなたのユニットが【ブライト】した時', ('bright', 'own', None)),
    (r'このユニットが【コスプレ】で登場した時', ('enter', 'self', {'cos': 1})),
    (r'あなたの他のユニットが【コスプレ】で登場した時', ('enter', 'own', {'cos': 1, 'evNotSelf': 1})),
    (r'あなたのユニットが【コスプレ】で登場した時', ('enter', 'own', {'cos': 1})),
    (r'エンドフェイズ以外にあなたのユニットが【コスプレ】で登場した時', ('enter', 'own', {'cos': 1, 'notEnd': 1})),
    (r'このユニットが【コスプレ】で手札に戻った時', ('cosReturn', 'self', None)),
    (r'このユニットにクラスカードがついた時', ('classAttach', 'self', None)),
    (r'このユニットがレストで登場した時', ('enter', 'self', {'enteredRested': 1})),
    (r'このユニットでテリトリーを開放した時', ('terrOpen', 'self', None)),
    (r'このユニットが効果で登場した時', ('enter', 'self', {'notPlayed': 1})),
    (r'このユニットがエナジーゾーンから登場した時', ('enter', 'self', {'fromEnergy': 1})),
    (r'このカードを【ブライト】でドロップした時|このカードが【ブライト】で手札からドロップされた時', ('brightDrop', 'self', None)),
    (r'あなたのエースがフィールドからドロップした時', ('leave', 'ownAce', None)),
    (r'このユニットがフィールドからドロップされた時', ('leave', 'self', None)),
    (r'このカードがフィールドからリムーブされた時', ('removed', 'self', None)),
    (r'あなたのユニットが卒業した時', ('graduate', 'own', None)),
    (r'このユニットがブロックした時', ('block', 'self', None)),
    (r'あなたの他のユニットがブロックしてバトルする時', ('block', 'own', {'evNotSelf': 1})),
    (r'このユニットが【(?P<n>[^】]+)】を着た時', ('dressed', 'self', None)),
    (r'このユニットが【ブライト】してバトルに勝利した時', ('win', 'self', {'brightWin': 1})),
    (r'このユニットが相手ターンにバトルする時', ('battle', 'self', {'oppTurnX': 1})),
    (r'ダメージでこのカードがライフからドロップした時', ('lifeDmgDrop', 'self', None)),
    (r'あなたのユニットがバトルする時', ('battle', 'own', None)),
    (r'あなたのユニットがアタックしたターンのエンドフェイズ開始時', ('endStart', 'me', {'attackedTurn': 1})),
    (r'このカードがどこからでもリムーブされた時', ('removed', 'self', None)),
    (r'(?:あなたのターンに)?あなたがカードをフィールドに伏せた時', ('setCard', 'me', None)),
    (r'フィールドに伏せられたこのカードがドロップされた時', ('setDrop', 'self', None)),
    (r'あなたのエースが【マギア】でエナジーを裏にした時', ('magiaFlip', 'ownAce', None)),
    (r'このカードを【夢を見ない】で公開してドロップした時', ('yumemiDrop', 'self', None)),
    (r'このユニットの【CAD】でコマンドを解決した時', ('cad', 'self', None)),
    (r'あなたが【CAD】でコマンドを解決した時', ('cad', 'own', None)),
    (r'(?:あなたのターンに)?あなたがコマンドを解決した時', ('cmdResolved', 'me', None)),
    (r'相手が効果でカードを引いた時', ('effDraw', 'opp', None)),
    (r'あなたのユニットにクラスカードがついた時', ('classAttach', 'own', None)),
    (r'(?:あなたが)?スキルコストで、?手札かライフ(?:の|から)このカードをドロップした時', ('skillDrop', 'self', None)),
    (r'(?:あなたのターン中、)?あなたのユニットが【スキル】を発動した時', ('skillUsed', 'own', None)),
    (r'このユニットがレストした時', ('rest', 'self', None)),
    (r'ユニットにつけたこのカードがドロップした時', ('attDrop', 'self', None)),
    (r'(?P<w>あなた|相手)の(?P<d>[^、。]*?)ユニットがアタックした時', ('attack', 'desc', None)),
    (r'(?P<w>あなた|相手)の(?P<d>[^、。]+?)ユニットが(?:フィールドから)?ドロップした時', ('leave', 'desc', None)),
    (r'(?P<w>あなた|相手)の(?P<d>[^、。]+?)ユニットが登場した時', ('enter', 'desc', None)),
    (r'このユニットが【ブライト】した時', ('bright', 'self', None)),
    (r'このユニットが総コスト(?P<n>\d+)以下のユニットとバトルする時', ('battle', 'self', 'vsCostLE')),
    (r'このユニットが(?P<d>[^、。]+?)ユニットとバトルする時', ('battle', 'self', 'vsDesc')),
    (r'(?P<d>[^、。]+?)ユニットとバトルする時', ('battle', 'self', 'vsDesc')),
    (r'バトル中のこのユニットがフィールドからドロップした時|このユニットがバトル中にフィールドからドロップした時', ('leave', 'self', {'inBattle': 1})),
    (r'このユニットのアタック終了時', ('attackEnd', 'self', None)),
    (r'いずれかのアタックフェイズに相手のユニットが登場した時', ('enter', 'opp', {'attackPhase': 1})),
]


_EXACT_TRIG = [
    (r'あなたのバトル中のユニットがフィールドからドロップした時', 'leave', 'own', [{'evInBattle': 1}]),
    (r'このユニットがバトルでドロップした時', 'leave', 'self', [{'evInBattle': 1}]),
    (r'このユニットが(?:エースか⁅(?:バスターアイコン|B)⁆|エースか⁅B⁆の)(?:の)?(?:ユニット)?とバトルする時', 'battle', 'self', [{'vsF': {'aceOrBuster': 1}}]),
    (r'あなたの【ブライト】を持つユニットがアタックしてバトルに勝利した時', 'win', 'own', [{'evF': {'bright': 1}}]),
    (r'あなたの称号「(?P<t>[^」]+)」のエースがアタックしてバトルに勝利した時', 'win', 'own', 'T_ACE'),
    (r'あなたの他のユニットがバトルする時', 'battle', 'own', [{'evNotSelf': 1}]),
    (r'クラスカードのついたこのユニットがフィールドからドロップした時', 'leave', 'self', [{'selfHadClass': 1}]),
    (r'(?:クラスカードがついた)このユニット(?:のアタック時|がアタックした時)', 'attack', 'self', [{'selfHasClass': 1}]),
    (r'あなたのエースがアタックしたターンのエンドフェイズ開始時', 'endStart', 'me', [{'hist': {'scope': 'turn', 'k': 'atk', 'side': 'own', 'f': {'ace': 1}}}]),
    (r'あなたのエンドフェイズ開始時', 'endStart', 'me', []),
    (r'このユニットがドロップゾーンから登場した時', 'enter', 'self', [{'fromZone': 'drop'}]),
    (r'このユニットが手札以外から登場した時', 'enter', 'self', [{'fromZone': 'notHand'}]),
    (r'このユニットがアタックしてバトルする時', 'battle', 'self', [{'selfAttacking': 1}]),
    (r'このユニットが【(?P<a>[^】]+)】か【(?P<b>[^】]+)】を持つユニットとバトルする時', 'battle', 'self', 'VS_KW2'),
    (r'このユニットが⁅?(?P<at>スペード|ハート|ダイヤ|クラブ)⁆?とバトルする時', 'battle', 'self', 'VS_ATTR'),
    (r'このユニットの【ブライト】で(?P<d>[^、。]+?)をドロップした時', 'bright', 'self', 'BRIGHT_F'),
]


def _exact_trigger(h):
    """조건이 붙은 발동 시점을 정확한 조건으로 (가능하면)"""
    for rx, on, src, cs in _EXACT_TRIG:
        m = re.fullmatch(rx, h)
        if not m:
            continue
        if cs == 'T_ACE':
            cs = [{'evF': {'title': m.group('t'), 'ace': 1}}]
        elif cs == 'VS_KW2':
            KM = {'デコイ': 'decoy', 'ブリッツ': 'blitz', 'バーサーク': 'berserk'}
            fs = [({'bright': 1} if k == 'ブライト' else {'kw': KM[k]} if k in KM else {'kwText': k}) for k in (m.group('a'), m.group('b'))]
            cs = [{'vsAny': fs}]
        elif cs == 'VS_ATTR':
            cs = [{'vsF': {'attr': [m.group('at')]}}]
        elif cs == 'BRIGHT_F':
            f = _zdesc(m.group('d'))
            if f is None:
                return None
            cs = [{'brightDropF': f}]
        return on, src, list(cs)
    return None


def _approx_trigger(h):
    """정확히 못 읽은 발동 시점 -> 가장 가까운 시점 (on, src, conds) — 실제로 해당하는지는 그때 플레이어에게 물음"""
    conds = []
    h = re.sub(r'」テリトリー', '」のテリトリー', h)
    m = re.match(r'あなたの(?:称号「(?P<ti>[^」]+)」の)?テリトリー(?:が開放されていて|開放中で|が開放中で|開放中に|が開放中に|開放中の|開放中)、?', h)
    if m:
        conds.append({'terrTitle': m.group('ti')} if m.group('ti') else {'terr': 1})
        h = h[m.end():]
        tr = parse_trigger(h)
        if tr:
            return tr[0], tr[1], conds + tr[2], False
    ex = _exact_trigger(h)
    if ex:
        return ex[0], ex[1], conds + ex[2], False
    side = 'self' if re.search(r'このユニット|このカード', h) else 'own' if h.startswith('あなた') else 'opp' if h.startswith('相手') else None
    who = 'opp' if h.startswith('相手') else 'me'
    fam = None
    if 'エンドフェイズ開始時' in h:
        fam = ('endStart', who)
    elif 'アタックフェイズ開始時' in h:
        fam = ('attackStart', who)
    elif 'メインフェイズ開始時' in h:
        fam = ('mainStart', who)
    elif 'ターン開始時' in h:
        fam = ('turnStart', who)
    elif side and 'バトルに勝利した時' in h:
        fam = ('win', side)
    elif side and 'バトルに負けた時' in h:
        fam = ('lose', side)
    elif side and re.search(r'バトルする時', h):
        fam = ('battle', side)
    elif side and re.search(r'ユニット[^、。]*?ドロップ(?:した|された)時|ユニットがバトルでドロップした時', h) and '手札' not in h:
        fam = ('leave', side)
    elif side and re.search(r'登場(?:した)?時', h):
        fam = ('enter', side)
    elif side and re.search(r'ブロックした時', h):
        fam = ('block', side)
    elif side and re.search(r'【ブライト】した時', h):
        fam = ('bright', side)
    elif side and re.search(r'アタック(?:した)?時', h):
        fam = ('attack', side)
    if not fam:
        return None
    return fam[0], fam[1], conds, True


def parse_trigger(t):
    """'あなたのテリトリー開放中にこのユニットが登場した時' -> (on, src, conds) | None"""
    conds = []
    t = re.sub(r'」テリトリー', '」のテリトリー', t)
    if t.startswith('あなたのターンに'):
        conds.append({'myTurn': 1})
        t = t[len('あなたのターンに'):]
    mst = re.match(r'このカードと共通の称号を持つあなたのテリトリー開放中に、?', t)
    if mst:
        conds.append({'terrShareTitle': 1})
        t = t[mst.end():]
    m = re.match(r'(?P<c>あなたの、称号「[^」]+」か(?:称号)?「[^」]+」のテリトリー開放中|あなたの(?:称号「[^」]+」の)?テリトリー(?:開放中|が開放されていて)|あなたのライフがレッドゾーンで)(?:に|、|で、|で)?', t)
    if m:
        c = parse_cond(m.group('c').replace('が開放されていて', '開放中').rstrip('で'))
        if c is None:
            return None
        conds += c
        t = t[m.end():]
    mx = re.fullmatch(r'このカードが「(?P<n>[^」]+)」の効果で山札からドロップした時', t)
    if mx:
        return 'milledCard', 'self', conds + [{'evSrcName': mx.group('n')}], None
    mx = re.fullmatch(r'このカードが称号「(?P<n>[^」]+)」のテリトリーの効果でドロップされた時', t)
    if mx:
        return 'milledCard', 'self', conds + [{'evSrcTerrTitle': mx.group('n')}], None
    mx = re.fullmatch(r'あなたの山札から(?P<d>[^、。]+?)がドロップした時', t)
    if mx and _zdesc(mx.group('d')) is not None:
        return 'milledCard', 'own', conds + [{'evF': _zdesc(mx.group('d'))}], None
    mx = re.fullmatch(r'(?P<o>相手のターンに)?このカードを手札からドロップした時', t)
    if mx:
        return 'discarded', 'self', conds + ([{'oppTurn': 1}] if mx.group('o') else []), None
    mx = re.fullmatch(r'あなたの(?P<d>[^、。]+?)がバトルでドロップした時', t)
    if mx and _zdesc(mx.group('d')) is not None:
        return 'leave', 'own', conds + [{'evF': _zdesc(mx.group('d'))}, {'evInBattle': 1}], None
    if t == 'あなたのユニットがアタックしたターンのエンドフェイズ開始時':
        return 'endStart', 'me', conds + [{'attackedTurn': 1}], None
    if t == 'あなたのカードがドロップした時':
        return 'anyDrop', 'me', conds, None
    mx = re.fullmatch(r'あなたの(?P<d>[^、。]+?)ユニットのアタック終了時', t)
    if mx and parse_desc(mx.group('d')) is not None:
        return 'attackEnd', 'own', conds + [{'evF': parse_desc(mx.group('d'))}], None
    if t == 'このユニットがブロックされたバトル終了時':
        return 'blockedEnd', 'self', conds, None
    mx = re.fullmatch(r'(?P<d>[^、。]*?)ユニットが登場した時', t)
    if mx and mx.group('d') and not re.match(r'(?:あなた|相手|この|他)', mx.group('d')) and parse_desc(mx.group('d')) is not None:
        return 'enter', 'any', conds + [{'evF': parse_desc(mx.group('d'))}], None
    mw = re.match(r'、?((?:【[^】]+】か?)+)を着ている(?=このユニット)', t)
    if mw:
        conds.append({'wearing': re.findall(r'【([^】]+)】', mw.group(1))})
        t = t[mw.end():]
    for rx, (on, src, extra) in TRIGGERS:
        m = re.fullmatch(rx, t)
        if m:
            if extra == 'vsCostLE':
                conds.append({'vsCostLE': int(m.group('n'))})
                extra = None
            if extra == 'vsDesc':
                f = parse_desc(m.group('d'))
                if f is None:
                    continue
                conds.append({'vsF': f})
                extra = None
            if extra and 'inBattle' in extra:
                conds.append(extra)
                extra = None
            if src == 'desc':
                f = parse_desc(m.group('d'))
                if f is None:
                    continue
                src = 'own' if m.group('w') == 'あなた' else 'opp'
                conds.append({'evF': f})
            if extra and 'brightWin' in extra:
                conds.append({'selfBrighted': 1})
                extra = {'any': 1}
            if extra and 'myTurn' in extra:
                conds.append(extra)
                extra = None
            if extra and 'oppTurnX' in extra:
                conds.append({'oppTurn': 1})
                extra = None
            if extra and ('notPlayed' in extra or 'fromEnergy' in extra or 'evNotSelf' in extra):
                conds.append(extra)
                extra = None
            if extra and ('enteredRested' in extra or 'attackedTurn' in extra):
                conds.append(extra)
                extra = None
            if extra and 'cos' in extra:
                conds.append(extra)
                extra = None
            elif extra and 'evBrighted' in extra:
                conds.append(extra)
                extra = None
            elif extra and ('fromHand' in extra or 'attackPhase' in extra):
                conds.append(extra)
            return on, src, conds, extra
    return None


# ---------- 비용 (ことで) ----------
_SKILL = {}


def parse_cost(t, skill):
    C = [
        (r'【スキル】(?:を)?発動(?:する|すること)?', lambda m: skill),
        (r'あなたのライフの先頭をドロップする', lambda m: [{'op': 'lifeDrop', 'n': 1}]),
        (r'そのアタックしたユニットを山札の下に置く', lambda m: [{'op': 'deckBottom', 'to': 'evt'}]),
        (r'あなたのレストしているエナジーから、(?P<l>(?:[黒青白赤]\d+枚、?)+)をスタンドする', lambda m: [{'op': 'standEnergyColors', 'colors': {{'赤': 'red', '青': 'blue', '白': 'white', '黒': 'black'}[c]: int(n) for c, n in re.findall(r'([黒青白赤])(\d+)枚', m.group('l'))}}]),
        (r'レストしているこのユニットをテリトリーゾーンに置く', lambda m: [{'op': 'toTerrZone'}]),
        (r'あなたの「(?P<nm>[^」]+)」を含むユニットを(?P<n>\d+)枚山札の下に置く', lambda m: [{'op': 'tgt', 'f': {'side': 'own', 'type': 'unit', 'name': m.group('nm')}, 'n': int(m.group('n')), 'upto': 0}, {'op': 'deckBottom', 'to': 'T'}]),
        (r'あなたのエナジー(?:の中)?から、(?P<l>(?:[黒青白赤]\d+枚、?)+)(?:を)?(?P<h>レスト|ドロップ)する', lambda m: [{'op': 'payEnergyMulti', 'colors': {{'赤': 'red', '青': 'blue', '白': 'white', '黒': 'black'}[c]: int(n) for c, n in re.findall(r'([黒青白赤])(\d+)枚', m.group('l'))}, 'how': 'rest' if m.group('h') == 'レスト' else 'drop'}]),
        (r'あなたの(?P<c>赤|青|白|黒)のエナジー(?:を)?(?P<n>\d+)枚(?:を)?ドロップする', lambda m: [{'op': 'payEnergy', 'n': int(m.group('n')), 'color': {'赤': 'red', '青': 'blue', '白': 'white', '黒': 'black'}[m.group('c')], 'how': 'drop'}]),
        (r'あなたの白と赤のエナジーをそれぞれ1枚ずつドロップ(?:する|してよい)', lambda m: [{'op': 'payEnergyMulti', 'colors': {'white': 1, 'red': 1}, 'how': 'drop'}]),
        (r'あなたの、?(?P<d>[^。]*?)のエナジーを(?:合計)?(?P<n>\d+)枚レストする', 'edesc'),
        (r'あなたのドロップゾーンのクラスカードを(?P<n>\d+)枚取り除く', lambda m: [{'op': 'classRemove', 'n': int(m.group('n'))}]),
        (r'このユニットをドロップさせる', lambda m: [{'op': 'drop', 'to': 'self'}]),
        (r'次のエンドフェイズ開始時、(?:これ|このユニット)をドロップさせる', lambda m: [{'op': 'delay', 'at': 'endStart', 'do': [{'op': 'drop', 'to': 'self'}]}]),
        (r'あなたの(?P<c>赤|青|白|黒)?の?エナジーを(?P<n>\d+)枚レストする', lambda m: [{'op': 'payEnergy', 'n': int(m.group('n')), **({'color': {'赤': 'red', '青': 'blue', '白': 'white', '黒': 'black'}[m.group('c')]} if m.group('c') else {})}]),
        (r'あなたの手札を(?P<n>\d+)枚ドロップする', lambda m: [{'op': 'discard', 'n': int(m.group('n'))}]),
        (r'あなたの手札の(?P<d>[^。]*?)' + NOUN + r'?を(?P<n>\d+)枚ドロップする', 'desc'),
        (r'あなたの⁅(?P<a>ハート|スペード|ダイヤ|クラブ)⁆のエナジーを(?P<n>\d+)枚レストする', lambda m: [{'op': 'payEnergy', 'n': int(m.group('n')), 'attr': m.group('a')}]),
        (r'あなたのエナジーを(?P<n>\d+)枚レストする', lambda m: [{'op': 'payEnergy', 'n': int(m.group('n'))}]),
        (r'このユニットをレストする', lambda m: [{'op': 'rest', 'to': 'self'}]),
        (r'あなたのエナジーを(?P<n>\d+)枚裏にする', lambda m: [{'op': 'flipEnergy', 'n': int(m.group('n'))}]),
        (r'(?:あなたは自身の|あなたの|この)テリトリーを閉じる', lambda m: [{'op': 'closeTerr'}]),
        (r'あなたのライフの先頭を(?P<n>\d+)枚ドロップする', lambda m: [{'op': 'lifeDrop', 'n': int(m.group('n'))}]),
        (r'あなたの手札の(?P<d>[^。]*?)を(?P<n>\d+)枚(?P<v>リムーブ|公開)する', lambda m: (lambda f: f is not None and [{'op': 'pick', 'from': 'hand', 'to': 'remove', 'f': f, 'n': int(m.group('n')), 'upto': 0}] if m.group('v') == 'リムーブ' else [{'op': 'revealHand', 'n': int(m.group('n')), 'f': f}])(_zdesc(m.group('d')))),
        (r'あなたの手札の(?P<d>[^。]+?)を(?P<n>\d+)枚ドロップする', lambda m: (lambda f: f is not None and [{'op': 'discard', 'n': int(m.group('n')), 'f': f}])(_zdesc(m.group('d')))),
        (r'あなたの(?P<d>[^。]*?)ユニット(?P<n>\d+)枚をドロップする|あなたの(?P<d2>[^。]*?)ユニットを(?P<n2>\d+)枚ドロップする', lambda m: (lambda f, n: f is not None and [{'op': 'tgt', 'f': dict(f, side='own', type='unit'), 'n': n, 'upto': 0}, {'op': 'drop', 'to': 'T'}])(parse_desc(m.group('d') if m.group('d') is not None else m.group('d2')) if (m.group('d') or m.group('d2')) else {}, int(m.group('n') or m.group('n2')))),
        (r'あなたのドロップゾーンを(?P<n>\d+)枚リムーブする', lambda m: [{'op': 'pick', 'from': 'drop', 'to': 'remove', 'f': {}, 'n': int(m.group('n')), 'upto': 0}]),
        (r'あなたの他のユニットを1枚レストする', lambda m: [{'op': 'tgt', 'f': {'side': 'own', 'type': 'unit', 'notSelf': 1, 'rested': 0}, 'n': 1, 'upto': 0}, {'op': 'rest', 'to': 'T'}]),
        (r'あなたの(?P<d>[^。]*?)ユニットを1枚手札に戻す', lambda m: (lambda f: f is not None and [{'op': 'tgt', 'f': dict(f, side='own', type='unit'), 'n': 1, 'upto': 0}, {'op': 'bounce', 'to': 'T'}])(parse_desc(m.group('d')) if m.group('d') else {})),
        (r'このユニットについたクラスカードを(?P<n>\d+)枚ドロップする', lambda m: [{'op': 'classDropSelf', 'n': int(m.group('n'))}]),
        (r'あなたのドロップゾーンの(?P<d>[^。]*?)を(?P<n>\d+)枚リムーブする', lambda m: (lambda f: f is not None and [{'op': 'pick', 'from': 'drop', 'to': 'remove', 'f': f, 'n': int(m.group('n')), 'upto': 0}])(_zdesc(m.group('d')))),
        (r'あなたの手札の(?P<d>[^。]*?)を(?P<n>\d+)枚まで公開する', lambda m: (lambda f: f is not None and [{'op': 'revealHand', 'n': int(m.group('n')), 'f': f, 'opt': 1}])(_zdesc(m.group('d')))),
        (r'このユニットをドロップする', lambda m: [{'op': 'drop', 'to': 'self'}]),
        (r'このユニットを手札に戻す', lambda m: [{'op': 'bounce', 'to': 'self'}]),
        (r'このユニットを山札の下に置く', lambda m: [{'op': 'deckBottom', 'to': 'self'}]),
        (r'このユニットをリムーブする', lambda m: [{'op': 'remove', 'to': 'self'}]),
        (r'あなたのライフの先頭を(?:ドロップ|手札に加え)る?', lambda m: [{'op': 'lifeHand', 'n': 1}]),
    ]
    for rx, fn in C:
        m = re.fullmatch(rx, t)
        if m:
            if fn == 'edesc':
                f = parse_desc(m.group('d') + 'の')
                if f is None:
                    return None
                return [{'op': 'payEnergy', 'n': int(m.group('n')), 'f': f, 'inCost': 1}]
            if fn == 'desc':
                f = parse_desc(m.group('d'))
                if f is None:
                    return None
                if m.group('noun'):
                    noun_filter(f, m.group('noun'))
                return [{'op': 'discard', 'n': int(m.group('n')), 'f': f, 'inCost': 1}]
            r = fn(m)
            return r and [{**x, 'inCost': 1} for x in r]
    return None


def _parse_alt(x, n):
    """대체 플레이 비용 -> {kind, ...} | None"""
    if n:
        return {'kind': 'cost', 'n': int(n)}
    if not x:
        return {'kind': 'free'}
    CL = {'黒': 'black', '白': 'white', '青': 'blue', '赤': 'red'}
    m = re.fullmatch(r'あなたの(?P<c>黒|白|青|赤)(?P<k>\d+)枚を含むエナジーを(?P<n>\d+)枚レストする', x)
    if m:
        return {'kind': 'restEIncl', 'n': int(m.group('n')), 'incl': {'color': CL[m.group('c')], 'n': int(m.group('k'))}}
    m = re.fullmatch(r'あなたの裏のエナジーを(?P<n>\d+)枚レストし、あなたの(?P<d>[^、。]+?)を(?P<k>\d+)枚ドロップする', x)
    if m and _zdesc(m.group('d')) is not None:
        return {'kind': 'multi', 'parts': [{'kind': 'restE', 'n': int(m.group('n')), 'f': {}, 'down': 1}, {'kind': 'dropU', 'f': dict(_zdesc(m.group('d')), type='unit'), 'n': int(m.group('k'))}], 'fText': x}
    m = re.fullmatch(r'あなたの手札(?:から|の)、?(?P<d>[^、。]+?)を(?P<n>\d+)枚ドロップする', x)
    if m and _zdesc(m.group('d')) is not None:
        return {'kind': 'discardF', 'f': _zdesc(m.group('d')), 'n': int(m.group('n')), 'fText': x}
    m = re.fullmatch(r'あなたのドロップゾーンの(?P<a>黒|白|青|赤)と(?P<b>黒|白|青|赤)の、(?P<d>[^、。]+?)を1枚ずつリムーブする', x)
    if m and _zdesc(m.group('d')) is not None:
        f = _zdesc(m.group('d'))
        return {'kind': 'removeDrop', 'each': [dict(f, color=[CL[m.group('a')]]), dict(f, color=[CL[m.group('b')]])], 'fText': x}
    m = re.fullmatch(r'あなたの(?P<d>[^。]*?)エナジー(?:を)?(?P<n>\d+)枚(?:を)?レストする', x)
    if m:
        dd = re.sub(r'である$', '', m.group('d').rstrip('の'))
        down = dd == '裏'
        f = {} if down or not dd else _zdesc(dd)
        if f is None:
            f = _zdesc(dd + 'カード')
        if f is None:
            return None
        f = {k: v for k, v in f.items() if k not in ('side', 'type')} if f else f
        if 'エース' in dd:
            f['ace'] = 1
        return {'kind': 'restE', 'n': int(m.group('n')), 'f': f, **({'down': 1} if down else {}), 'fText': dd}
    m = re.fullmatch(r'あなたの(?:フィールドの)?(?P<d>[^。]*?)(?P<ace>エース)?(?:ユニット)?1枚をレストする|あなたの(?:フィールドの)?(?P<d2>[^。]*?)(?:ユニット)?を1枚レストする', x)
    if m:
        dd = m.group('d') if m.group('d') is not None else m.group('d2')
        f = _zdesc(dd) if dd else {}
        if f is not None and m.group('ace'):
            f = dict(f, ace=1)
        if f is None:
            return None
        return {'kind': 'restU', 'units': [dict(f, type='unit')], 'fText': dd}
    m = re.fullmatch(r'あなたの、?(?P<l>(?:(?:ハート|スペード|ダイヤ|クラブ)、?)+)のユニットをそれぞれ1枚ずつレストする', x)
    if m:
        at = re.findall(r'ハート|スペード|ダイヤ|クラブ', m.group('l'))
        return {'kind': 'restU', 'units': [{'attr': [a], 'type': 'unit'} for a in at], 'fText': '、'.join(at)}
    return None


def parse_skill(line):
    """【スキル】… 줄 -> 비용 단계 | None"""
    m = re.fullmatch(r'【スキル】(.+?)。?', N(line))
    if not m:
        return None
    body = m.group(1)
    parts = re.split(r'か、|か(?=あなたの)', body)
    if len(parts) > 1:
        return None   # 'A か B' 선택형 비용은 아직 수동
    return parse_cost(body.rstrip('。'), None)


# ---------- 상시 능력 ----------
def parse_perm(t):
    """⁅永続⁆ 본문 -> {if:[...], do:[pow/hit/kw ...]} | None"""
    _t = t.strip('。')
    if _t.startswith('あなたのテリトリー開放中なら、各プレイヤーのプレイしたコマンドの効果は『ユニットを1枚対象とし、対象に10000ダメージ'):
        return {'if': [{'terr': 1}], 'do': [{'op': 'rule', 'rule': 'cmdTo10000'}]}
    if re.fullmatch(r'あなたのテリトリー開放中にこのユニットが与えたダメージで、最初にライフから出たカードが⁅B⁆でも⁅☆⁆でもないなら、そのカードに⁅B⁆を与える', _t):
        return {'if': [{'terr': 1}], 'do': [{'op': 'kw', 'kw': 'firstLifeBuster', 'to': 'self'}]}
    t = re.sub(r'(\d+)億', lambda m: str(int(m.group(1)) * 100000000), t)
    t = re.sub(r'(\d+)万', lambda m: str(int(m.group(1)) * 10000), t)
    t = t.replace('。』', '』')
    t = re.sub(r'各ターン1回まで、(このユニットはレストしていてもアタックできる)', r'\1', t)
    t = re.sub(r'(を[+-]\d+)し、', r'\1。', t)
    t = re.sub(r'(を[+-]\d+)、(?=相手は|このユニットは|あなたは|あなたの|パワーを\d+倍)', r'\1。', t)
    # 규칙 문장
    R = [(r'あなたがドローフェイズにカードを引く際、自分の手札が1枚以下なら、1枚引く代わりに(?:あなたの)?手札が3枚になるように引(?:く|いてよい)', 'drawTo3'),
         (r'あなたのドロップゾーンのカードは他の領域に移動できない', 'dropLock')]
    pre_rules = []
    for rx, rule in R:
        if re.search(rx, t):
            pre_rules.append({'op': 'rule', 'rule': rule})
            t = re.sub(rx + r'。?', '', t).strip('。')
    if pre_rules and not t:
        return {'if': [], 'do': pre_rules}
    conds = []
    for _ in range(3):
        m = re.match(r'(?P<c>.+?)(?:なら|ていたら|中で|中|時|際)、', t)
        if not m:
            break
        c = parse_cond(m.group('c').rstrip('で') + ('ている' if m.group(0).endswith('ていたら、') else ''))
        if c is None:
            break
        conds += c
        t = t[m.end():]
    out = list(pre_rules)
    last = {}
    m0 = re.match(r'クラスカード(?:を持つ|がついた|がついている)(?=このユニット)', t)
    if m0:
        conds = conds + [{'selfHasClass': 1}]
        t = t[m0.end():]
    for sent in [x for x in t.split('。') if x]:
        n0 = len(out)
        per = None
        sc = None
        msc = re.match(r'(?P<c>[^、。]+?)(?:なら|ていたら)、(?:さらに)?', sent)
        if msc:
            cc = parse_cond(msc.group('c') + ('ている' if msc.group(0).rstrip('さらに').endswith('ていたら、') else ''))
            if cc is not None:
                sc = cc
                sent = sent[msc.end():]
        if re.fullmatch(r'[+-]\d+', sent) and last:   # 「さらに+1」: 앞과 같은 수정
            out.append(dict(last, n=int(sent), **({'c': sc} if sc else {})))
            continue
        mp = re.match(r'あなたの(?P<z>エナジー|手札|ドロップゾーンのカード|ドロップゾーン|ユニット|つけた契約書|つけたログ)(?P<k>\d+)枚につき、', sent)
        if mp:
            per = {'zone': {'エナジー': 'energy', '手札': 'hand', 'ドロップゾーンのカード': 'drop', 'ドロップゾーン': 'drop', 'ユニット': 'field', 'つけた契約書': 'contract', 'つけたログ': 'log'}[mp.group('z')], 'k': int(mp.group('k'))}
            sent = sent[mp.end():]
        mp = re.match(r'(?:あなたのターン中、)?あなたの(?P<z>ドロップゾーンの)?(?P<d>[^、。]+?)(?P<noun>ユニット|カード)(?P<k>\d+)枚につき、', sent) if not per else None
        if mp:
            f = _zdesc(mp.group('d') + mp.group('noun'))
            if f is not None:
                per = {'zone': 'drop' if mp.group('z') else 'field', 'k': int(mp.group('k')), 'f': f}
                sent = sent[mp.end():]
        mp = re.match(r'このユニットのパワー(?P<k>\d+)につき、', sent) if not per else None
        if mp:
            per = {'selfPow': int(mp.group('k'))}
            sent = sent[mp.end():]
        sent = re.sub(r'^フィールドの', '', sent)
        if re.match(r'【(?:デコイ|ブリッツ|バーサーク)】を得', sent):
            sent = 'このユニットは' + sent
        if re.match(r'(?:パワー|ヒット)を(?:[+-]\d+|\d+倍にする)$', sent) and last:   # 주어 생략: 앞 문장의 대상
            sent = {'self': 'このユニット', 'host': 'このカードをつけたユニット'}.get(last.get('to'), 'このユニット') + 'の' + sent
        r = _perm_sent(sent, per)
        if r is None:
            _FAIL['at'] = 'PERM:' + sent
            return None
        for st in r:
            if sc:
                st['c'] = sc
        out += r
        if r and r[-1].get('op') in ('pow', 'hit'):
            last = {k: v for k, v in r[-1].items() if k != 'c'}
    return {'if': conds, 'do': out} if out else None


def _perm_sent(sent, per):
    """영속 효과 한 문장 -> 단계 목록 | None"""
    out = []
    mg = re.fullmatch(r'あなたの、?(?P<a>.+?)ユニットと(?P<b>.+?)ユニット全ては、相手のコマンドの対象にならない', sent)
    if mg and parse_desc(mg.group('a')) is not None and parse_desc(mg.group('b')) is not None:
        return [{'op': 'kw', 'kw': 'cmdImmune', 'to': {'all': {'side': 'own', 'type': 'unit', 'or': [parse_desc(mg.group('a')), parse_desc(mg.group('b'))]}}}]
    if sent == '各プレイヤーのプレイしたコマンドの効果は『ユニットを1枚対象とし、対象に10000ダメージ。』になる':
        return [{'op': 'rule', 'rule': 'cmdTo10000'}]
    if sent == 'このユニットが与えたダメージで、最初にライフから出たカードが⁅B⁆でも⁅☆⁆でもないなら、そのカードに⁅B⁆を与える':
        return [{'op': 'kw', 'kw': 'firstLifeBuster', 'to': 'self'}]
    SP = {'このユニットがユニットに与えるダメージは2倍になる': 'dealDouble',
          'このユニットが【ブライト】していないバトル中、このユニットがユニットに与えるダメージは0になる': 'zeroUnlessBright'}
    if sent in SP:
        return [{'op': 'kw', 'kw': SP[sent], 'to': 'self'}]
    m = re.fullmatch(r'相手は(?P<d>[^、。]*?)ユニットではアタックができない', sent)
    if m:
        f = parse_desc('相手の' + m.group('d'))
        return None if f is None else [{'op': 'kw', 'kw': 'noAttack', 'to': {'all': dict(f, type='unit')}}]
    if True:
        sent = re.sub(r'^あなたの、', 'あなたの', sent)
        m = re.fullmatch(r'(?P<to>[^。]*?)の(?P<mods>(?:パワー|ヒット)を[+-]\d+(?:、(?:パワー|ヒット)を[+-]\d+)?)(?:する)?', sent)
        if m and per:
            to = subj(m.group('to'))
            if not to:
                return None
            for k, v in re.findall(r'(パワー|ヒット)を([+-]\d+)', m.group('mods')):
                out.append({'op': 'pow' if k == 'パワー' else 'hit', 'n': int(v), 'to': to, 'per': per})
            return out
        if m:
            to = subj(m.group('to'))
            if not to:
                return None
            for k, v in re.findall(r'(パワー|ヒット)を([+-]\d+)', m.group('mods')):
                out.append({'op': 'pow' if k == 'パワー' else 'hit', 'n': int(v), 'to': to})
            return out
        m = re.fullmatch(r'(?P<to>[^、。]*?)は【(?P<k>デコイ|ブリッツ|バーサーク)】を得て、(?P<mods>(?:パワー|ヒット)を[+-]\d+)', sent)
        if m:
            to = subj(m.group('to'))
            if not to:
                return None
            out.append({'op': 'kw', 'kw': {'デコイ': 'decoy', 'ブリッツ': 'blitz', 'バーサーク': 'berserk'}[m.group('k')], 'to': to})
            for k, v in re.findall(r'(パワー|ヒット)を([+-]\d+)', m.group('mods')):
                out.append({'op': 'pow' if k == 'パワー' else 'hit', 'n': int(v), 'to': to})
            return out
        KWP = [(r'アタックもブロックもされ(?:ず|ない)', ['noBeAttacked', 'unblockable']), (r'ユニットにアタックできない', ['noAttackUnit']), (r'他の能力を全て失う', ['blank']),
               (r'受けるダメージ全てを0にする', ['noDamage']), (r'ドロップ以外の方法でフィールドを離れない', ['stayField']), (r'コマンドの対象にならず', ['cmdImmune']),
               (r'アタックされ(?:ず|ない)', ['noBeAttacked']), (r'【デコイ】を無視してアタックでき(?:る)?', ['ignoreDecoy']), (r'ブロックされ(?:ず|ない)', ['unblockable']),
               (r'ブロックができ(?:ず|ない)', ['noBlock']), (r'アタックもブロックもできない', ['noAttack', 'noBlock']), (r'レストで登場する', ['enterRested']),
               (r'可能な限りアタックする', ['mustAttack']), (r'手札に戻らず(?:、)?山札に置かれない', ['noBounce', 'noDeck']), (r'手札に戻らない', ['noBounce']),
               (r'卒業できず(?:、)?リムーブされない', ['noGraduate', 'noRemove']), (r'相手の効果でレストしない', ['noOppRest']),
               (r'(?:相手の)?エースにアタックされない', ['noAtkByAce']), (r'相手の効果の対象にならない', ['oppFxImmune']), (r'ユニットの効果の対象にならない', ['unitFxImmune']),
               (r'相手のコマンドの対象にならない', ['cmdImmune']), (r'相手の効果でパワーが減少しない', ['noOppDebuff']), (r'【デコイ】を失い', ['loseDecoy']),
               (r'(?:各ターン1回まで、)?レストしていてもアタックできる', ['attackRested']), (r'スタンドしているユニットにアタックできる', ['atkStand']),
               (r'コマンドカードでも【ブライト】できる', ['brightCmdSelf']),
               (r'ユニットに与えるダメージは2倍になる', ['dealDouble']),
               (r'(?:パワーを(?P<pw>[+-]\d+)(?:、|し、))', 'POW'), (r'(?:ヒットを(?P<ht>[+-]\d+)(?:、|し、)?)', 'HIT'),
               (r'【(デコイ|ブリッツ|バーサーク)】(?:と【(デコイ|ブリッツ|バーサーク)】)?を得(?:る|て)', None)]
        sent = re.sub(r'^このユニットが受けるダメージ全てを0にする$', 'このユニットは受けるダメージ全てを0にする', sent)
        mk = re.fullmatch(r'(?P<to>[^。]*?)(?:では|は)(?P<l>.+)', sent)
        if mk and subj(re.sub(r'^あなたの、', 'あなたの', mk.group('to'))):
            to = subj(re.sub(r'^あなたの、', 'あなたの', mk.group('to')))
            rest_, ks = mk.group('l'), []
            while rest_:
                for rx, kk in KWP:
                    mm = re.match(rx + r'(?:、)?', rest_)
                    if mm:
                        if kk in ('POW', 'HIT'):
                            ks.append(('pow', int(mm.group('pw'))) if kk == 'POW' else ('hit', int(mm.group('ht'))))
                        elif kk is None:
                            ks += [{'デコイ': 'decoy', 'ブリッツ': 'blitz', 'バーサーク': 'berserk'}[x] for x in mm.groups() if x]
                        else:
                            ks += kk
                        rest_ = rest_[mm.end():]
                        break
                else:
                    break
            if not rest_ and ks:
                out += [{'op': k[0], 'n': k[1], 'to': to} if isinstance(k, tuple) else {'op': 'kw', 'kw': k, 'to': to} for k in ks]
                return out
        mb = re.fullmatch(r'(?P<to>[^。]*?)は【ブライト(?P<n>\d+):(?P<a>[^】]+)】を得る', sent)
        if mb and subj(mb.group('to')):
            out.append({'op': 'kw', 'kw': 'bright:' + mb.group('n') + ':' + mb.group('a'), 'to': subj(mb.group('to'))})
            return out
        if re.fullmatch(r'相手はあなたのユニットのアタックを可能な限りブロックする', sent):
            out.append({'op': 'kw', 'kw': 'mustBlock', 'to': {'all': {'side': 'opp', 'type': 'unit'}}})
            return out
        m = re.fullmatch(r'(?P<to>[^、。]*?)は(?P<k>アタックされない|スタンドフェイズにスタンドしない|エースでないユニットにはアタックされない|スタンドしているユニットにアタックできる|レストで登場し、スタンドフェイズにスタンドしない)', sent)
        if m:
            to = subj(m.group('to'))
            if not to:
                return None
            out.append({'op': 'kw', 'kw': {'アタックされない': 'noBeAttacked', 'スタンドフェイズにスタンドしない': 'noStand', 'エースでないユニットにはアタックされない': 'aceOnlyAttack', 'スタンドしているユニットにアタックできる': 'atkStand', 'レストで登場し、スタンドフェイズにスタンドしない': 'noStand'}[m.group('k')], 'to': to})
            if 'レストで登場' in m.group('k'):
                out.append({'op': 'kw', 'kw': 'enterRested', 'to': to})
            return out
        if re.fullmatch(r'あなたは(?:ライフが0枚でも)?ダメージで敗北しない', sent):
            out.append({'op': 'rule', 'rule': 'noLoseDmg'})
            return out
        if re.fullmatch(r'相手の手札上限は(\d+)枚になる', sent):
            out.append({'op': 'rule', 'rule': 'oppHand' + re.search(r'\d+', sent).group()})
            return out
        m = re.fullmatch(r'(?P<to>[^、。]*?)(?:は|では)(?P<k>アタックとブロックができない|アタックできない|アタックができない|ブロックができない|ブロックできない|ブロックされない)', sent)
        if m:
            to = subj(m.group('to'))
            if not to:
                return None
            ks = {'アタックとブロックができない': ['noAttack', 'noBlock'], 'アタックできない': ['noAttack'], 'アタックができない': ['noAttack'], 'ブロックができない': ['noBlock'], 'ブロックできない': ['noBlock'], 'ブロックされない': ['unblockable']}[m.group('k')]
            out += [{'op': 'kw', 'kw': k, 'to': to} for k in ks]
            return out
        m = re.fullmatch(r'(?P<to>[^、。]*?)は(?P<n>\d+)ダメージでも受けるとドロップする', sent)
        if m and subj(m.group('to')):
            out.append({'op': 'kw', 'kw': 'fragile', 'to': subj(m.group('to'))})
            return out
        m = re.fullmatch(r'(?P<to>[^、。]*?)は【(?P<k>デコイ|ブリッツ|バーサーク)】を得る', sent)
        if m:
            to = subj(m.group('to'))
            if not to:
                return None
            out.append({'op': 'kw', 'kw': {'デコイ': 'decoy', 'ブリッツ': 'blitz', 'バーサーク': 'berserk'}[m.group('k')], 'to': to})
            return out
        # 그 밖의 영속 문장
        sent2 = re.sub(r'^フィールドの', '', sent)
        m = re.fullmatch(r'相手はこのユニットを、トリガーでプレイするコマンド以外で対象にできない', sent2)
        if m:
            return [{'op': 'kw', 'kw': 'oppFxImmuneT', 'to': 'self'}]
        m = re.fullmatch(r'相手はこのユニットのアタックを可能な限りブロックする', sent2)
        if m:
            return [{'op': 'kw', 'kw': 'forceBlock', 'to': 'self'}]
        m = re.fullmatch(r'このユニットは【ブリッツ】を得て、相手はこのユニットのアタックを可能な限りブロックする', sent2)
        if m:
            return [{'op': 'kw', 'kw': 'blitz', 'to': 'self'}, {'op': 'kw', 'kw': 'forceBlock', 'to': 'self'}]
        m = re.fullmatch(r'相手は(?P<d>[^、。]*?)ユニットではアタックができない', sent2)
        if m:
            f = parse_desc('相手の' + m.group('d'))
            if f is not None:
                return [{'op': 'kw', 'kw': 'noAttack', 'to': {'all': dict(f, type='unit')}}]
        m = re.fullmatch(r'(?:クラスカードがついた)?このユニットがダメージを与えたユニットは、パワーに関わらずドロップされる', sent2)
        if m:
            return [{'op': 'kw', 'kw': 'deathtouch', 'to': 'self'}]
        if re.fullmatch(r'その際、そのユニットが持つ能力は全て発動しない', sent2):
            return [{'op': 'kw', 'kw': 'deathtouchSilent', 'to': 'self'}]
        m = re.fullmatch(r'このユニットはコスト(?P<n>\d+)のユニットにアタックされない', sent2)
        if m:
            return [{'op': 'kw', 'kw': 'noAtkByCost:' + m.group('n'), 'to': 'self'}]
        m = re.fullmatch(r'(?P<to>[^、。]*?)は【(?P<a>デコイ|ブリッツ|バーサーク)】と【(?P<b>デコイ|ブリッツ|バーサーク)】を得て、それらが受ける効果によるダメージを0にする', sent2)
        if m and subj(m.group('to')):
            to = subj(m.group('to'))
            KM = {'デコイ': 'decoy', 'ブリッツ': 'blitz', 'バーサーク': 'berserk'}
            return [{'op': 'kw', 'kw': KM[m.group('a')], 'to': to}, {'op': 'kw', 'kw': KM[m.group('b')], 'to': to}, {'op': 'kw', 'kw': 'noEffDmg', 'to': to}]
        m = re.fullmatch(r'(?P<to>相手のユニット|あなたのユニット)が受けるダメージは2倍になる', sent2)
        if m:
            return [{'op': 'kw', 'kw': 'dmgDouble', 'to': {'all': {'side': 'opp' if m.group('to').startswith('相手') else 'own', 'type': 'unit'}}}]
        if re.fullmatch(r'このユニットが受けるダメージ全てを0にする|そのバトル中にこのユニットが受けるダメージ全てを0にする', sent2):
            return [{'op': 'kw', 'kw': 'noDamage', 'to': 'self'}]
        m = re.fullmatch(r'このユニットの色は(?P<c>赤|青|白|黒)になり、(?:赤|青|白|黒)以外の色を失う', sent2)
        if m:
            c = {'赤': 'red', '青': 'blue', '白': 'white', '黒': 'black'}[m.group('c')]
            return [{'op': 'kw', 'kw': 'colorAs:only', 'to': 'self'}, {'op': 'kw', 'kw': 'colorAs:' + c, 'to': 'self'}]
        m = re.fullmatch(r'このユニットは⁅(?P<i>バスター|ショット)アイコン⁆を持つ', sent2)
        if m:
            return [{'op': 'kw', 'kw': 'iconAs:' + ('buster' if m.group('i') == 'バスター' else 'shot'), 'to': 'self'}]
        if re.fullmatch(r'あなたのバスターアイコンがライフからドロップする際、代わりに手札に戻す', sent2):
            return [{'op': 'rule', 'rule': 'lifeBusterToHand'}]
        if re.fullmatch(r'このユニットがダメージを与えたユニットは、そのターン中、ドロップする際、代わりにエナジーゾーンに置く', sent2):
            return [{'op': 'kw', 'kw': 'dmgToEnergy', 'to': 'self'}]
        if re.fullmatch(r'このユニットがこのターンのアタックフェイズに登場したユニットから受けるダメージは0になる', sent2):
            return [{'op': 'kw', 'kw': 'noDmgFromAtkEntered', 'to': 'self'}]
        if re.fullmatch(r'各プレイヤーはショットアイコンのコマンドをプレイできない', sent2):
            return [{'op': 'rule', 'rule': 'noShotCmd'}]
        m = re.fullmatch(r'このユニットのパワーを(?P<n>\d+)倍にする', sent2)
        if m:
            return [{'op': 'kw', 'kw': 'powMul:' + m.group('n'), 'to': 'self'}]
        m = re.fullmatch(r'このユニットは色に(?P<a>赤|青|白|黒)と(?P<b>赤|青|白|黒)も持つ', sent2)
        if m:
            CL = {'赤': 'red', '青': 'blue', '白': 'white', '黒': 'black'}
            return [{'op': 'kw', 'kw': 'colorAs:' + CL[m.group('a')], 'to': 'self'}, {'op': 'kw', 'kw': 'colorAs:' + CL[m.group('b')], 'to': 'self'}]
        # 『~』を得る: 다른 능력 부여
        m = re.fullmatch(r'(?P<to>[^、。『]*?)は(?P<kws>(?:【(?:デコイ|ブリッツ|バーサーク)】と)*)『(?P<ab>⁅自動⁆[^』]+?)。?』を得(?:る|て、(?P<mods>(?:(?:パワー|ヒット)を[+-]\d+、?)+))?', sent2)
        if m and subj(m.group('to')):
            to = subj(m.group('to'))
            ab = _parse_body2(m.group('ab'), {}, None)
            if ab and ab.get('k') == 'auto':
                r = [{'op': 'kw', 'kw': {'デコイ': 'decoy', 'ブリッツ': 'blitz', 'バーサーク': 'berserk'}[x], 'to': to} for x in re.findall(r'【([^】]+)】', m.group('kws') or '')]
                r.append({'op': 'grant', 'ab': ab, 'to': to})
                for kk, vv in re.findall(r'(パワー|ヒット)を([+-]\d+)', m.group('mods') or ''):
                    r.append({'op': 'pow' if kk == 'パワー' else 'hit', 'n': int(vv), 'to': to})
                return r
        return None


# ---------- 카드 전체 ----------
def split_once(body):
    once = 0
    for rx in [r'この能力は(?:各|1)ターン(?:に)?1回(?:まで|のみ)?(?:しか)?発動(?:でき|し)(?:る|ない)。?', r'\(この能力は各ターン1回まで発動できる\)']:
        if re.search(rx, body):
            once = 1
            body = re.sub(rx, '', body)
    return body.strip(), once


def parse_card(d):
    """카드 정의 d(text/tfx 포함) -> (ab 목록, 자동 처리된 줄 번호 집합)"""
    if d.get('type') == 'territory':
        lines = [x for x in (d.get('tfx', {}).get('text', '') or '').split(' / ') if x and x != '(효과 없음)']
    else:
        lines = list(d.get('text') or [])
    lines = [N(x) for x in lines]
    lines = [re.sub(r'(【怪異:[^】⁆]+)⁆/自動⁆', r'\1】⁅自動⁆', x) for x in lines]
    tmerge = []
    if d.get('type') == 'territory':   # 테리토리 효과가 ' / '로 잘린 이어지는 문장
        merged = []
        for x in lines:
            if merged and not re.match(r'[⁅【・(「]|このカードは', x) and re.match(r'(?:次の|その|そうしたら|さらに)', x):
                k0 = max(i0 for i0, y in enumerate(merged) if y)
                merged[k0] = merged[k0] + x
                tmerge.append((len(merged), k0))
                merged.append('')
            else:
                merged.append(x)
        lines = merged
    # 원문 줄이 문장 중간에서 끊긴 경우 이어 붙임 (줄 번호는 첫 줄)
    joined = {}
    k = 0
    while k < len(lines) - 1:
        j = k + 1
        while j < len(lines):
            a, b = lines[k], lines[j]
            if a and not re.search(r'[。)」】]$', a) and b and not re.match(r'[⁅【・(「]', b) and not a.startswith('【スキル】'):
                lines[k] = a + b
                lines[j] = ''
                joined[j] = k
                j += 1
                continue
            break
        k = j
    skill = None
    for x in lines:
        if x.startswith('【スキル】'):
            skill = parse_skill(x)
    abs_, done, mts = [], set(), []
    _SKILL['s'] = skill
    i = 0
    while i < len(lines):
        ln = lines[i]
        if not ln:
            i += 1
            continue
        # 「以下を1つ行う」 + ・줄들
        ln = re.sub(r'(行う。)\([^)]*\)$', r'\1', ln)
        # 「以下を1つでも満たすなら、~」 + ・조건 줄들
        mor = re.fullmatch(r'(?P<h>.*?)以下を1つでも満たすなら、(?P<a>.+)', ln)
        if mor and i + 1 < len(lines) and lines[i + 1].startswith('・'):
            j = i + 1
            cs = []
            while j < len(lines) and lines[j].startswith('・'):
                cs.append(parse_cond(lines[j][1:].rstrip('。')))
                j += 1
            if all(c is not None for c in cs):
                _ORCOND['c'] = [{'any': [{'all': c} if len(c) > 1 else c[0] for c in cs]}]
                r = parse_body(mor.group('h') + '__ORCOND__なら、' + mor.group('a'), d, skill)
                _ORCOND.clear()
                if r:
                    r['li'] = list(range(i, j))
                    abs_.append(r)
                    done.update(range(i, j))
            i = j
            continue
        # 「以下をN回(まで)行う(てよい)」
        mrp = re.fullmatch(r'(?P<h>.*?)(?<!相手は)以下を(?P<n>\d+)回(?P<upto>まで)?行(?:う|ってよい)。?', ln)
        if mrp and i + 1 < len(lines) and lines[i + 1].startswith('・'):
            j = i + 1
            opts = []
            while j < len(lines) and lines[j].startswith('・'):
                opts.append(parse_effects_lenient(lines[j][1:]))
                j += 1
            if all(o is not None for o in opts):
                body = sum(opts, [])
                seq = []
                for k2 in range(int(mrp.group('n'))):
                    if mrp.group('upto') or 'てよい' in ln:
                        seq.append({'op': 'confirm', 'text': f'{k2 + 1}번째로 할까요?', 'alt': 1, 'no': [{'op': 'stop'}]})
                    seq += body
                r = parse_body(mrp.group('h') + '__CHOOSE__', d, skill) or parse_body_lenient(mrp.group('h') + '__CHOOSE__', d, skill)
                if r:
                    def _sub(sq):
                        for k3, st in enumerate(sq):
                            if st.get('op') == 'choose' and not st.get('opts'):
                                sq[k3:k3 + 1] = seq
                                return True
                            if st.get('op') in ('if', 'askIf') and _sub(st.get('then', [])):
                                return True
                        return False
                    if _sub(r['do']):
                        r['li'] = list(range(i, j))
                        abs_.append(r)
                        done.update(range(i, j))
            i = j
            continue
        # 「以下を行う。Xなら、2回行う / もう1回行ってよい」: 묶음을 한 번 더
        mrep = re.fullmatch(r'(?P<h>.*?)以下を行う。(?P<c>[^。]+?)なら、(?:その後、)?(?:2回行う|もう1回行(?P<may>ってよい|う))。?(?:\(.*\))?', ln)
        if mrep and i + 1 < len(lines) and lines[i + 1].startswith('・'):
            j = i + 1
            opts = []
            while j < len(lines) and lines[j].startswith('・'):
                opts.append(parse_effects_lenient(lines[j][1:]))
                j += 1
            c = parse_cond(mrep.group('c'))
            if all(o is not None for o in opts) and c is not None:
                body = sum(opts, [])
                again = ([{'op': 'confirm', 'text': '한 번 더 할까요?', 'alt': 1, 'no': []}] if mrep.group('may') else []) + body
                tail = {'op': 'if', 'c': c, 'then': again} if c is not None else None
                r = parse_body(mrep.group('h') + '__CHOOSE__', d, skill) or parse_body_lenient(mrep.group('h') + '__CHOOSE__', d, skill)
                if r:
                    for k2, st in enumerate(r['do']):
                        if st.get('op') == 'choose':
                            r['do'][k2:k2 + 1] = body + [tail]
                            break
                    if c is None:
                        r['guided'] = 1
                    r['li'] = list(range(i, j))
                    abs_.append(r)
                    done.update(range(i, j))
            i = j
            continue
        # 「以下を1つ行う。Xなら、N つ目の選択肢は選べない」
        mdis = re.fullmatch(r'(?P<h>.*?以下を1つ行う。)(?P<c>[^。]+?)なら、(?P<k>\d)つ目の選択肢は選べない。?', ln)
        dis = None
        if mdis:
            dis = {'k': int(mdis.group('k')) - 1, 'c': parse_cond(mdis.group('c'))}
            ln = mdis.group('h')
        # 특수 ・목록들
        def _bul(j0):
            j = j0
            out = []
            while j < len(lines) and lines[j].startswith('・'):
                out.append(lines[j][1:].rstrip('。'))
                j += 1
            return out, j
        def _subch(sq, rep_):
            for k3, st in enumerate(sq):
                if st.get('op') == 'if' and st.get('c') == [{'did': 1}] and st.get('then') == [] and k3 + 1 < len(sq) and sq[k3 + 1].get('op') == 'choose' and not sq[k3 + 1].get('opts'):
                    st['then'] = rep_
                    del sq[k3 + 1]
                    return True
                if st.get('op') == 'choose' and not st.get('opts'):
                    sq[k3:k3 + 1] = rep_
                    return True
                if st.get('op') == 'if' and _subch(st.get('then', []), rep_):
                    return True
            return False
        msp = re.fullmatch(r'(?P<h>.*?)あなたは手札を望む枚数ドロップしてよい。ドロップした枚数\+1回、以下を行う。?', ln)
        if msp and i + 1 < len(lines) and lines[i + 1].startswith('・'):
            bl, j = _bul(i + 1)
            opts = [parse_effects_lenient(b) for b in bl]
            r = parse_body(msp.group('h') + '__CHOOSE__', d, skill)
            if r and all(o is not None for o in opts) and _subch(r['do'], [{'op': 'pick', 'from': 'hand', 'to': 'drop', 'f': {}, 'n': 99, 'upto': 1, 'may': 1}, {'op': 'repeatMilled', 'plus': 1, 'do': sum(opts, [])}]):
                r['li'] = list(range(i, j)); abs_.append(r); done.update(range(i, j))
            i = j
            continue
        msp = re.fullmatch(r'相手は手札を1枚公開し、そのカードタイプにより以下を行う。?', ln)
        if msp and i + 1 < len(lines) and lines[i + 1].startswith('・'):
            bl, j = _bul(i + 1)
            steps = [{'op': 'oppRevealPick'}]
            ok = True
            for b in bl:
                mb2 = re.fullmatch(r'(ユニットカード|コマンドカード):そのカードを(レストで登場させる|登場させる|ドロップする)', b)
                if not mb2:
                    ok = False; break
                act = {'op': 'milledOppHand', 'to': 'drop'} if 'ドロップ' in mb2.group(2) else {'op': 'milledOppHand', 'to': 'field', **({'rested': 1} if 'レスト' in mb2.group(2) else {})}
                steps.append({'op': 'if', 'c': [{'milledF': {'type': 'unit' if mb2.group(1) == 'ユニットカード' else 'command'}}], 'then': [act]})
            if ok:
                abs_.append({'k': 'play', 'if': [], 'do': steps, 'li': list(range(i, j))}); done.update(range(i, j))
            i = j
            continue
        msp = re.fullmatch(r'(?P<h>.*?)相手は以下を(?P<n>\d+)回行う。?', ln)
        if msp and i + 1 < len(lines) and lines[i + 1].startswith('・'):
            bl, j = _bul(i + 1)
            opts = [parse_effects_lenient(b) or parse_effects_lenient(b.replace('自身の', 'あなたの')) for b in bl]
            r = parse_body(msp.group('h') + '__CHOOSE__', d, skill)
            if r and all(o is not None for o in opts) and _subch(r['do'], [{'op': 'asOpp', 'do': sum(opts, []) * int(msp.group('n'))}]):
                r['li'] = list(range(i, j)); abs_.append(r); done.update(range(i, j))
            i = j
            continue
        msp = re.fullmatch(r'(?P<h>(?:⁅保持称号開放中⁆)?)⁅永続⁆このユニットはあなたのドロップゾーンのカードにより以下を得る。?', ln)
        if msp and i + 1 < len(lines) and lines[i + 1].startswith('・'):
            bl, j = _bul(i + 1)
            CL = {'黒': 'black', '青': 'blue', '白': 'white', '赤': 'red'}
            for b in bl:
                mb2 = re.fullmatch(r'(黒|青|白|赤)のエース:(.+)', b)
                if not mb2:
                    continue
                cc = [{'countGE': {'zone': 'drop', 'f': {'color': [CL[mb2.group(1)]], 'ace': 1}, 'n': 1}}] + ([{'hold': 1}] if msp.group('h') else [])
                y = mb2.group(2)
                mn = re.fullmatch(r'このユニットは「([^」]+)」として扱う', y)
                if mn:
                    abs_.append({'k': 'perm', 'if': cc, 'do': [{'op': 'kw', 'kw': 'nameAs:' + mn.group(1), 'to': 'self'}], 'li': [i]}); continue
                if re.fullmatch(r'このユニットは相手ターンは効果の対象にならない', y):
                    abs_.append({'k': 'perm', 'if': cc + [{'oppTurn': 1}], 'do': [{'op': 'kw', 'kw': 'fxImmune', 'to': 'self'}], 'li': [i]}); continue
                if '時、' in y:
                    gab = parse_body('⁅自動⁆' + y, d, skill)
                    if gab:
                        abs_.append({'k': 'perm', 'if': cc, 'do': [{'op': 'grant', 'ab': gab, 'to': 'self'}], 'li': [i]})
                    continue
                pm = parse_perm(y)
                if pm:
                    abs_.append({'k': 'perm', 'if': cc + pm['if'], 'do': pm['do'], 'li': [i]})
            done.update(range(i, j))
            i = j
            continue
        mall = re.fullmatch(r'(?P<h>.*?)(?P<opp>相手は)?(?P<get>(?:そのターン中、)?このユニットは)?以下を(?:全て)?(?:行(?P<may>ってよい|う)|得る)。?', ln)
        if mall and i + 1 < len(lines) and lines[i + 1].startswith('・'):
            j = i + 1
            opts = []
            while j < len(lines) and lines[j].startswith('・'):
                opts.append(parse_effects_lenient(re.sub(r'^これを得た時、', '', lines[j][1:])))
                j += 1
            if all(o is not None for o in opts) and (mall.group('opp') or mall.group('may') == 'ってよい'):
                flat = sum(opts, [])
                opts = [[{'op': 'choose', 'who': 'opp' if mall.group('opp') else None, 'opts': [flat, []], 'labels': ['한다', '하지 않는다'], 'text': '아래 효과를 실행할까요?'}]]
            if all(o is not None for o in opts):
                r = parse_body(mall.group('h') + '__CHOOSE__', d, skill) or parse_body_lenient(mall.group('h') + '__CHOOSE__', d, skill)
                if r:
                    for st in r['do']:
                        if st.get('op') == 'choose':
                            st['op'] = 'all'
                            st['opts'] = opts
                    r['li'] = list(range(i, j))
                    abs_.append(r)
                    done.update(range(i, j))
            i = j
            continue
        ln = re.sub(r'以下から1つ、(?P<c>[^。]+?)なら、両方を行う。?$', r'以下を1つ行う。\g<c>なら、両方行う。', ln)
        mb = re.search(r'以下を1つ(?:選んで)?行う。(?P<c>[^。]+?)なら、(?:代わりに)?両方行(?:う|ってよい)。?$', ln)
        kwline = re.search(r'【(?:夢を見ない|マギア|マケイン)】', ln)
        if not kwline and (re.fullmatch(r'以下を1つ(?:選んで)?行う。?', ln) or re.search(r'以下を1つ(?:選んで)?行う。?$', ln) or mb):
            both = parse_cond(mb.group('c')) if mb else None
            if mb and both is None:
                i += 1
                continue
            head = re.sub(r'以下を1つ(?:選んで)?行う。.*$|以下を1つ(?:選んで)?行う。?$', '', ln)
            head = re.sub(r'、?あなたは$', '、', head)
            byOpp = head.endswith('相手は')
            if byOpp:
                head = head[:-3]
            j = i + 1
            opts = []
            while j < len(lines) and lines[j].startswith('・'):
                opts.append(parse_effects_lenient(lines[j][1:].replace('自身の', 'あなたの') if byOpp else lines[j][1:]))
                j += 1
            ok = opts and all(o is not None for o in opts)
            if ok and byOpp:   # 상대가 고르고 상대 입장에서 실행
                opts = [[{'op': 'asOpp', 'do': o}] for o in opts]
            if ok:
                r = parse_body(head + '__CHOOSE__', d, skill) or parse_body_lenient(head + '__CHOOSE__', d, skill)
                if r and byOpp:
                    for st in r['do']:
                        if st.get('op') == 'choose':
                            st['who'] = 'opp'
                if r:
                    def _fill(seq):
                        for st in seq:
                            if st.get('op') == 'choose' and not st.get('opts'):
                                st['opts'] = opts
                                if both:
                                    st['bothIf'] = both
                                if dis and dis['c'] is not None:
                                    st['dis'] = dis
                            if st.get('op') in ('if', 'askIf'):
                                _fill(st.get('then', []))
                    _fill(r['do'])
                    r['li'] = list(range(i, j))
                    abs_.append(r)
                    done.update(range(i, j))
            i = j
            continue
        if re.fullmatch(r'【卒業】(?:\(.*\))?', ln):
            abs_.append({'k': 'auto', 'on': 'attackEnd', 'src': 'self', 'if': [], 'do': [{'op': 'graduate', 'may': 1}], 'li': [i]})
            done.add(i)
            i += 1
            continue
        m = re.fullmatch(r'【コスプレ(\d+)】(?:\(.*\))?', ln)
        if m:
            d['cos'] = int(m.group(1))
            done.add(i)
            i += 1
            continue
        m = re.fullmatch(r'⁅永続⁆このカードが「([^」]+)」を含むユニットの【コスプレ】で登場する際、コスト(\d+)として扱う。?', ln)
        if m:
            d['cosCost'] = {'name': m.group(1), 'cost': int(m.group(2))}
            done.add(i)
            i += 1
            continue
        m = re.fullmatch(r'⁅永続⁆あなたの称号「([^」]+)」のテリトリー開放中なら、このユニットの【コスプレ】は手札とエナジーから選べる。エナジーと入れ替えたら、1枚引く。?', ln)
        if m:
            abs_.append({'k': 'perm', 'if': [{'terrTitle': m.group(1)}], 'do': [{'op': 'rule', 'rule': 'cosEnergySelf', 'to': 'self'}], 'li': [i]})
            done.add(i)
            i += 1
            continue
        if re.fullmatch(r'⁅永続⁆あなたのユニットの【コスプレ】は、あなたのアタックフェイズ開始時にも発動する。?', ln):
            abs_.append({'k': 'perm', 'if': [], 'do': [{'op': 'rule', 'rule': 'cosAttackStart'}], 'li': [i]})
            done.add(i)
            i += 1
            continue
        m = re.fullmatch(r'⁅永続⁆(?:あなたの称号「([^」]+)」のテリトリー開放中、)?このユニットはブロックされず、【デコイ】を無視してアタックでき、ライフがレッドゾーンなら、さらにヒットを\+(\d)。?', ln)
        if m:
            c = [{'terrTitle': m.group(1)}] if m.group(1) else []
            abs_.append({'k': 'perm', 'if': c, 'do': [{'op': 'kw', 'kw': 'unblockable', 'to': 'self'}, {'op': 'kw', 'kw': 'ignoreDecoy', 'to': 'self'}], 'li': [i]})
            abs_.append({'k': 'perm', 'if': c + [{'red': 1}], 'do': [{'op': 'hit', 'n': int(m.group(2)), 'to': 'self'}], 'li': [i]})
            done.add(i)
            i += 1
            continue
        if re.fullmatch(r'⁅永続⁆あなたのクラスカードのエナジーは色が黒と青と赤になる。?', ln):
            abs_.append({'k': 'perm', 'if': [], 'do': [{'op': 'rule', 'rule': 'classTri'}], 'li': [i]})
            done.add(i)
            i += 1
            continue
        m = re.fullmatch(r'(?P<h>⁅保持称号開放中⁆)?【CAD】(?P<spec>[^(]*?)(?:\(.*\))?', ln)
        if m:
            spec = m.group('spec')
            f = {'magic': 1}
            mm = re.fullmatch(r'(?:(?P<c1>赤|青|白|黒)(?:か(?P<c2>赤|青|白|黒))?(?:で|の))?(?:コスト(?P<n>\d+)(?P<le>以下)?)?(?P<shot>ショットアイコン)?', spec)
            if mm:
                CL = {'赤': 'red', '青': 'blue', '白': 'white', '黒': 'black'}
                if mm.group('c1'):
                    f['color'] = [CL[x] for x in (mm.group('c1'), mm.group('c2')) if x]
                if mm.group('n'):
                    f['costLE' if mm.group('le') else 'costEQ'] = int(mm.group('n'))
                if mm.group('shot'):
                    f['icon'] = 'shot'
                d['cad'] = f
                abs_.append({'k': 'auto', 'on': 'attack', 'src': 'self', 'if': ([{'hold': 1}] if m.group('h') else []) + [{'cadOk': 1}],
                             'do': [{'op': 'playFree', 'from': 'hand', 'f': f, 'may': 1, 'cad': 1}], 'li': [i]})
                done.add(i)
                i += 1
                continue
        m = re.fullmatch(r'⁅永続⁆あなたの「(?P<nm>[^」]+)」を含むユニットの【CAD】で手札からこのカードをプレイする際、このカードはコスト(?P<n>\d+)として扱う。?', ln)
        if m:
            d['cadCost'] = {'name': m.group('nm'), 'n': int(m.group('n'))}
            done.add(i); i += 1; continue
        m = re.fullmatch(r'⁅永続⁆このカードがテリトリーゾーンにあるなら、あなたの「(?P<nm>[^」]+)」を含むエースの【CAD】の指定は『コスト(?P<n>\d+)以下』になる。?', ln)
        if m:
            d['cadBoost'] = {'name': m.group('nm'), 'costLE': int(m.group('n'))}
            done.add(i); i += 1; continue
        m = re.fullmatch(r'⁅永続⁆各ターン1回だけ、このユニットの【CAD】でコマンドを解決した時、このユニットの【CAD】をもう1回使ってよい。?', ln)
        if m and d.get('cad'):
            abs_.append({'k': 'auto', 'on': 'cad', 'src': 'self', 'if': [], 'once': 1, 'do': [{'op': 'playFree', 'from': 'hand', 'f': d['cad'], 'may': 1, 'cad': 1}], 'li': [i]})
            done.add(i); i += 1; continue
        if re.fullmatch(r'⁅永続⁆あなたのテリトリーが開放されていないなら、このユニットの【CAD】は使えない。?', ln):
            d['cadNeedsTerr'] = 1
            done.add(i)
            i += 1
            continue
        if re.fullmatch(r'⁅永続⁆あなたのテリトリー開放中なら、このユニットの【CAD】でプレイする魔法カードは手札とエナジーから選べる。?', ln):
            abs_.append({'k': 'perm', 'if': [{'terr': 1}], 'do': [{'op': 'rule', 'rule': 'cadEnergy'}], 'li': [i]})
            done.add(i)
            i += 1
            continue
        # 【マギア】: 공격 시 에너지 2장을 뒷면으로 해서 발동 / 【マケイン】: 배틀에서 졌을 때 / 【ログ】: 등장 시 덱 위를 뒷면으로 테리토리에
        m = re.fullmatch(r'(?P<h>⁅保持称号開放中⁆)?【(?P<k>マギア|マケイン)】(?:\([^)]*\))?(?P<x>.*)', ln)
        if m:
            k = m.group('k')
            d['magia' if k == 'マギア' else 'makein'] = 1
            body = m.group('x')
            if re.fullmatch(r'以下を1つ(?:選んで)?行う。?', body):
                j = i + 1
                opts = []
                while j < len(lines) and lines[j].startswith('・'):
                    opts.append(parse_effects_lenient(lines[j][1:]))
                    j += 1
                sub = [{'op': 'choose', 'opts': opts}] if opts and all(o is not None for o in opts) else None
                rng = list(range(i, j))
            else:
                _LAST.clear()
                sub = parse_effects_lenient(body) if body else []
                if sub is not None and '$prev' in str(sub):
                    sub = None
                rng = [i]
                j = i + 1
            on = 'attack' if k == 'マギア' else 'lose'
            if sub is not None:
                ab = {'k': 'auto', 'on': on, 'src': 'self', 'if': [{'hold': 1}] if m.group('h') else [], 'do': sub, 'li': rng}
                if k == 'マギア':
                    ab['cost'] = [{'op': 'flipEnergy', 'n': 2, 'inCost': 1}]
                abs_.append(ab)
                done.update(rng)
            else:
                mts.append({'on': on, 'src': 'self', 'if': [], 'li': rng})
            i = j
            continue
        # 【恋愛頭脳戦】: 등장 시 패 1장을 필드에 뒷면으로 둘 수 있음
        if re.fullmatch(r'【恋愛頭脳戦】(?:\(.*\))?', ln):
            d['renai'] = 1
            abs_.append({'k': 'auto', 'on': 'enter', 'src': 'self', 'if': [], 'do': [{'op': 'setHand', 'n': 1, 'may': 1}], 'li': [i]})
            done.add(i)
            i += 1
            continue
        # 뒷면으로 둔 이 카드를 코스트 없이 플레이할 수 있는 때
        m = re.fullmatch(r'(?:(?P<c>[^。]*?)なら、)?伏せられたこのカードは(?P<w>相手エンドフェイズ|自分のメインフェイズ)にコストを払わずプレイできる。?', ln)
        if m:
            c = parse_cond(m.group('c').replace('このターンにあなたがダメージを受けている', 'このターンあなたがダメージを受けている')) if m.group('c') else []
            if c is not None:
                d['setPlay'] = {'when': 'oppEnd' if '相手' in m.group('w') else 'myMain', 'if': c}
                done.add(i)
            i += 1
            continue
        # 【神衣-鮮血】【神衣-純潔】: 내가 플레이한 그 커맨드를 이 유닛에 겹쳐 입힐 수 있음
        m = re.fullmatch(r'((?:【神衣-[^】]+】)+)(?:\(.*\))?', ln)
        if m:
            d['kamui'] = re.findall(r'【神衣-([^】]+)】', m.group(1))
            done.add(i)
            i += 1
            continue
        # 입히는 커맨드: 【鮮血】着ているユニットのパワーを+3000
        m = re.fullmatch(r'【(?P<n>[^】]+)】着ているユニットの(?P<mods>(?:パワー|ヒット)を[+-]\d+(?:、(?:パワー|ヒット)を[+-]\d+)?)。?', ln)
        if m:
            d['dress'] = m.group('n').split('/')
            abs_.append({'k': 'perm', 'if': [], 'do': [{'op': 'pow' if k == 'パワー' else 'hit', 'n': int(v), 'to': 'host'} for k, v in re.findall(r'(パワー|ヒット)を([+-]\d+)', m.group('mods'))], 'li': [i]})
            done.add(i)
            i += 1
            continue
        m = re.fullmatch(r'あなたの(?P<d>[^。]*?)ユニットにこのカードを重ねて着せてよい。?', ln)
        if m and parse_desc(m.group('d')) is not None:
            d['dressAny'] = parse_desc(m.group('d'))
            done.add(i)
            i += 1
            continue
        if re.fullmatch(r'【ログ】(?:\(.*\))?', ln):
            d['log'] = 1
            abs_.append({'k': 'auto', 'on': 'enter', 'src': 'self', 'if': [], 'do': [{'op': 'logAttach', 'may': 1}], 'li': [i]})
            done.add(i)
            i += 1
            continue
        # 【夢を見ない】〔색/속성〕: 공격 시 덱 위 1장을 공개해서 드롭할 수 있고, 지정 색·속성이면 효과 발동
        m = re.fullmatch(r'(?P<h>⁅保持称号開放中⁆)?【夢を見ない】〔(?P<spec>[^〕]+)〕(?:\([^)]*\))?:?(?P<x>.+?)(?:\((?:[^()]|\([^)]*\))*\))?', ln)
        if m:
            d['yumemi'] = 1
            CL = {'赤': 'red', '青': 'blue', '白': 'white', '黒': 'black'}
            parts = m.group('spec').split('か')
            f = {'color': [CL[x] for x in parts if x in CL]} if all(x in CL for x in parts) else {'attr': parts}
            body = m.group('x')
            if re.fullmatch(r'以下を1つ(?:選んで)?行う。?', body):
                j = i + 1
                opts = []
                while j < len(lines) and lines[j].startswith('・'):
                    opts.append(parse_effects_lenient(lines[j][1:]))
                    j += 1
                sub = [{'op': 'choose', 'opts': opts}] if opts and all(o is not None for o in opts) else None
                rng = list(range(i, j))
            else:
                _LAST.clear()
                sub = parse_effects_lenient(body)
                if sub is not None and '$prev' in str(sub):
                    sub = None
                rng = [i]
                j = i + 1
            if sub is not None:
                abs_.append({'k': 'auto', 'on': 'attack', 'src': 'self', 'if': [{'hold': 1}] if m.group('h') else [],
                             'do': [{'op': 'yumemi', 'f': f, 'may': 1}, {'op': 'if', 'c': [{'did': 1}], 'then': sub}], 'li': rng})
                done.update(rng)
            else:
                mts.append({'on': 'attack', 'src': 'self', 'if': [], 'li': rng})
            i = j
            continue
        m = re.fullmatch(r'⁅永続⁆あなたの【夢を見ない】で公開されている(このカード|エースカード)は全ての色を持つ。?', ln)
        if m:
            if m.group(1) == 'このカード':
                d['yumemiAll'] = 1
            else:
                abs_.append({'k': 'perm', 'if': [], 'do': [{'op': 'rule', 'rule': 'yumemiAce'}], 'li': [i]})
            done.add(i)
            i += 1
            continue
        if re.fullmatch(r'⁅永続⁆あなたの【夢を見ない】で公開されているコマンドカードは⁅スペード⁆⁅ハート⁆⁅ダイヤ⁆⁅クラブ⁆として扱う。?', ln):
            abs_.append({'k': 'perm', 'if': [], 'do': [{'op': 'rule', 'rule': 'yumemiCmd'}], 'li': [i]})
            done.add(i)
            i += 1
            continue
        if ln in ('【魔法】',):
            d['magic'] = 1
            done.add(i)
            i += 1
            continue
        m = re.fullmatch(r'⁅永続⁆(?P<t>あなたのテリトリー開放中、)?このカードを含めて「[^」]+」が手札に(?P<n>\d+)枚揃ったら、あなたはそれらを全て公開し、このゲームに勝利する。?', ln)
        if m:
            d['win5'] = {'n': int(m.group('n')), **({'terr': 1} if m.group('t') else {})}
            done.add(i)
            i += 1
            continue
        m = re.fullmatch(r'⁅永続⁆このカードは全(?:ての)?領域でコスト(\d+)になる。?', ln)
        if m:
            d['cost'] = int(m.group(1))
            done.add(i)
            i += 1
            continue
        m = re.fullmatch(r'⁅永続⁆このカードは(?:全(?:ての)?領域で)?称号「([^」]+)」(?:と称号「([^」]+)」)?を持つ。?', ln)
        if m:
            d['titles'] = list(dict.fromkeys((d.get('titles') or []) + [x for x in m.groups() if x]))
            done.add(i)
            i += 1
            continue
        m = re.fullmatch(r'あなたのエナジーが(\d+)色(?:以上)?なら、このカードをプレイする際のコストを(\d+)減らしてプレイできる。?', ln)
        if m:
            d['costRed'] = {'colors': int(m.group(1)), 'by': int(m.group(2))}
            done.add(i)
            i += 1
            continue
        m = re.fullmatch(r'⁅永続⁆このユニットは((?:称号「[^」]+」か?)+)のテリトリー(?:も|を)開放できる。?(?:\(.*\))?', ln)
        if m:
            d['openTitles'] = re.findall(r'「([^」]+)」', m.group(1))
            done.add(i)
            i += 1
            continue
        m = re.fullmatch(r'このカードはデッキに(\d+)枚まで入れられる。?', ln)
        if m:
            d['maxCopies'] = int(m.group(1))
            done.add(i)
            i += 1
            continue
        m = re.fullmatch(r'⁅永続⁆(?:このユニット|このカード)は(?:全(?:ての)?領域で)?(?:カード名を)?「([^」]+)」(?:として|としても)扱う。?(?:\(.*\))?', ln)
        if m:
            d['alias'] = m.group(1)
            done.add(i)
            i += 1
            continue
        if re.fullmatch(r'このカードはデッキに\d+枚より多く入れられる。?', ln):
            d['anyCopies'] = 1
            done.add(i)
            i += 1
            continue
        if re.fullmatch(r'⁅永続⁆あなたは「同じ色のコマンドカード」でも【ブライト】できる。?', ln):
            abs_.append({'k': 'perm', 'if': [], 'do': [{'op': 'rule', 'rule': 'brightCmd'}], 'li': [i]})
            done.add(i)
            i += 1
            continue
        m = re.match(r'【結束:([^】]+)】', ln)
        if m:
            d['kesso'] = m.group(1).split('/')
            done.add(i)
            i += 1
            continue
        # 설명용 줄 (괄호 안 리마인더, 머리말)
        if re.fullmatch(r'\((?:[^()]|\([^)]*\))*\)|0|※.*の効果|アイコン能力', ln) and not (ln == 'アイコン能力' and i + 1 < len(lines) and lines[i + 1].startswith('・')):
            done.add(i)
            i += 1
            continue
        if ln == 'アイコン능력'.replace('능력', '能力'):   # 「アイコン能力」 + ・줄: 상시 효과
            j = i + 1
            pms = []
            while j < len(lines) and lines[j].startswith('・'):
                pms.append(parse_perm(re.sub(r'\([^)]*\)$', '', lines[j][1:]).rstrip('。')))
                j += 1
            if pms and all(pms):
                for pm in pms:
                    abs_.append({'k': 'perm', 'if': pm['if'], 'do': pm['do'], 'li': list(range(i, j))})
                done.update(range(i, j))
            i = j
            continue
        m = re.fullmatch(r'【(デコイ|ブリッツ|バーサーク)】', ln)
        if m:
            abs_.append({'k': 'perm', 'if': [], 'do': [{'op': 'kw', 'kw': {'デコイ': 'decoy', 'ブリッツ': 'blitz', 'バーサーク': 'berserk'}[m.group(1)], 'to': 'self'}], 'li': [i]})
            done.add(i)
            i += 1
            continue
        # 플레이 제한
        m = re.fullmatch(r'このカードは(?P<c>.+?)時にしかプレイできない。?', ln)
        if m:
            c = parse_cond(m.group('c'))
            if c is not None:
                d['playIf'] = c
                done.add(i)
            i += 1
            continue
        m = re.fullmatch(r'(?P<c>[^。]+?)なら、このカードはプレイできない。?', ln)
        if m:
            c = parse_cond(m.group('c'))
            if c is not None:
                d['playNot'] = c
                done.add(i)
            i += 1
            continue
        m = re.fullmatch(r'⁅永(?:続)?⁆あなたの、?(?P<d>[^。]+?)ユニットがアタックしてバトルする際、手札からこのカードをドロップすることで、そのユニットを【ブライト(?P<n>\d+)】させる。?', ln)
        if m and parse_desc(m.group('d')) is not None:
            d['handTrig'] = 1
            abs_.append({'k': 'auto', 'fromHand': 1, 'on': 'battle', 'src': 'own', 'if': [{'evF': dict(parse_desc(m.group('d')), attacking=1)}], 'cost': [{'op': 'discardSelf', 'inCost': 1}],
                         'do': [{'op': 'brightBoost', 'n': int(m.group('n')), 'to': 'evt'}], 'li': [i]})
            done.add(i); i += 1; continue
        if re.fullmatch(r'⁅永続⁆このユニットの【ブライト】はこのユニットが登場した時にも発動できる。?', ln):
            abs_.append({'k': 'auto', 'on': 'enter', 'src': 'self', 'if': [], 'do': [{'op': 'brightSelf'}], 'li': [i]})
            done.add(i); i += 1; continue
        m = re.fullmatch(r'⁅永続⁆あなたはカード名に「(?P<n>[^」]+)」を含むユニットの効果でカードを伏せる事はできない。?', ln)
        if m:
            d['noSetBy'] = m.group('n'); done.add(i); i += 1; continue
        m = re.fullmatch(r'⁅永続⁆このユニットの【恋愛頭脳戦】で手札をフィールドに伏せる際、(?P<c>[^。]+?)なら、あなたのドロップゾーンの(?P<d>[^、。]+?)を手札にあるかのようにフィールドに伏せるカードに選べる。?', ln)
        if m and parse_cond(m.group('c')) is not None and _zdesc(m.group('d')) is not None:
            d['renaiDrop'] = {'c': parse_cond(m.group('c')), 'f': _zdesc(m.group('d'))}; done.add(i); i += 1; continue
        if re.fullmatch(r'「[^」]+」はデッキに1枚しか入れられない。?', ln):
            d['maxCopies'] = 1; done.add(i); i += 1; continue
        if re.fullmatch(r'ゲーム開始時、この面を表にしてテリトリーゾーンに置く。?', ln):
            d['startInTerr'] = 1; done.add(i); i += 1; continue
        if re.fullmatch(r'⁅永続⁆このユニットがフィールドを離れる際、代わりにテリトリーゾーンに置く。?(?:\(.*\))?', ln):
            d['toTerrOnLeave'] = 1; done.add(i); i += 1; continue
        if re.fullmatch(r'⁅永続⁆あなたのテリトリーが無いなら、テリトリーゾーンからこのカードをプレイできる。?(?:\(.*\))?', ln):
            d['playFromTerr'] = 1; done.add(i); i += 1; continue
        if re.fullmatch(r'・アイコン能力.*', ln):
            done.add(i); i += 1; continue
        m = re.fullmatch(r'⁅永続⁆あなたのドロップゾーンから[【⁅]ログ[】⁆]を持つカードが手札に戻る際、代わりにそのカードを登場させてよい。?', ln)
        if m:
            abs_.append({'k': 'perm', 'if': [], 'do': [{'op': 'rule', 'rule': 'logReturnSummon'}], 'li': [i]}); done.add(i); i += 1; continue
        m = re.fullmatch(r'⁅永(?:続)?⁆各ターン1回まで、あなたはコマンドカードを『あなたの⁅神衣⁆を持つユニット1枚をレストする』でもプレイできる。?', ln)
        if m:
            d.setdefault('terrAlt', []).append({'kind': 'restU', 'units': [{'kamui': 1, 'type': 'unit'}], 'once': 1, 'onceKey': 'tA' + str(d.get('id', d.get('jp', ''))), 'f': {'type': 'command'}, 'fText': '神衣'})
            done.add(i); i += 1; continue
        m = re.fullmatch(r'⁅永続⁆各ターン1回まで、あなたがカードをプレイする際、コストを(?P<n>\d+)減らしてプレイでき、あなたのエナジーが4色あるなら、さらに1減らしてプレイできる。ただしコストは1より下にならない。?', ln)
        if m:
            key = 'tR' + str(d.get('id', d.get('jp', '')))
            for nn in range(1, int(m.group('n')) + 1):   # 공식 Q&A: 덜 줄이는 것도 가능
                d.setdefault('terrAlt', []).append({'kind': 'costRed', 'n': nn, 'once': 1, 'onceKey': key})
            d['terrAlt'].append({'kind': 'costRed', 'n': int(m.group('n')) + 1, 'need4': 1, 'once': 1, 'onceKey': key})
            done.add(i); i += 1; continue
        if re.fullmatch(r'⁅永続⁆あなたは『ドロップゾーンから指定属性のカードをリムーブする』でも【ブライト】できる。?', ln):
            abs_.append({'k': 'perm', 'if': [], 'do': [{'op': 'rule', 'rule': 'brightFromDrop'}], 'li': [i]}); done.add(i); i += 1; continue
        if re.fullmatch(r'⁅永続⁆あなたのターン中、あなたは『あなたの手札のコマンドカードを1枚ドロップする。?』でもスキルコストを払える。?', ln):
            abs_.append({'k': 'perm', 'if': [{'myTurn': 1}], 'do': [{'op': 'rule', 'rule': 'skillAltCmd'}], 'li': [i]}); done.add(i); i += 1; continue
        m = re.fullmatch(r'このカードは、(?P<l>称号「[^」]+」(?:、「[^」]+」)+)を持つ。?(?:\(.*\))?', ln)
        if m:
            d['titles'] = list(dict.fromkeys((d.get('titles') or []) + re.findall(r'「([^」]+)」', m.group('l'))))
            done.add(i); i += 1; continue
        m = re.fullmatch(r'⁅自動⁆このテリトリーが開放された時とあなたのユニットがこのターン初めて登場した時、(?P<x>.+)', ln)
        if m:
            body = parse_effects(m.group('x'))
            if body:
                abs_.append({'k': 'auto', 'on': 'terrOpen', 'src': 'me', 'if': [], 'do': body, 'li': [i]})
                abs_.append({'k': 'auto', 'on': 'enter', 'src': 'own', 'if': [{'firstEnterTurn': 1}], 'do': copy.deepcopy(body), 'li': [i]})
                done.add(i)
            i += 1; continue
        m = re.fullmatch(r'(?P<c>[^。]+?)なら、このカードはドロップゾーンからプレイできる。?', ln)
        if m and parse_cond(m.group('c')) is not None:
            d['playFromDrop'] = parse_cond(m.group('c'))
            done.add(i); i += 1; continue
        m = re.fullmatch(r'(?P<k>【[^】]+】)(?:\([^)]*\))?⁅永続⁆このカードは全ての領域でコスト(?P<n>\d+)になる。?', ln)
        if m:
            mk = re.fullmatch(r'【怪異:([^】]+)】', m.group('k'))
            if mk:
                d['costAs'] = {'n': int(m.group('n')), 'c': [{'droppedAttr': mk.group(1).split('/')}]}
                done.add(i); i += 1; continue
        # 대체 플레이 방법
        m = re.fullmatch(r'(?P<once>各ターン1回まで、)?(?:(?P<c>[^。]+?)なら、)?このカードは(?:『(?P<x>[^』]+?)。?』でも|コスト(?P<n>\d+)でも?|コストを払わず(?:に)?)(?:プレイできる|プレイしてよい)。?(?P<r>そうしたら、このユニットはレストで登場する。?)?', ln)
        if m:
            alt = _parse_alt(m.group('x'), m.group('n'))
            c = parse_cond(m.group('c')) if m.group('c') else []
            if alt is not None and c is not None:
                if c:
                    alt['c'] = c
                if m.group('r'):
                    alt['rested'] = 1
                if m.group('once'):
                    alt['once'] = 1
                d.setdefault('alt', []).append(alt)
                done.add(i)
            i += 1
            continue
        if ln.startswith('【スキル】') and skill is not None:
            done.add(i)   # 비용 정의 줄: 다른 줄에서 씀
            i += 1
            continue
        if re.fullmatch(r'\(ライフからトリガーした時、コストを払わずに登場させてよい\)|\(この登場でテリトリー開放はできない\)', ln):
            done.add(i)
            i += 1
            continue
        r = parse_body(ln, d, skill) or parse_body_lenient(ln, d, skill)
        if r:
            r['li'] = [i]
            abs_.append(r)
            done.add(i)
            if r.get('guided'):
                d.setdefault('gl', []).append(i)
        else:
            mt = manual_trigger(ln, d)
            if mt:
                mt['li'] = [i]
                mts.append(mt)
        i += 1
    for j2, k2 in joined.items():   # 이어 붙인 줄은 앞줄과 같이 처리됨
        if k2 in done:
            done.add(j2)
            for r in abs_:
                if k2 in r.get('li', []):
                    r['li'] = sorted(set(r['li']) | {j2})
    # 커맨드의 못 읽은 본문은 한 번에 묶어 플레이할 때 직접 처리
    play = [m for m in mts if m['on'] == 'play']
    if len(play) > 1:
        play[0]['li'] = sorted(sum((m['li'] for m in play), []))
        mts = [m for m in mts if m['on'] != 'play'] + [play[0]]
    # 그래도 못 읽은 줄: 시점을 알면 문장마다 다시 읽음.
    #  - 읽을 수 있는 문장·조건은 자동 (조건은 게임이 판단)
    #  - 못 읽은 문장만 글에서 추정한 처리를 골라 실행 (직접 처리 창은 마지막 수단)
    rest_mts = []
    for mt in mts:
        body = ''.join(lines[i] for i in mt['li'] if i < len(lines))
        body = re.sub(r'^(?:⁅[^⁆]+⁆|【[^】]+】(?:〔[^〕]*〕)?(?:\([^)]*\))?:?)+', '', body)
        if mt['on'] != 'play':
            body = re.sub(r'^[^。]*?時、', '', body, count=1)
        body = re.sub(r'\((?:[^()]|\([^)]*\))*\)', '', body)
        steps, ok, partial = [], True, False
        body = re.sub(r'『[^』]*』', lambda m: m.group(0).replace('。', '＄'), body)
        for sent in [x.replace('＄', '。') for x in body.split('。') if x.strip()]:
            if re.fullmatch(r'この能力は各ターン.*?発動できる', sent):
                continue
            r = parse_effects_lenient(sent)
            if r is not None:
                steps += r
                continue
            # 문장 안의 조건은 게임이 판단(못 하면 물어봄)하고, 나머지만 고르기
            cond, ask_c, rest, pre_steps = None, None, sent, []
            cs = _cond_split(sent)
            if cs:
                pre, cond, ask_c, rest = cs
                if ask_c:
                    ok = False
                    break
                if pre.strip('、'):
                    pre_steps = parse_effects_lenient(pre) or []
            acts = _infer_acts(rest)
            if len(acts) > 7:
                ok = False
                break
            loop = {'op': 'choose', 'loop': 1, 'guide': rest[:60],
                    'opts': [a[1] for a in acts] + [[{'op': 'manualOpen'}], []],
                    'labels': [a[0] for a in acts] + ['다른 처리가 필요해요 (직접 처리 창 열기)', '처리 끝내기'],
                    'text': '이 부분은 자동으로 다 읽지 못했어요. 카드 문구에 맞는 처리를 차례로 고르고, 다 했으면 \'처리 끝내기\'를 누르세요' if acts else '이 부분은 자동으로 처리할 수 없어요. 필요하면 직접 처리 창에서 처리하고, 해당 없으면 \'처리 끝내기\'를 누르세요'}
            if not acts:
                partial = True
            steps += pre_steps
            steps.append({'op': 'if', 'c': cond, 'then': [loop]} if cond else loop)
        if not ok or not steps:
            rest_mts.append(mt)
            continue
        _resolve_prev(steps, [])   # 문장마다 나눠 읽어도 「さらに」 등은 앞 문장의 대상·수정 종류를 이어받음
        _resolve_repeat(steps)
        if '$prev' in json.dumps(steps) or '$repeat' in json.dumps(steps):
            rest_mts.append(mt)
            continue
        if not any(st.get('op') != 'choose' or st.get('opts', [[]])[0] != [{'op': 'manualOpen'}] for st in steps):
            rest_mts.append(mt)   # 처리 후보가 하나도 없으면 직접 처리 그대로
            continue
        ab = {'k': 'play' if mt['on'] == 'play' else 'auto', 'if': mt['if'], 'do': steps, 'li': mt['li'], 'guided': 1, **({'partial': 1} if partial else {})}
        if mt['on'] != 'play':
            ab.update(on=mt['on'], src=mt['src'])
        abs_.append(ab)
        done.update(mt['li'])
        for j2, k2 in joined.items():
            if k2 in mt['li']:
                done.add(j2)
        d.setdefault('pl' if partial else 'gl', []).extend(mt['li'])
    mts = rest_mts
    if mts:
        d['mt'] = mts
    elif 'mt' in d:
        del d['mt']
    for j0, k0 in tmerge:
        if k0 in done:
            done.add(j0)
            for a in abs_:
                if k0 in a.get('li', []):
                    a['li'] = sorted(set(a['li']) | {j0})
    for i0, x in enumerate(lines):
        if i0 in done and x.rstrip('。').endswith('以下の規則を厳守する'):
            j0 = i0 + 1
            while j0 < len(lines) and lines[j0].startswith('・'):
                done.add(j0); j0 += 1
    for a in abs_:
        if a.get('k') != 'auto':
            continue
        txt = ''.join(lines[i] for i in a.get('li', []) if i < len(lines))
        if '手札からこのカードを登場' in txt or ('手札からこのカードをドロップすることで' in txt and a.get('on') == 'battle'):
            a['fromHand'] = 1; d['handTrig'] = 1
        if 'エナジーのこのカード' in txt and a.get('on') not in ('skillDrop',) and a.get('src') != 'self':
            a['fromEnergy'] = 1; d['energyTrig'] = 1
    for a in abs_:
        _fix_summoned(a.get('do') or [])
    return abs_, done


def _is_summon(o):
    if not isinstance(o, dict):
        return False
    op = o.get('op', '')
    return (op in ('pick', 'look') and o.get('to') == 'field') or op.startswith('summon')


def _fix_summoned(seq, st=None):
    """登場させ…そのユニット: 대상을 고른 적 없이 등장시킨 뒤의 'T'는 등장시킨 유닛"""
    st = st or {'tgt': False, 'sum': False}
    for o in seq:
        if not isinstance(o, dict):
            continue
        if o.get('op') == 'tgt' or o.get('into') == 'T':
            st['tgt'] = True
        if st['sum'] and not st['tgt'] and o.get('to') == 'T' and o.get('op') not in ('tgt', 'pick', 'look'):
            o['to'] = 'summoned'
        for k in ('then', 'else', 'do'):
            if isinstance(o.get(k), list):
                _fix_summoned(o[k], dict(st) if k != 'do' or o.get('op') in ('if',) else {'tgt': False, 'sum': False})
        if _is_summon(o):
            st['sum'] = True


def _ko_ask(d, abs_):
    """'조건 묻기' 단계에 한국어 문구의 해당 조건절을 붙임 (몇 번째 조건인지로 맞춤)"""
    ko = d.get('ko') or []
    for r in abs_:
        if not r.get('guided'):
            continue
        line = ' '.join(ko[i] for i in r.get('li', []) if i < len(ko))
        cl = re.findall(r'(?:^|[,.] ?)([^,.]*?(?:라면|다면|이라면|하면|이면|으면|있으면|없으면))(?=,)', line)
        k = [0]
        def walk(seq):
            for st in seq:
                if st.get('op') == 'askIf' and st.get('trig'):
                    mt = re.search(r'^(?:\[[^\]]+\]\s*)*(.*?때),', line)
                    if mt:
                        st['ko'] = mt.group(1).strip()
                elif st.get('op') == 'askIf':
                    if k[0] < len(cl):
                        st['ko'] = re.sub(r'^\s*(?:그 후|그리고|또한)\s*', '', cl[k[0]]).strip()
                    k[0] += 1
                for key in ('then', 'else'):
                    walk(st.get(key) or [])
                for o in st.get('opts') or []:
                    walk(o)
        walk(r.get('do', []))


def manual_trigger(ln, d):
    """자동 처리하지 못한 줄이라도 발동 시점을 알면 그때 '직접 처리' 창을 띄우도록 {on, src, if}"""
    hold = [{'hold': 1}] if '⁅保持称号開放中⁆' in ln else []
    body = re.sub(r'^(?:⁅(?:自動|永続|保持称号開放中|自|永)⁆)+', '', ln).strip()
    if '⁅永続⁆' in ln or ln.startswith('【スキル】') or re.fullmatch(r'\(.*\)', ln):
        return None
    if '⁅自動⁆' in ln or '⁅自⁆' in ln:
        m = re.match(r'(?P<t>(?:あなたの(?:称号「[^」]+」の)?テリトリー(?:が開放されていて|開放中で|が開放中で)、)?[^、]*?時)、', body)
        if m:
            tr = parse_trigger(m.group('t'))
            if tr:
                return {'on': tr[0], 'src': tr[1], 'if': hold + tr[2]}
            h = m.group('t')
            if 'このユニット' in h and '登場' in h:
                return {'on': 'enter', 'src': 'self', 'if': hold}
            if 'このユニット' in h and 'アタック' in h and '終了' not in h:
                return {'on': 'attack', 'src': 'self', 'if': hold}
            if 'このユニット' in h and 'フィールドからドロップ' in h:
                return {'on': 'leave', 'src': 'self', 'if': hold}
        return None
    # 작품 고유 키워드: 괄호 설명으로 시점을 판단
    if body.startswith('【'):
        if re.search(r'\(登場時', body):
            return {'on': 'enter', 'src': 'self', 'if': hold}
        if re.search(r'\(アタック時|アタック時、', body) or body.startswith('【CAD】') or body.startswith('【マギア】'):
            return {'on': 'attack', 'src': 'self', 'if': hold}
        if re.search(r'バトルに負けた時', body):
            return {'on': 'lose', 'src': 'self', 'if': hold}
        if re.search(r'エンドフェイズ', body) and body.startswith('【コスプレ'):
            return {'on': 'endStart', 'src': 'me', 'if': hold + [{'terr': 1}]}
        if d.get('type') != 'command':
            return None
    if d.get('type') == 'command':
        return {'on': 'play', 'src': 'self', 'if': []}
    return None


def parse_body_lenient(ln, d, skill):
    """엄격히 못 읽은 줄: 모르는 조건은 묻고, 모르는 효과는 처리 방법을 고르게 해서라도 자동 진행"""
    _LEN['on'] = True
    try:
        r = parse_body(ln, d, skill)
    finally:
        _LEN['on'] = False
    if r:
        r['guided'] = 1
    return r


def parse_effects_lenient(t):
    r = parse_effects(t)
    if r is not None:
        return r
    _LEN['on'] = True
    try:
        return parse_effects(t)
    finally:
        _LEN['on'] = False


def parse_body(ln, d, skill):
    _LAST.clear()
    r = _parse_body(ln, d, skill)
    if r and ('$prev' in str(r) or '$repeat' in str(r)):
        return None   # 앞 대상을 끝내 찾지 못함
    return r


def _parse_body(ln, d, skill):
    gk = False
    m0 = re.match(r'^((?:⁅保持称号開放中⁆)?)【相棒】⁅(ハート|スペード|ダイヤ|クラブ)⁆(?:\([^)]*\))?', ln)
    if m0:   # 相棒: 내 다른 지정 속성 유닛이 있으면 유효
        d['aibou'] = m0.group(2)
        r = _parse_body2(m0.group(1) + ln[m0.end():], d, skill)
        if r:
            r['if'] = r.get('if', []) + [{'exists': {'side': 'own', 'attr': [m0.group(2)], 'notSelf': 1, 'type': 'unit'}}]
        return r
    m = re.match(r'^((?:⁅保持称号開放中⁆)?)【(我駆力|INTERNET[34]\.0|特記事項(\d+)|怪異:([^】]+)|境界-([^】]+))】(?:\([^)]*\))?', ln)
    kc = None
    if m:   # 조건이 맞을 때만 유효한 작품 키워드
        gk = m.group(2)
        if gk == '我駆力':
            d['gaku'] = 1; kc = {'dmgTurn': 1}               # 이번 턴 어느 플레이어든 데미지
        elif gk.startswith('INTERNET'):
            d['net3'] = 1; kc = {'net3': 4 if '4.0' in gk else 1}   # 레스트한 에너지 3색(4.0은 4색) 이상
        elif gk.startswith('特記事項'):
            d['tokki'] = int(m.group(3)); kc = {'countGE': {'zone': 'drop', 'f': {'type': 'command'}, 'n': int(m.group(3))}}
        elif gk.startswith('怪異'):
            d['kaii'] = m.group(4).split('/'); kc = {'droppedAttr': m.group(4).split('/')}   # 이번 턴 내 해당 속성 카드가 드롭
        else:
            CL = {'赤': 'red', '青': 'blue', '白': 'white', '黒': 'black'}
            cols = [CL[c] for c in m.group(5) if c in CL]
            d['kyokai'] = m.group(5); kc = {'energyEach': {'colors': cols, 'n': 2}} if cols else {'energyColorsEq': 2}
        ln = m.group(1) + ln[m.end():]
    r = _parse_body2(ln, d, skill)
    if r and kc:
        r['if'] = r.get('if', []) + [kc]
    return r


def _parse_body2(ln, d, skill):
    ln = re.sub(r'\((?:[^()]*)\)$', '', ln).strip()   # 끝의 괄호 설명문(리마인더) 제거
    mtag = re.match(r'^(?:⁅(?:自動|永続|保持称号開放中|自|永)⁆)+', ln)
    tags = re.findall(r'⁅(自動|永続|保持称号開放中|自|永)⁆', mtag.group(0)) if mtag else []
    body = ln[mtag.end():].strip() if mtag else ln.strip()
    conds = [{'hold': 1}] if '保持称号開放中' in tags else []
    body, once = split_once(body)
    if '永続' in tags or '永' in tags:
        pm = parse_perm(body.rstrip('。'))
        if not pm and re.match(r'[^。]*?時、', body) and '⁅' not in body:   # 영속 표기지만 '~時' 자동 능력
            return _parse_body2('⁅自動⁆' + body, d, skill)
        if not pm:
            return None
        return {'k': 'perm', 'if': conds + pm['if'], 'do': pm['do']}
    if not any(t in tags for t in ('自動', '自', '永続', '永')) and d.get('type') == 'unit' and re.match(r'[^。]{0,60}?時、', body) and not body.startswith('『'):
        tags = tags + ['自動']
    if ('自動' in tags or '自' in tags) and not re.search(r'時、', body):
        pm = parse_perm(re.sub(r'^あなたのテリトリー開放中、', 'あなたのテリトリー開放中なら、', body).rstrip('。'))
        if pm:
            return {'k': 'perm', 'if': conds + pm['if'], 'do': pm['do']}
    if '自動' in tags or '自' in tags:
        m = re.match(r'(?P<t>(?:あなたの(?:称号「[^」]+」の)?テリトリー(?:が開放されていて|開放中で|が開放中で)、|(?:あなたのターン中|スキルコストで)、)?[^、]*?時)、', body)
        tr = parse_trigger(m.group('t')) if m else None
        if not tr:   # 「、」가 들어간 발동 조건: 앞에서부터 「時、」마다 시험
            for mm in re.finditer(r'時、', body):
                t2 = body[:mm.start() + 1]
                if len(t2) > 90:
                    break
                tr2 = parse_trigger(t2) or parse_trigger(re.sub(r'中に、', '中に', t2))
                if tr2:
                    m = re.match(re.escape(t2) + '、', body)
                    m = type('M', (), {'group': lambda self, k=0, _t=t2: _t if k == 't' else _t + '、', 'end': lambda self, _n=len(t2) + 1: _n})()
                    tr = tr2
                    break
        if not m:
            return None
        if not tr:
            tr = parse_trigger(m.group('t'))
        if not tr:
            _FAIL['at'] = 'TRIG:' + m.group('t')
            ap = _approx_trigger(m.group('t')) if _LEN['on'] else None
            if ap and ap[3]:
                ap = None   # 발동 시점을 정확히 못 읽으면 묻지 않음
            mt = manual_trigger(ln, d) if _LEN['on'] and not ap else None
            if ap:
                tr = (ap[0], ap[1], ap[2], {'approx': m.group('t')} if ap[3] else None)
            elif mt:
                tr = (mt['on'], mt['src'], [c for c in mt['if'] if c != {'hold': 1}], None)
            else:
                return None
        on, src, tc, extra = tr
        rest = body[m.end():]
        pre_ask = None
        mcnd = re.match(r'(?P<c>[^、。]*?)なら、(?=【スキル】)', rest)
        if mcnd:
            cc = parse_cond(mcnd.group('c'))
            if cc is None:
                return None
            tc = tc + cc
            rest = rest[mcnd.end():]
        cost = None
        mc = re.match(r'(?P<c>[^。]*?)(?:ことで|事で|で)、', rest)
        if mc:
            cost = parse_cost(mc.group('c'), skill)
            if cost:
                rest = rest[mc.end():]
            elif '【スキル】' in mc.group('c'):
                if not (_LEN['on'] and skill):
                    return None
                cost = skill
                rest = rest[mc.end():]
        if rest.startswith('【スキル】発動で、') or rest.startswith('【スキル】を発動することで、'):
            if not skill:
                return None
            cost = skill
            rest = rest.split('、', 1)[1]
        if rest.endswith('__CHOOSE__'):
            pre = rest[:-len('__CHOOSE__')]
            mc2 = re.fullmatch(r'(?P<c>[^、。]+?)なら、', pre)
            if mc2:
                cc = parse_cond(mc2.group('c'))
                if cc is not None:
                    steps = [{'op': 'if', 'c': cc, 'then': [{'op': 'choose'}]}]
                else:
                    steps = None
            else:
                steps = (parse_effects(pre) if pre else [])
                steps = None if steps is None else steps + [{'op': 'choose'}]
        else:
            steps = parse_effects(rest)
        if steps is None:
            return None
        r = {'k': 'auto', 'on': on, 'src': src, 'if': conds + tc, 'do': steps}
        if extra and extra.get('any'):
            r['any'] = 1
        if cost:
            r['cost'] = cost
        if once:
            r['once'] = 1
        return r
    # 태그 없음: 커맨드 본문
    if d.get('type') != 'command':
        return None
    if body.endswith('__CHOOSE__'):
        pre = body[:-len('__CHOOSE__')]
        steps = parse_effects(pre) if pre else []
        if steps is None:
            return None
        return {'k': 'play', 'if': [], 'do': steps + [{'op': 'choose'}]}
    steps = parse_effects(body)
    if steps is None:
        return None
    return {'k': 'play', 'if': [], 'do': steps}
