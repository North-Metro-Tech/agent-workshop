import type {Projection,ViewItem} from './projection';
import {isUnacknowledged} from './projection';
export type Intent={type:'select',id:string}|{type:'navigate',station:string};
export type SceneNode={readonly item:ViewItem;readonly x:number;readonly y:number;readonly unacknowledged:boolean};
export function SceneAdapter(snapshot:Projection,station:string|null=null):readonly SceneNode[]{
  const items=station===null?snapshot.items:snapshot.items.filter(i=>i.station===station);
  return Object.freeze(items.map((item,n)=>Object.freeze({item,x:16+(n%3)*144,y:24+Math.floor(n/3)*78,unacknowledged:isUnacknowledged(item)})));
}
export function selectionIntent(nodes:readonly SceneNode[],index:number):Intent|null {const n=nodes[index];return n?{type:'select',id:n.item.id}:null;}
