// Temporary contract mirror; parent replaces from backend schema before final validation.
export type Fact={name:string,value:string};
export type Item={id:string,kind:'role'|'execution'|'task'|'alarm'|'incident'|'diagnostic',label:string,station:string,facts:Fact[],attention:boolean,acknowledge_id:string|null};
export type Snapshot={cursor:string,generated_at:number,native_write_enabled:false,source_mode:'synthetic'|'approved-local',connection_quality:string,items:Item[]};
