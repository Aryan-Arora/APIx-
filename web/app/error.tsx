"use client";
export default function ErrorPage({
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  return (
    <main className="state error">
      <h1>The dashboard could not be displayed.</h1>
      <p>
        Try loading the page again. No replacement data has been substituted.
      </p>
      <button className="button primary" onClick={reset}>
        Try again
      </button>
    </main>
  );
}
