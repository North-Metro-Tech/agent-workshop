// Adapted from Pixel Agents webview-ui/src/office/projection.ts at
// d1e007a9fdf3003c252d2973abe1999ae59aec33 (MIT, copyright 2026 Pablo De Lucca).
// See /THIRD_PARTY_NOTICES.md. Only pure coordinate projection retained.
const TILE_SIZE=16;
export function mapOffset(width:number,height:number,cols:number,rows:number,zoom:number,panX=0,panY=0){
  const mapW=cols*TILE_SIZE*zoom,mapH=rows*TILE_SIZE*zoom;
  return {offsetX:Math.floor((width-mapW)/2)+Math.round(panX),offsetY:Math.floor((height-mapH)/2)+Math.round(panY)};
}
export function overlayProjection(layout:{cols:number;rows:number},rect:{width:number;height:number},zoom:number,pan:{x:number;y:number},dpr:number){
  const canvasW=Math.round(rect.width*dpr),canvasH=Math.round(rect.height*dpr);
  const {offsetX,offsetY}=mapOffset(canvasW,canvasH,layout.cols,layout.rows,zoom,pan.x,pan.y);
  return {toScreenX:(x:number)=>(offsetX+x*zoom)/dpr,toScreenY:(y:number)=>(offsetY+y*zoom)/dpr,viewportWorldWidth:canvasW/zoom,viewportWorldHeight:canvasH/zoom,toWorldLength:(px:number)=>(px*dpr)/zoom};
}
