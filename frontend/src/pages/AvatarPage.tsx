import { useEffect, useState } from 'react';
import { Lock, Zap, Save } from 'lucide-react';
import api from '../lib/api';
import PlayerCard from '../components/card/PlayerCard';

interface AvatarData {
  skinTone: string; hairStyle: string; hairColour: string; facialHair: string;
  kitColour: string; kitPattern: string; bootColour: string; bodyType: string;
  pose: string; headband: boolean; wristTape: boolean; gloves: boolean;
  captainArmband: boolean; glasses: boolean;
}

interface UnlockItem {
  key: string; label: string; type: string; value: string | boolean; xpRequired: number;
}

interface AvatarPageData {
  avatar: AvatarData;
  unlocks: UnlockItem[];
  unlockedKeys: string[];
  totalXp: number;
}

const SKIN_TONES = [
  { value: 'light', label: 'Light', color: '#f5cba7' },
  { value: 'medium_light', label: 'Med Light', color: '#e8a87c' },
  { value: 'medium', label: 'Medium', color: '#c68642' },
  { value: 'medium_dark', label: 'Med Dark', color: '#8d5524' },
  { value: 'dark', label: 'Dark', color: '#4a2912' },
];

const HAIR_STYLES = ['short', 'long', 'curly', 'fade', 'bald'];
const BASE_HAIR_COLOURS = ['brown', 'black', 'blonde', 'red', 'grey'];
const BASE_KIT_COLOURS = ['red', 'blue', 'green', 'black', 'white', 'yellow', 'purple', 'orange'];
const BASE_KIT_PATTERNS = ['plain', 'stripes', 'halves'];
const BASE_BOOT_COLOURS = ['black', 'white', 'red', 'blue', 'green', 'yellow'];
const FACIAL_HAIR = ['none', 'stubble', 'beard', 'moustache'];
const BODY_TYPES = ['athletic', 'lean', 'stocky', 'muscular'];
const POSES = ['ready', 'arms_crossed'];

function ColourSwatch({ color, label, selected, onClick, locked }: {
  color: string; label: string; selected: boolean; onClick: () => void; locked?: boolean;
}) {
  return (
    <button
      onClick={locked ? undefined : onClick}
      className={`relative flex flex-col items-center gap-1 group ${locked ? 'opacity-40 cursor-not-allowed' : 'cursor-pointer'}`}
    >
      <div
        className={`w-10 h-10 rounded-full border-2 transition-all ${selected ? 'border-electric-400 scale-110' : 'border-transparent hover:border-gray-500'}`}
        style={{ backgroundColor: color }}
      >
        {locked && (
          <div className="absolute inset-0 flex items-center justify-center">
            <Lock size={10} className="text-white" />
          </div>
        )}
      </div>
      <span className="text-[9px] text-gray-500 leading-none">{label}</span>
    </button>
  );
}

function OptionButton({ label, selected, onClick, locked, xpRequired }: {
  label: string; selected: boolean; onClick: () => void; locked?: boolean; xpRequired?: number;
}) {
  return (
    <button
      onClick={locked ? undefined : onClick}
      className={`relative px-3 py-2 rounded-lg text-xs font-medium border transition-all ${
        locked ? 'opacity-40 cursor-not-allowed bg-pitch-800 border-pitch-600 text-gray-600'
        : selected ? 'bg-electric-500/20 border-electric-500 text-electric-400'
        : 'bg-pitch-700 border-pitch-600 text-gray-300 hover:border-gray-500'
      }`}
    >
      {locked && <Lock size={8} className="inline mr-1 opacity-60" />}
      {label}
      {locked && xpRequired && (
        <span className="ml-1 text-yellow-500 text-[9px]">
          <Zap size={7} className="inline" />{xpRequired.toLocaleString()}
        </span>
      )}
    </button>
  );
}

function ToggleButton({ label, value, onChange, locked, xpRequired }: {
  label: string; value: boolean; onChange: (v: boolean) => void; locked?: boolean; xpRequired?: number;
}) {
  return (
    <button
      onClick={locked ? undefined : () => onChange(!value)}
      className={`flex items-center justify-between w-full px-3 py-2.5 rounded-lg border transition-all ${
        locked ? 'opacity-40 cursor-not-allowed bg-pitch-800 border-pitch-600'
        : value ? 'bg-electric-500/20 border-electric-500'
        : 'bg-pitch-700 border-pitch-600 hover:border-gray-500'
      }`}
    >
      <span className={`text-sm font-medium ${value ? 'text-electric-400' : 'text-gray-300'}`}>{label}</span>
      <div className="flex items-center gap-2">
        {locked && xpRequired && (
          <span className="text-yellow-500 text-xs flex items-center gap-0.5">
            <Lock size={10} /> <Zap size={9} />{xpRequired.toLocaleString()} XP
          </span>
        )}
        <div className={`w-10 h-5 rounded-full transition-colors ${value && !locked ? 'bg-electric-500' : 'bg-pitch-600'}`}>
          <div className={`w-4 h-4 rounded-full bg-white mt-0.5 transition-transform ${value && !locked ? 'translate-x-5' : 'translate-x-0.5'}`} />
        </div>
      </div>
    </button>
  );
}

export default function AvatarPage() {
  const [pageData, setPageData] = useState<AvatarPageData | null>(null);
  const [avatar, setAvatar] = useState<AvatarData | null>(null);
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    api.get('/avatar').then(r => {
      setPageData(r.data);
      setAvatar(r.data.avatar);
      setLoading(false);
    });
  }, []);

  const update = (key: keyof AvatarData, val: string | boolean) => {
    setAvatar(a => a ? { ...a, [key]: val } : a);
    setSaved(false);
  };

  const isUnlocked = (key: string) => pageData?.unlockedKeys.includes(key) ?? false;
  const getXpRequired = (key: string) => pageData?.unlocks.find(u => u.key === key)?.xpRequired ?? 0;

  const isKitColourLocked = (colour: string) => {
    const unlock = pageData?.unlocks.find(u => u.type === 'kitColour' && u.value === colour);
    return unlock ? !isUnlocked(unlock.key) : false;
  };
  const isKitPatternLocked = (pattern: string) => {
    const unlock = pageData?.unlocks.find(u => u.type === 'kitPattern' && u.value === pattern);
    return unlock ? !isUnlocked(unlock.key) : false;
  };
  const isBootColourLocked = (colour: string) => {
    const unlock = pageData?.unlocks.find(u => u.type === 'bootColour' && u.value === colour);
    return unlock ? !isUnlocked(unlock.key) : false;
  };
  const isPoseLocked = (pose: string) => {
    const unlock = pageData?.unlocks.find(u => u.type === 'pose' && u.value === pose);
    return unlock ? !isUnlocked(unlock.key) : false;
  };
  const isBodyTypeLocked = (bt: string) => {
    const unlock = pageData?.unlocks.find(u => u.type === 'bodyType' && u.value === bt);
    return unlock ? !isUnlocked(unlock.key) : false;
  };
  const isHairColourLocked = (colour: string) => {
    const unlock = pageData?.unlocks.find(u => u.type === 'hairColour' && u.value === colour);
    return unlock ? !isUnlocked(unlock.key) : false;
  };
  const isAccessoryLocked = (type: string) => {
    const unlock = pageData?.unlocks.find(u => u.type === type && u.value === true);
    return unlock ? !isUnlocked(unlock.key) : false;
  };
  const getAccessoryXp = (type: string) => {
    const unlock = pageData?.unlocks.find(u => u.type === type && u.value === true);
    return unlock ? getXpRequired(unlock.key) : 0;
  };

  const handleSave = async () => {
    if (!avatar) return;
    setSaving(true);
    try {
      await api.put('/avatar', avatar);
      setSaved(true);
    } catch (err: any) {
      alert(err.response?.data?.error || 'Save failed');
    } finally {
      setSaving(false);
    }
  };

  if (loading || !avatar) {
    return <div className="flex items-center justify-center min-h-screen"><div className="text-electric-400 font-display font-bold animate-pulse">LOADING...</div></div>;
  }

  const dummyCard = { overall: 45, tier: 'bronze', pace: 45, shooting: 45, passing: 45, dribbling: 45, defending: 45, physical: 45, stamina: 45, recovery: 45, composure: 45 };
  const dummyProfile = { displayName: 'YOU', position: 'CM' };

  const allHairColours = [...BASE_HAIR_COLOURS,
    ...(pageData?.unlocks.filter(u => u.type === 'hairColour').map(u => u.value as string) || [])
  ];
  const allKitColours = [...BASE_KIT_COLOURS,
    ...(pageData?.unlocks.filter(u => u.type === 'kitColour').map(u => u.value as string) || [])
  ];
  const allKitPatterns = [...BASE_KIT_PATTERNS,
    ...(pageData?.unlocks.filter(u => u.type === 'kitPattern').map(u => u.value as string) || [])
  ];
  const allBootColours = [...BASE_BOOT_COLOURS,
    ...(pageData?.unlocks.filter(u => u.type === 'bootColour').map(u => u.value as string) || [])
  ];
  const allPoses = [...POSES,
    ...(pageData?.unlocks.filter(u => u.type === 'pose').map(u => u.value as string) || [])
  ];
  const allBodyTypes = [...BODY_TYPES];

  return (
    <div className="px-4 py-4 pb-8 space-y-5">
      <div className="flex items-center justify-between">
        <h1 className="section-title">Avatar</h1>
        <button onClick={handleSave} disabled={saving} className={`flex items-center gap-1.5 text-sm px-3 py-2 rounded-lg font-medium transition-all ${saved ? 'bg-emerald-500/20 text-emerald-400 border border-emerald-500/40' : 'btn-primary'}`}>
          <Save size={14} /> {saving ? 'Saving...' : saved ? 'Saved!' : 'Save'}
        </button>
      </div>

      {/* XP unlock progress */}
      <div className="card bg-gradient-to-r from-yellow-500/5 to-orange-500/5 border border-yellow-500/20">
        <div className="flex items-center justify-between">
          <div>
            <div className="text-xs text-gray-400 mb-0.5">Your XP</div>
            <div className="font-display font-black text-xl text-yellow-400 flex items-center gap-1">
              <Zap size={16} /> {(pageData?.totalXp || 0).toLocaleString()}
            </div>
          </div>
          <div className="text-right text-xs text-gray-500">
            <div>Earn XP by completing</div>
            <div>workouts & challenges</div>
            <div>to unlock avatar items</div>
          </div>
        </div>
      </div>

      {/* Preview */}
      <div className="flex justify-center py-2">
        <PlayerCard card={dummyCard} profile={dummyProfile} avatar={avatar} compact />
      </div>

      {/* Skin Tone */}
      <div className="card">
        <h3 className="label mb-3">Skin Tone</h3>
        <div className="flex gap-4 flex-wrap">
          {SKIN_TONES.map(s => (
            <ColourSwatch key={s.value} color={s.color} label={s.label} selected={avatar.skinTone === s.value} onClick={() => update('skinTone', s.value)} />
          ))}
        </div>
      </div>

      {/* Hair */}
      <div className="card">
        <h3 className="label mb-3">Hair Style</h3>
        <div className="flex flex-wrap gap-2 mb-4">
          {HAIR_STYLES.map(h => (
            <OptionButton key={h} label={h.charAt(0).toUpperCase() + h.slice(1)} selected={avatar.hairStyle === h} onClick={() => update('hairStyle', h)} />
          ))}
        </div>
        <h3 className="label mb-3">Hair Colour</h3>
        <div className="flex flex-wrap gap-2">
          {allHairColours.map(c => {
            const locked = isHairColourLocked(c);
            const xpReq = locked ? getXpRequired(pageData?.unlocks.find(u => u.type === 'hairColour' && u.value === c)?.key || '') : 0;
            return (
              <OptionButton key={c} label={c.charAt(0).toUpperCase() + c.slice(1)} selected={avatar.hairColour === c} onClick={() => update('hairColour', c)} locked={locked} xpRequired={xpReq} />
            );
          })}
        </div>
      </div>

      {/* Facial Hair */}
      <div className="card">
        <h3 className="label mb-3">Facial Hair</h3>
        <div className="flex flex-wrap gap-2">
          {FACIAL_HAIR.map(f => (
            <OptionButton key={f} label={f.charAt(0).toUpperCase() + f.slice(1)} selected={avatar.facialHair === f} onClick={() => update('facialHair', f)} />
          ))}
        </div>
      </div>

      {/* Kit */}
      <div className="card">
        <h3 className="label mb-3">Kit Colour</h3>
        <div className="flex flex-wrap gap-2 mb-4">
          {allKitColours.map(c => {
            const locked = isKitColourLocked(c);
            const xpReq = locked ? getXpRequired(pageData?.unlocks.find(u => u.type === 'kitColour' && u.value === c)?.key || '') : 0;
            return <OptionButton key={c} label={c.replace('_', ' ')} selected={avatar.kitColour === c} onClick={() => update('kitColour', c)} locked={locked} xpRequired={xpReq} />;
          })}
        </div>
        <h3 className="label mb-3">Kit Pattern</h3>
        <div className="flex flex-wrap gap-2">
          {allKitPatterns.map(p => {
            const locked = isKitPatternLocked(p);
            const xpReq = locked ? getXpRequired(pageData?.unlocks.find(u => u.type === 'kitPattern' && u.value === p)?.key || '') : 0;
            return <OptionButton key={p} label={p.charAt(0).toUpperCase() + p.slice(1)} selected={avatar.kitPattern === p} onClick={() => update('kitPattern', p)} locked={locked} xpRequired={xpReq} />;
          })}
        </div>
      </div>

      {/* Boots */}
      <div className="card">
        <h3 className="label mb-3">Boot Colour</h3>
        <div className="flex flex-wrap gap-2">
          {allBootColours.map(c => {
            const locked = isBootColourLocked(c);
            const xpReq = locked ? getXpRequired(pageData?.unlocks.find(u => u.type === 'bootColour' && u.value === c)?.key || '') : 0;
            return <OptionButton key={c} label={c.charAt(0).toUpperCase() + c.slice(1)} selected={avatar.bootColour === c} onClick={() => update('bootColour', c)} locked={locked} xpRequired={xpReq} />;
          })}
        </div>
      </div>

      {/* Body & Pose */}
      <div className="card">
        <h3 className="label mb-3">Body Type</h3>
        <div className="flex flex-wrap gap-2 mb-4">
          {allBodyTypes.map(b => {
            const locked = isBodyTypeLocked(b);
            const xpReq = locked ? getXpRequired(pageData?.unlocks.find(u => u.type === 'bodyType' && u.value === b)?.key || '') : 0;
            return <OptionButton key={b} label={b.charAt(0).toUpperCase() + b.slice(1)} selected={avatar.bodyType === b} onClick={() => update('bodyType', b)} locked={locked} xpRequired={xpReq} />;
          })}
        </div>
        <h3 className="label mb-3">Pose</h3>
        <div className="flex flex-wrap gap-2">
          {allPoses.map(p => {
            const locked = isPoseLocked(p);
            const xpReq = locked ? getXpRequired(pageData?.unlocks.find(u => u.type === 'pose' && u.value === p)?.key || '') : 0;
            return <OptionButton key={p} label={p.replace('_', ' ')} selected={avatar.pose === p} onClick={() => update('pose', p)} locked={locked} xpRequired={xpReq} />;
          })}
        </div>
      </div>

      {/* Accessories */}
      <div className="card">
        <h3 className="label mb-3">Accessories</h3>
        <div className="space-y-2">
          <ToggleButton label="Headband" value={avatar.headband} onChange={v => update('headband', v)} locked={isAccessoryLocked('headband')} xpRequired={getAccessoryXp('headband')} />
          <ToggleButton label="Wrist Tape" value={avatar.wristTape} onChange={v => update('wristTape', v)} locked={isAccessoryLocked('wristTape')} xpRequired={getAccessoryXp('wristTape')} />
          <ToggleButton label="GK Gloves" value={avatar.gloves} onChange={v => update('gloves', v)} locked={isAccessoryLocked('gloves')} xpRequired={getAccessoryXp('gloves')} />
          <ToggleButton label="Captain Armband ðŸ†" value={avatar.captainArmband} onChange={v => update('captainArmband', v)} locked={isAccessoryLocked('captainArmband')} xpRequired={getAccessoryXp('captainArmband')} />
          <ToggleButton label="Shades ðŸ˜Ž" value={avatar.glasses} onChange={v => update('glasses', v)} locked={isAccessoryLocked('glasses')} xpRequired={getAccessoryXp('glasses')} />
        </div>
        <p className="text-xs text-gray-600 mt-3 flex items-center gap-1">
          <Lock size={10} /> Items with lock icon require XP to unlock â€” keep grinding!
        </p>
      </div>
    </div>
  );
}
