# 키가 '어딘가'가 아니라 처리 함수 안에서 실제로 쓰이는지 확인 (조건 → condOk/condHolds, 필터 → defMatches/unitMatches, op → execStep case)
import json, re
H='/home/claude/bdb-simulator/simulator/index.html'; code=open(H,encoding='utf-8').read()
K=json.load(open('/tmp/keys.json'))
def body(name):
    i=code.index('function '+name+'('); depth=0; j=code.index('{',i)
    for k in range(j,len(code)):
        if code[k]=='{': depth+=1
        elif code[k]=='}':
            depth-=1
            if depth==0: return code[j:k]
cond_body=body('condOk')+body('condHolds')
match_body=body('defMatches')+body('unitMatches')
step_body=body('execStep') if 'function execStep(' in code else code
print('== condOk에 case가 없는 조건 키')
for k,c in sorted(K['conds'].items()):
    if f"case '{k}'" not in cond_body and not re.search(r"\b"+re.escape(k)+r"\b",cond_body): print(' ',k,len(c),c[:6])
print('== defMatches/unitMatches가 안 읽는 필터 키')
for k,c in sorted(K['filt'].items()):
    if not re.search(r"f\??\."+re.escape(k)+r"\b|\['"+re.escape(k)+r"'\]|'"+re.escape(k)+"'",match_body): print(' ',k,len(c),c[:6])
