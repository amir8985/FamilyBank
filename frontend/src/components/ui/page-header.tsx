import Link from "next/link";

export function PageHeader({ title, backHref }: { title: string; backHref: string }) {
  return (
    <div className="pt-6 px-5 pb-1 flex items-center gap-2.5">
      <Link
        href={backHref}
        aria-label="Back"
        className="w-[26px] h-[26px] flex items-center justify-center text-emerald text-lg"
      >
        ‹
      </Link>
      <h1 className="font-serif font-semibold text-[19px] text-emerald-dark">{title}</h1>
    </div>
  );
}
