import type { ReactNode } from "react";

export function Loading() {
  return <p className="muted">Loading...</p>;
}

export function ErrorPanel({ message }: { message: string }) {
  return (
    <div className="panel empty">
      <h2>Something went wrong</h2>
      <p>{message}</p>
    </div>
  );
}

export function PageHead({ title, sub, children }: { title: string; sub: string; children?: ReactNode }) {
  return (
    <div className="head">
      <div>
        <h1>{title}</h1>
        <p className="sub">{sub}</p>
      </div>
      {children}
    </div>
  );
}
