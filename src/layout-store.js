export class LayoutStore {
  key=null;nodes=[];byId=new Map();
  ensure(ref,create){const key=JSON.stringify(ref);if(this.key===key)return false;
    this.nodes=create();this.byId=new Map(this.nodes.map(n=>[n.id,n]));this.key=key;return true;}
}
