// drawPixels adapts getCachedSprite's opaque-pixel raster loop from Pixel Agents
// webview-ui/src/office/sprites/spriteCache.ts, d1e007a9fdf3003c252d2973abe1999ae59aec33.
// MIT, copyright 2026 Pablo De Lucca. See /THIRD_PARTY_NOTICES.md.
// Changed: direct drawing, immutable sprites, no DOM cache or upstream assets.
export type Sprite=readonly (readonly string[])[];
export function drawPixels(ctx:CanvasRenderingContext2D,sprite:Sprite,x:number,y:number,zoom:number){
  ctx.imageSmoothingEnabled=false;
  for(let r=0;r<sprite.length;r++) for(let c=0;c<sprite[r].length;c++){
    const color=sprite[r][c];if(color==='')continue;
    ctx.fillStyle=color;ctx.fillRect(x+c*zoom,y+r*zoom,zoom,zoom);
  }
}
// Original Workshop pixel technician art, drawn as code; no upstream artwork.
const palette:Record<string,string>={'.':'','h':'#c0b5a6','v':'#343a40','s':'#91999e','b':'#555f68'};
export const technician:Sprite=Object.freeze(['..hhhh..','..hvvh..','..hhhh..','.ssssss.','ssbbbbss','.sbbbbs.','..bbbb..','..b..b..','..v..v..'].map(row=>Object.freeze([...row].map(c=>palette[c]??''))));
