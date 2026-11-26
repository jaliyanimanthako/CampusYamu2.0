import { useState } from "react";
import { postSetAvatar } from "../api/client.ts";
import {
  getLocalAuthToken,
  getSupabase,
  setLocalAuthSession,
} from "../auth/supabase.ts";
import { AnimalAvatar, AVATARS, saveAvatar, type AvatarId } from "./AnimalAvatar.tsx";
import { ArrowRightIcon } from "./BrandMark.tsx";

interface AvatarPickerModalProps {
  initialAvatar?: AvatarId;
  onSaved: (avatar: AvatarId) => void;
  onToast: (msg: string) => void;
}

export function AvatarPickerModal({
  initialAvatar = "fox",
  onSaved,
  onToast,
}: AvatarPickerModalProps) {
  const [selected, setSelected] = useState<AvatarId>(initialAvatar);
  const [busy, setBusy] = useState(false);

  const handleConfirm = async () => {
    setBusy(true);
    try {
      const sb = getSupabase();
      if (sb) {
        const { error } = await sb.auth.updateUser({
          data: { avatar: selected, avatar_locked: true },
        });
        if (error) {
          onToast(error.message);
          return;
        }
      } else {
        const token = getLocalAuthToken();
        if (token) {
          const updatedUser = await postSetAvatar(selected);
          setLocalAuthSession(token, updatedUser);
        }
      }
      saveAvatar(selected);
      onSaved(selected);
    } catch (err) {
      onToast(err instanceof Error ? err.message : "Could not save avatar");
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="modal-backdrop" role="dialog" aria-modal="true" aria-labelledby="av-modal-title">
      <div className="modal-card">
        <div>
          <span className="label">One last step</span>
          <h2 id="av-modal-title" style={{ marginTop: 8, fontSize: "clamp(24px, 3vw, 32px)" }}>
            Choose your <span className="accent">avatar.</span>
          </h2>
          <p className="muted" style={{ margin: "8px 0 0", fontSize: 15 }}>
            Pick your animal friend now. It cannot be changed later.
          </p>
        </div>

        <div className="avatar-grid" style={{ justifyContent: "center" }} role="group" aria-label="Choose your animal avatar">
          {AVATARS.map((av) => (
            <button
              key={av.id}
              type="button"
              className="avatar-opt"
              aria-pressed={selected === av.id}
              onClick={() => setSelected(av.id)}
            >
              <AnimalAvatar id={av.id} size={48} />
              <span>{av.label}</span>
            </button>
          ))}
        </div>

        <button
          type="button"
          className="btn block"
          disabled={busy}
          onClick={() => void handleConfirm()}
        >
          {busy ? "Saving…" : "Save & continue"} <ArrowRightIcon />
        </button>
      </div>
    </div>
  );
}
