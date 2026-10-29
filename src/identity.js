const $=s=>document.querySelector(s);
function fill(select,students){select.replaceChildren(...students.map(s=>{const o=document.createElement('option');o.value=s.student_id;o.textContent=`${s.display_name} · ${s.student_number}`;return o;}));}
export function selection(store){return {role:$('#role').value,subject:$('#person').value==='class'?{type:'class',id:store.registry.classes[0].class_id}:{type:'student',id:$('#person').value},scenario:$('#scenario').value};}
export function setupIdentity(store,load,diagnose){
 const populate=(role,previous)=>{fill($('#person'),store.students);if(role==='teacher'){const o=document.createElement('option');o.value='class';o.textContent='班级整体概览';$('#person').prepend(o);}$('#person').value=[...$('#person').options].some(o=>o.value===previous)?previous:role==='teacher'?'class':'DEMO001';};
 fill($('#entry-student'),store.students);populate('teacher');
 $('#enter-teacher').onclick=()=>{const previous=$('#person').value;$('#role').value='teacher';populate('teacher',previous);$('#entry').close();load();};
 $('#choose-student').onclick=()=>{$('#identity-step').hidden=false;$('#entry-student').value=$('#person').value==='class'?'DEMO001':$('#person').value;};
 $('#enter-student').onclick=()=>{$('#role').value='student';populate('student',$('#entry-student').value);diagnose();$('#entry').close();load();};
 $('#entry').addEventListener('cancel',e=>{if(!store.current)e.preventDefault();});
 $('#change-role').onclick=()=>$('#entry').showModal();
 $('#role').onchange=()=>{const previous=$('#person').value;populate($('#role').value,previous);if($('#role').value==='student')diagnose();load();};
 $('#person').onchange=load;$('#entry').showModal();
}
