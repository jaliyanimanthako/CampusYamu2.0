export type AvatarId =
  | "cat"
  | "fox"
  | "bear"
  | "bunny"
  | "panda"
  | "owl"
  | "koala"
  | "dog";

export interface AvatarMeta {
  id: AvatarId;
  label: string;
  bg: string;
}

export const AVATARS: readonly AvatarMeta[] = [
  { id: "fox", label: "Fox", bg: "#FDF1D6" },
  { id: "cat", label: "Cat", bg: "#ECE4FD" },
  { id: "bear", label: "Bear", bg: "#E3EBFF" },
  { id: "bunny", label: "Bunny", bg: "#FCE7F3" },
  { id: "panda", label: "Panda", bg: "#E6F6EC" },
  { id: "owl", label: "Owl", bg: "#EDE9FE" },
  { id: "koala", label: "Koala", bg: "#E0F2FE" },
  { id: "dog", label: "Puppy", bg: "#FEF3C7" },
] as const;

const AVATAR_KEY = "cy.avatar";

export function loadSavedAvatar(email?: string | null): AvatarId {
  try {
    const saved = window.localStorage.getItem(AVATAR_KEY);
    if (saved && AVATARS.some((a) => a.id === saved)) {
      return saved as AvatarId;
    }
  } catch {
    // Ignore storage errors
  }
  if (email) {
    const sum = email.split("").reduce((acc, ch) => acc + ch.charCodeAt(0), 0);
    return AVATARS[sum % AVATARS.length].id;
  }
  return "fox";
}

export function saveAvatar(id: AvatarId): void {
  try {
    window.localStorage.setItem(AVATAR_KEY, id);
  } catch {
    // Ignore storage errors
  }
}

export function AnimalAvatar({
  id,
  size = 40,
}: {
  id: AvatarId;
  size?: number;
}) {
  const meta = AVATARS.find((a) => a.id === id) ?? AVATARS[0];

  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 64 64"
      aria-label={`${meta.label} avatar`}
      style={{ display: "block", borderRadius: "50%", flexShrink: 0 }}
    >
      <circle cx="32" cy="32" r="32" fill={meta.bg} />

      {id === "fox" && (
        <g>
          <polygon points="14,26 18,10 29,21" fill="#E87A3D" />
          <polygon points="50,26 46,10 35,21" fill="#E87A3D" />
          <polygon points="17,24 19,14 26,21" fill="#FDE6D8" />
          <polygon points="47,24 45,14 38,21" fill="#FDE6D8" />
          <ellipse cx="32" cy="35" rx="18" ry="15" fill="#F28C4B" />
          <path d="M14,37 Q23,33 32,45 Q41,33 50,37 Q46,50 32,50 Q18,50 14,37 Z" fill="#FFFFFF" />
          <circle cx="25" cy="33" r="2.6" fill="#14185C" />
          <circle cx="39" cy="33" r="2.6" fill="#14185C" />
          <circle cx="25.8" cy="32.2" r="0.9" fill="#FFFFFF" />
          <circle cx="39.8" cy="32.2" r="0.9" fill="#FFFFFF" />
          <ellipse cx="32" cy="40" rx="3" ry="2.2" fill="#14185C" />
          <path d="M29,43.5 Q32,46 35,43.5" fill="none" stroke="#14185C" strokeWidth="1.8" strokeLinecap="round" />
        </g>
      )}

      {id === "cat" && (
        <g>
          <polygon points="15,27 17,11 29,20" fill="#8D7CE8" />
          <polygon points="49,27 47,11 35,20" fill="#8D7CE8" />
          <polygon points="18,24 19,15 26,20" fill="#F9B4C9" />
          <polygon points="46,24 45,15 38,20" fill="#F9B4C9" />
          <ellipse cx="32" cy="35" rx="18" ry="15.5" fill="#A99CF2" />
          <ellipse cx="22" cy="38" rx="3.2" ry="1.8" fill="#F9B4C9" opacity="0.8" />
          <ellipse cx="42" cy="38" rx="3.2" ry="1.8" fill="#F9B4C9" opacity="0.8" />
          <circle cx="25" cy="33" r="2.7" fill="#14185C" />
          <circle cx="39" cy="33" r="2.7" fill="#14185C" />
          <circle cx="25.9" cy="32.1" r="0.9" fill="#FFFFFF" />
          <circle cx="39.9" cy="32.1" r="0.9" fill="#FFFFFF" />
          <polygon points="30,38 34,38 32,40.5" fill="#F472B6" />
          <path d="M28,42.5 Q30,44.5 32,41.5 Q34,44.5 36,42.5" fill="none" stroke="#14185C" strokeWidth="1.8" strokeLinecap="round" />
          <path d="M12,35 H19 M12,38.5 H19 M45,35 H52 M45,38.5 H52" stroke="#14185C" strokeWidth="1.4" strokeLinecap="round" opacity="0.55" />
        </g>
      )}

      {id === "bear" && (
        <g>
          <circle cx="17" cy="20" r="7" fill="#8C5A3C" />
          <circle cx="47" cy="20" r="7" fill="#8C5A3C" />
          <circle cx="17" cy="20" r="3.8" fill="#D8A98B" />
          <circle cx="47" cy="20" r="3.8" fill="#D8A98B" />
          <ellipse cx="32" cy="35" rx="18" ry="16" fill="#A46B48" />
          <ellipse cx="32" cy="40" rx="8.5" ry="6.5" fill="#F3D9C6" />
          <circle cx="24.5" cy="32" r="2.6" fill="#14185C" />
          <circle cx="39.5" cy="32" r="2.6" fill="#14185C" />
          <circle cx="25.3" cy="31.2" r="0.9" fill="#FFFFFF" />
          <circle cx="40.3" cy="31.2" r="0.9" fill="#FFFFFF" />
          <ellipse cx="32" cy="38" rx="3.2" ry="2.2" fill="#14185C" />
          <path d="M29,42 Q32,44.5 35,42" fill="none" stroke="#14185C" strokeWidth="1.8" strokeLinecap="round" />
        </g>
      )}

      {id === "bunny" && (
        <g>
          <ellipse cx="23" cy="17" rx="5.2" ry="12" fill="#FFFFFF" stroke="#E2D5F8" strokeWidth="1.5" />
          <ellipse cx="41" cy="17" rx="5.2" ry="12" fill="#FFFFFF" stroke="#E2D5F8" strokeWidth="1.5" />
          <ellipse cx="23" cy="17" rx="2.6" ry="8" fill="#F9B4C9" />
          <ellipse cx="41" cy="17" rx="2.6" ry="8" fill="#F9B4C9" />
          <ellipse cx="32" cy="37" rx="17.5" ry="15" fill="#FFFFFF" stroke="#E2D5F8" strokeWidth="1.5" />
          <ellipse cx="22" cy="39" rx="3.2" ry="1.8" fill="#F9B4C9" />
          <ellipse cx="42" cy="39" rx="3.2" ry="1.8" fill="#F9B4C9" />
          <circle cx="25.5" cy="35" r="2.6" fill="#14185C" />
          <circle cx="38.5" cy="35" r="2.6" fill="#14185C" />
          <circle cx="26.3" cy="34.2" r="0.9" fill="#FFFFFF" />
          <circle cx="39.3" cy="34.2" r="0.9" fill="#FFFFFF" />
          <ellipse cx="32" cy="39" rx="2.3" ry="1.7" fill="#F472B6" />
          <path d="M29.5,42.5 Q32,45 34.5,42.5" fill="none" stroke="#14185C" strokeWidth="1.8" strokeLinecap="round" />
        </g>
      )}

      {id === "panda" && (
        <g>
          <circle cx="17" cy="20" r="6.8" fill="#14185C" />
          <circle cx="47" cy="20" r="6.8" fill="#14185C" />
          <ellipse cx="32" cy="35" rx="18" ry="16" fill="#FFFFFF" />
          <ellipse cx="24" cy="34" rx="5.5" ry="4.5" transform="rotate(-18 24 34)" fill="#14185C" />
          <ellipse cx="40" cy="34" rx="5.5" ry="4.5" transform="rotate(18 40 34)" fill="#14185C" />
          <circle cx="24.5" cy="33.5" r="2" fill="#FFFFFF" />
          <circle cx="39.5" cy="33.5" r="2" fill="#FFFFFF" />
          <circle cx="24.8" cy="33.5" r="1" fill="#14185C" />
          <circle cx="39.2" cy="33.5" r="1" fill="#14185C" />
          <ellipse cx="32" cy="40" rx="3" ry="2" fill="#14185C" />
          <path d="M29,43.5 Q32,46 35,43.5" fill="none" stroke="#14185C" strokeWidth="1.8" strokeLinecap="round" />
        </g>
      )}

      {id === "owl" && (
        <g>
          <polygon points="15,24 19,14 26,21" fill="#4F6FE8" />
          <polygon points="49,24 45,14 38,21" fill="#4F6FE8" />
          <ellipse cx="32" cy="36" rx="18" ry="16" fill="#4F6FE8" />
          <circle cx="24.5" cy="33" r="7.5" fill="#FFFFFF" />
          <circle cx="39.5" cy="33" r="7.5" fill="#FFFFFF" />
          <circle cx="25.5" cy="33" r="3.4" fill="#14185C" />
          <circle cx="38.5" cy="33" r="3.4" fill="#14185C" />
          <circle cx="26.5" cy="32" r="1.1" fill="#FFFFFF" />
          <circle cx="39.5" cy="32" r="1.1" fill="#FFFFFF" />
          <polygon points="29,37 35,37 32,42" fill="#F2B84B" />
        </g>
      )}

      {id === "koala" && (
        <g>
          <circle cx="15" cy="28" r="8.5" fill="#94A3B8" />
          <circle cx="49" cy="28" r="8.5" fill="#94A3B8" />
          <circle cx="15" cy="28" r="4.8" fill="#E2E8F0" />
          <circle cx="49" cy="28" r="4.8" fill="#E2E8F0" />
          <ellipse cx="32" cy="36" rx="16.5" ry="15" fill="#CBD5E1" />
          <circle cx="24" cy="34" r="2.5" fill="#14185C" />
          <circle cx="40" cy="34" r="2.5" fill="#14185C" />
          <circle cx="24.8" cy="33.2" r="0.9" fill="#FFFFFF" />
          <circle cx="40.8" cy="33.2" r="0.9" fill="#FFFFFF" />
          <ellipse cx="32" cy="38" rx="4.2" ry="5.5" fill="#14185C" />
          <path d="M29,45.5 Q32,47.5 35,45.5" fill="none" stroke="#14185C" strokeWidth="1.6" strokeLinecap="round" />
        </g>
      )}

      {id === "dog" && (
        <g>
          <ellipse cx="16" cy="33" rx="5.5" ry="11" transform="rotate(14 16 33)" fill="#C68642" />
          <ellipse cx="48" cy="33" rx="5.5" ry="11" transform="rotate(-14 48 33)" fill="#C68642" />
          <ellipse cx="32" cy="35" rx="17" ry="15.5" fill="#F2B84B" />
          <ellipse cx="32" cy="40" rx="8.5" ry="6.5" fill="#FFFBEB" />
          <circle cx="25" cy="32" r="2.6" fill="#14185C" />
          <circle cx="39" cy="32" r="2.6" fill="#14185C" />
          <circle cx="25.8" cy="31.2" r="0.9" fill="#FFFFFF" />
          <circle cx="39.8" cy="31.2" r="0.9" fill="#FFFFFF" />
          <ellipse cx="32" cy="38" rx="3.2" ry="2.2" fill="#14185C" />
          <path d="M29,42 Q32,44.5 35,42" fill="none" stroke="#14185C" strokeWidth="1.8" strokeLinecap="round" />
          <path d="M30.5,43.5 Q32,47.5 33.5,43.5" fill="#F472B6" />
        </g>
      )}
    </svg>
  );
}
