import type {HistoryEntry} from './generated';
import type {Immutable} from './projection';
export type Observation=Immutable<HistoryEntry>;
export function Timeline({observations,historyExcerptCursor=null}:{observations:readonly Observation[];historyExcerptCursor?:string|null}){
 return <section aria-labelledby="timeline-heading">
  <h2 id="timeline-heading">Retained diagnostic history</h2>
  <p>Historian excerpt cursor: <code data-history-cursor>{historyExcerptCursor??'not loaded'}</code></p>
  <p>Historian-backed historical evidence; bounded excerpt of at most 100 entries, not current alarms or verified progress. Per-identity retained order; cross-source ordering uncertain. Missing occurrence or acquisition timestamps remain unknown. No transcript or native filesystem browser.</p>
  {!observations.length&&<p>No retained evidence loaded. This is not proof of no activity.</p>}
  <ol>{observations.map(o=><li key={o.id} data-history-id={o.id}>
   <details><summary>{o.label} · {o.item_id} · historical occurrence: {o.observed_at??'unknown'}</summary>
    <p>Retained identity: <code>{o.id}</code></p>
    <dl>{o.facts.map((f,n)=><div key={n}><dt>{f.name}</dt><dd>{f.value}</dd></div>)}</dl>
   </details>
  </li>)}</ol>
 </section>;
}
