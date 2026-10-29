export const palette={green:'#5b9d87',yellow:'#d5b56c',red:'#cf7b70',grey:'#cbd5d9'};
const structure={L1_Ability:'#ad9bc4',L2_Course:'#5e9997',L3_Knowledge:'#a2bec6'};
export function presentation(node,mode,policy){
  const s=node.status;
  const risk=mode==='diagnosis'&&s.health_color==='grey'&&s.score_is_provisional&&Number.isFinite(s.achievement_rate)&&s.achievement_rate<policy.yellow_min;
  const pending=mode==='diagnosis'&&s.health_color==='grey';
  return {fill:mode==='structure'?structure[node.level]:palette[s.health_color],risk,
    stroke_style:{color:risk?'#df743e':pending?'#aabcc1':'#ffffff',width:risk?3:2,dasharray:risk?'5 3':pending?'3 3':null}};
}
