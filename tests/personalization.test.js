import {test} from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs/promises';
import {DataStore} from '../src/data-store.js';
import {LayoutStore} from '../src/layout-store.js';
import {presentation} from '../src/presentation.js';
const root=new URL('../',import.meta.url);
const fetchFile=async path=>({ok:true,json:async()=>JSON.parse(await fs.readFile(new URL(path,root),'utf8'))});
const choose=(id='DEMO001',role='teacher',scenario='mixed_evidence')=>({role,subject:{type:'student',id},scenario});
test('joins personal facts and isolates role advice without modifying frozen public records',async()=>{
 const calls=[];const store=new DataStore(async path=>{calls.push(path);return fetchFile(path);});await store.initialize();
 const before=JSON.stringify(store.graph),teacher=await store.select(choose());const count=calls.length;
 const student=await store.select(choose('DEMO001','student'));
 assert.equal(calls.length,count);assert.deepEqual(teacher.nodes.map(n=>n.status),student.nodes.map(n=>n.status));
 assert.ok(teacher.nodes.every(n=>n.sidebar_info.recommendations.every(r=>r.audience==='teacher')));
 assert.ok(student.nodes.every(n=>n.sidebar_info.recommendations.every(r=>r.audience==='student')));
 assert.equal(JSON.stringify(store.graph),before);assert.ok(Object.isFrozen(store.graph.nodes[0]));
 assert.equal(student.nodes.find(n=>n.id==='C05').status.learning_progress,.6);
 assert.equal(student.nodes.find(n=>n.id==='C05').status.coverage_rate,.5);
 assert.equal(student.nodes.find(n=>n.id==='C05.K05').status.learning_state,'not_started');
});
test('course totals never fill knowledge scores and individual scores differ from class presets',async()=>{
 const store=new DataStore(fetchFile);await store.initialize();const person=await store.select(choose());
 const cls=await store.select({role:'teacher',subject:{type:'class',id:store.registry.classes[0].class_id},scenario:'mixed_evidence'});
 assert.notEqual(person.nodes.find(n=>n.id==='C05').status.achievement_rate,cls.nodes.find(n=>n.id==='C05').status.achievement_rate);
 const totals=await store.select(choose('DEMO001','student','course_totals_only'));
 assert.ok(totals.nodes.filter(n=>n.level==='L3_Knowledge').every(n=>n.status.achievement_rate===null&&n.status.health_color==='grey'));
 await assert.rejects(()=>store.select(choose('DEMO040')),/尚未开放/);
});
test('late object responses cannot overwrite the final selection',async()=>{
 let release;const gate=new Promise(r=>release=r);
 const store=new DataStore(async path=>{if(path.includes('snapshots/student/DEMO001/'))await gate;return fetchFile(path);});
 await store.initialize();const slow=store.select(choose());const fast=await store.select(choose('DEMO002'));release();
 assert.equal(await slow,null);assert.equal(store.current,fast);assert.equal(fast.profile.student_id,'DEMO002');
});
test('rejects stale or foreign snapshots; failed reads can be retried',async()=>{
 let wrong=true;
 const store=new DataStore(async path=>{const r=await fetchFile(path),data=await r.json();if(wrong&&path.includes('snapshots/student/DEMO001/'))data.subject.id='DEMO002';return {ok:true,json:async()=>data};});
 await store.initialize();await assert.rejects(()=>store.select(choose()),/对象或版本/);assert.equal(store.current,null);
 wrong=false;store.invalidateSelected(choose());await store.select(choose());assert.equal(store.current.profile.student_id,'DEMO001');
});
test('missing node result shows an unknown state without borrowing class scores or stale advice',async()=>{
 const store=new DataStore(async path=>{const response=await fetchFile(path),value=await response.json();if(path.includes('snapshots/student/DEMO001/'))delete value.node_results.C05;return {ok:true,json:async()=>value};});
 await store.initialize();const view=await store.select(choose());const node=view.nodes.find(n=>n.id==='C05');
 assert.equal(node.status.achievement_rate,null);assert.equal(node.status.health_color,'grey');assert.equal(node.sidebar_info.recommendations.length,0);
 assert.ok(!view.summary.provisional_low_node_ids.includes('C05'));
});
test('advice based on a different profile revision never becomes the current projection',async()=>{
 const store=new DataStore(async path=>{const response=await fetchFile(path),value=await response.json();if(path.includes('recommendations/DEMO001/'))value.basis_profile_version=99;return {ok:true,json:async()=>value};});
 await store.initialize();await assert.rejects(()=>store.select(choose()),/已过期/);assert.equal(store.current,null);
});
test('layout object identity, fixed coordinates and velocity survive subject projection changes',()=>{
 const layout=new LayoutStore();const ref={graph_id:'g',graph_version:1};let count=0;
 const make=()=>{count++;return [{id:'C05',x:7,y:8,fx:7,fy:8,vx:0,vy:0}];};
 assert.ok(layout.ensure(ref,make));const node=layout.byId.get('C05');assert.equal(layout.ensure(ref,make),false);
 assert.equal(count,1);assert.equal(layout.byId.get('C05'),node);assert.equal(node.fx,7);
});
test('risk presentation keeps grey fill for zero/provisional grades and never treats null as zero',()=>{
 const node={level:'L2_Course',status:{health_color:'grey',score_is_provisional:true,achievement_rate:0}};
 assert.ok(presentation(node,'diagnosis',{yellow_min:60}).risk);
 assert.equal(presentation(node,'diagnosis',{yellow_min:60}).fill,'#cbd5d9');
 assert.equal(presentation({...node,status:{...node.status,achievement_rate:null}},'diagnosis',{yellow_min:60}).risk,false);
 assert.equal(presentation(node,'structure',{yellow_min:60}).risk,false);
});
