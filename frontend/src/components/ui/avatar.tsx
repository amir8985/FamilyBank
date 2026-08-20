import { initial } from "@/lib/format";

const AVATAR_BG: Record<string, string> = {
  amber: "bg-avatar-amber",
  teal: "bg-avatar-teal",
  violet: "bg-avatar-violet",
  rose: "bg-avatar-rose",
  sky: "bg-avatar-sky",
  lime: "bg-avatar-lime",
};

export function Avatar({
  name,
  color,
  size = 38,
}: {
  name: string;
  color: string;
  size?: number;
}) {
  return (
    <div
      className={`shrink-0 rounded-full flex items-center justify-center font-semibold text-emerald ${AVATAR_BG[color] ?? "bg-avatar-amber"}`}
      style={{ width: size, height: size, fontSize: size * 0.37 }}
    >
      {initial(name)}
    </div>
  );
}
