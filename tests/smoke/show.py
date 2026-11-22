import json,sys
r=json.load(open(f'/tmp/sm/r{sys.argv[1]}.json'))
for x in r.get('miss',[])+r.get('cost',[]):
    print(x['k'],x['name'][:18],x.get('miss','COST'),'|',x['txt'][:150])
    print('     →',' / '.join(x['log'][-3:])[:230])
