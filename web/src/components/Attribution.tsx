import type { Attributed } from "../api";

export function Attribution({ a }: { a: Attributed }) {
  return (
    <span className="text-xs text-neutral-500">
      {a.url ? (
        <a href={a.url} target="_blank" rel="noreferrer" className="underline">
          {a.source}
        </a>
      ) : (
        a.source
      )}
      {a.license ? ` · ${a.license}` : ""}
    </span>
  );
}

export function SourceLine({ text }: { text: string }) {
  return <p className="mt-2 text-xs text-neutral-500">Source: {text}</p>;
}
