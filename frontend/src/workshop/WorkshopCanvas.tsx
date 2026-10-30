import {useEffect,useRef,useState} from 'react';
import {overlayProjection} from '../scene/geometry';
import {drawPixels,technician} from '../scene/pixels';
import {SceneAdapter,selectionIntent,type Intent,type SceneNode} from './SceneAdapter';
import type {Projection,ViewItem} from './projection';
export function canvasDetailLines(item:ViewItem|undefined):string[]{return item?[item.label,`Identity: ${item.id}`,`${item.kind} · Station: ${item.station}`,...item.facts.map(f=>`${f.name}: ${f.value}`)]:[];}
function wrapLines(lines:readonly string[]):string[]{return lines.flatMap(line=>line.split('\n').flatMap(part=>part.match(/.{1,64}/gu)??['']));}
export function drawWorkshop(ctx:CanvasRenderingContext2D,nodes:readonly SceneNode[],selected:string|null,width:number,height:number,detailLines:readonly string[]=[]){
 ctx.clearRect(0,0,width,height);ctx.fillStyle='#20252a';ctx.fillRect(0,0,width,height);
 const visible=nodes.slice(0,96);
 const sceneHeight=Math.max(180,Math.ceil(visible.length/3)*80+40);
 const project=overlayProjection({cols:28,rows:Math.ceil(visible.length/3)*5+2},{width,height:sceneHeight},1,{x:0,y:0},1);
 ctx.font='11px monospace';
 for(const node of visible){
  const x=project.toScreenX(node.x),y=project.toScreenY(node.y);
  ctx.strokeStyle=node.item.attention?'#e2b76d':'#626a71';ctx.strokeRect(x-5,y-15,137,72);
  if(node.item.kind==='execution'||node.item.kind==='role')drawPixels(ctx,technician,x,y,2);
  else{ctx.fillStyle='#91999e';ctx.fillRect(x,y+2,16,10);}
  ctx.fillStyle='#e7e9eb';ctx.fillText(node.item.label.slice(0,17),x+22,y+5);ctx.fillText(node.item.station.slice(0,20),x,y+35);
  if(node.unacknowledged){ctx.fillStyle='#e2b76d';ctx.fillText('◆ UNACK',x+22,y+20);}
  if(node.item.id===selected){ctx.strokeStyle='#f3f5f7';ctx.strokeRect(x-7,y-17,141,76);}
 }
 ctx.fillStyle='#e7e9eb';
 detailLines.forEach((line,n)=>ctx.fillText(line,12,sceneHeight+20+n*16));
}
export function WorkshopCanvas({snapshot,station,selected,reducedMotion,onIntent}:{snapshot:Projection;station:string|null;selected:string|null;reducedMotion:boolean;onIntent:(intent:Intent)=>void}){
 const canvas=useRef<HTMLCanvasElement>(null);const [active,setActive]=useState(0);
 const nodes=SceneAdapter(snapshot,station);
 const detailLines=wrapLines(canvasDetailLines(snapshot.items.find(i=>i.id===selected))).slice(0,80);
 const height=Math.max(180,Math.ceil(Math.min(nodes.length,96)/3)*80+40)+(detailLines.length?detailLines.length*16+32:0);
 useEffect(()=>{const ctx=canvas.current?.getContext('2d');if(ctx)drawWorkshop(ctx,nodes,selected,448,height,detailLines);},[snapshot,station,selected,height]);
 function choose(index:number){const i=selectionIntent(nodes,index);if(i)onIntent(i);}
 return <section aria-labelledby="scene-heading"><h2 id="scene-heading">Workshop / spatial overview</h2><p>Stationary, evidence-assigned figures; no travel or progress inferred. {reducedMotion?'Reduced motion: stationary unacknowledged markers.':''}</p><canvas ref={canvas} width={448} height={height} role="img" aria-label="Workshop station layout. Every figure and fact is available in the adjacent keyboard list."/><div role="listbox" aria-label="Scene items" tabIndex={0} aria-activedescendant={nodes.length?`scene-choice-${Math.min(active,nodes.length-1)}`:undefined} onKeyDown={event=>{
 const limit=nodes.length-1;if(limit<0)return;
 if(['ArrowRight','ArrowDown','ArrowLeft','ArrowUp','Home','End'].includes(event.key)){event.preventDefault();setActive(n=>event.key==='Home'?0:event.key==='End'?limit:Math.max(0,Math.min(limit,n+(['ArrowRight','ArrowDown'].includes(event.key)?1:-1))));}
 if(event.key==='Enter'||event.key===' '){event.preventDefault();choose(Math.min(active,limit));}
 }}>{nodes.map((node,n)=><div key={node.item.id} id={`scene-choice-${n}`} role="option" aria-selected={node.item.id===selected}><button tabIndex={-1} onClick={()=>{setActive(n);choose(n);}}>{node.item.kind}: {node.item.label} · {node.item.station}{node.unacknowledged?' · ◆ UNACKNOWLEDGED':''}</button></div>)}</div><p>Canvas shows at most 96 figures and an 80-line selected-detail excerpt. Complete same-snapshot facts and local actions are in the DOM roster, detail and operator panel below; no item is removed from that hierarchy.</p></section>;
}
