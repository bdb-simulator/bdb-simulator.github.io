const {Engine,DEFS,U,C,base,run,auto,L}=require('./h.js');
let s=base('7059'); const p=s.active,o=1-p; s.players[o].territory.open=true; s.field.push(U('7156',o,{uid:'ST',rested:true}),U('7153',o,{uid:'SE'}),U('7150',o,{uid:'X'}),U('7130',o,{uid:'Y2'}));
s=run(s,p,'7170',0); console.log(s.pending?.cands, s.field.map(u=>u.uid+':'+Engine.hasKw(s,u,'cmdImmune')));
