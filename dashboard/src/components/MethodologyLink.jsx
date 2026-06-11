import Link from "next/link";

/**
 * Uniform per-section pointer to the Methodology tab, which reproduces the
 * pipeline-written method notes verbatim. `anchor` is a key of data.methods.
 */
export default function MethodologyLink({ anchor }) {
  const href = anchor
    ? `/?tab=methodology#method-${anchor}`
    : "/?tab=methodology";
  return (
    <p className="mt-4 text-xs text-slate-500">
      Full computation details:{" "}
      <Link href={href} className="underline">
        Methodology tab
      </Link>
      .
    </p>
  );
}
