// GENERATED from backend Pydantic models. Do not edit.
// Regenerate: .venv/bin/python scripts/generate_schema.py
export type Acknowledgement = {
  "occurrence_id": string;
  "position": "operator";
};

export type Fact = {
  "name": string;
  "value": string;
};

export type History = {
  "cursor": string;
  "entries": Array<HistoryEntry>;
  "semantics": "historical evidence; bounded excerpt, not current state or verified progress";
  "ordering": "per-identity retained order; cross-source ordering uncertain";
};

export type HistoryEntry = {
  "id": string;
  "item_id": string;
  "label": string;
  "observed_at": number | null;
  "facts": Array<Fact>;
};

export type Item = {
  "id": string;
  "kind": "role" | "execution" | "task" | "alarm" | "incident" | "diagnostic";
  "label": string;
  "station": string;
  "facts": Array<Fact>;
  "attention": boolean;
  "acknowledge_id": string | null;
};

export type Login = {
  "token": string;
};

export type Session = {
  "csrf": string;
  "permissions": Array<"viewer" | "operator">;
  "controller_connected": false;
};

export type Snapshot = {
  "cursor": string;
  "generated_at": number;
  "native_write_enabled": false;
  "source_mode": "synthetic" | "approved-local";
  "connection_quality": string;
  "items": Array<Item>;
};
