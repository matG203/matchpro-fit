import { useState } from ''react'';

interface CardData {
  overall: number;
  tier: string;
  pace: number;
  shooting: number;
  passing: number;
  dribbling: number;
  defending: number;
  physical: number;
  stamina: number;
  recovery: number;
  composure: number;
}

interface ProfileData {
  displayName: string;
  position: string;
}

interface AvatarData {
  skinTone: string;
  kitColour: string;
  kitPattern: string;
  hairStyle: string;
  hairColour: string;
  facialHair: string;
  bootColour: string;
  bodyType: string;
  pose: string;
  headband: boolean;
  wristTape: boolean;
  gloves: boolean;
  captainArmband: boolean;
  glasses: boolean;
}

interface PlayerCardProps {
  card: CardData;
  profile: ProfileData;
  avatar: AvatarData;
  animated?: boolean;
  compact?: boolean;
}

const TIER_CONFIG = {
  bronze: {
    bgClass: ''bronze-card'',
    borderColor: ''#cd7f32'',
    textColor: ''#ffd9a0'',
    accentColor: ''#cd7f32'',
    label: ''BRONZE'',
  },
  silver: {
    bgClass: ''silver-card'',
    borderColor: ''#a8b2c0'',
    textColor: ''#e2e8f0'',
    accentColor: ''#94a3b8'',
    label: ''SILVER'',
  },
  common_gold: {
    bgClass: ''gold-card'',
    borderColor: ''#f59e0b'',
    textColor: ''#fde68a'',
    accentColor: ''#f59e0b'',
    label: ''GOLD'',
  },
  rare_gold: {
    bgClass: ''rare-gold-card'',
    borderColor: ''#f59e0b'',
    textColor: ''#fde68a'',
    accentColor: ''#fbbf24'',
    label: ''RARE GOLD'',
  },
  elite: {
    bgClass: ''elite-card'',
    borderColor: ''#a78bfa'',
    textColor: ''#e9d5ff'',
    accentColor: ''#a78bfa'',
    label: ''ELITE'',
  },
};

const SKIN_COLORS: Record<string, string> = {
  light: ''#f5cba7'',
  medium_light: ''#e8a87c'',
  medium: ''#c68642'',
  medium_dark: ''#8d5524'',
  dark: ''#4a2912'',
};

const KIT_COLORS: Record<string, string> = {
  red: ''#dc2626'',
  blue: ''#2563eb'',
  green: ''#16a34a'',
  black: ''#1f2937'',
  white: ''#f9fafb'',
  yellow: ''#ca8a04'',
  purple: ''#7c3aed'',
  orange: ''#ea580c'',
  elite_blue: ''#0ea5e9'',
  elite_black: ''#0f172a'',
  gold: ''#f59e0b'',
  chrome: ''#94a3b8'',
};

function AvatarSVG({ avatar, tier }: { avatar: AvatarData; tier: string }) {
  const skinColor = SKIN_COLORS[avatar.skinTone] || SKIN_COLORS.medium;
  const kitColor = KIT_COLORS[avatar.kitColour] || ''#dc2626'';
  const bootColor = KIT_COLORS[avatar.bootColour] || ''#1f2937'';
  const isElite = tier === ''elite'';

  return (
    <svg viewBox="0 0 100 130" className="w-full h-full" xmlns="http://www.w3.org/2000/svg">
      {/* Glow for elite */}
      {isElite && (
        <defs>
          <filter id="elite-glow">
            <feGaussianBlur stdDeviation="2" result="coloredBlur" />
            <feMerge><feMergeNode in="coloredBlur" /><feMergeNode in="SourceGraphic" /></feMerge>
          </filter>
        </defs>
      )}

      {/* Body / Kit */}
      <ellipse cx="50" cy="90" rx="20" ry="25" fill={kitColor} opacity="0.9" />
      
      {/* Kit pattern */}
      {avatar.kitPattern === ''stripes'' && (
        <>
          <line x1="44" y1="65" x2="44" y2="115" stroke="rgba(255,255,255,0.2)" strokeWidth="3" />
          <line x1="50" y1="65" x2="50" y2="115" stroke="rgba(255,255,255,0.2)" strokeWidth="3" />
          <line x1="56" y1="65" x2="56" y2="115" stroke="rgba(255,255,255,0.2)" strokeWidth="3" />
        </>
      )}
      {avatar.kitPattern === ''flame'' && (
        <path d="M40 115 Q35 95 45 80 Q40 90 50 85 Q45 95 55 90 Q50 100 60 95 Q55 110 60 115 Z" fill="rgba(251,191,36,0.4)" />
      )}

      {/* Neck */}
      <rect x="46" y="58" width="8" height="10" rx="2" fill={skinColor} />

      {/* Head */}
      <ellipse cx="50" cy="48" rx="16" ry="18" fill={skinColor} filter={isElite ? ''url(#elite-glow)'' : undefined} />

      {/* Hair */}
      {avatar.hairStyle === ''short'' && <ellipse cx="50" cy="34" rx="16" ry="8" fill={avatar.hairColour === ''gold'' ? ''#f59e0b'' : avatar.hairColour === ''blonde'' ? ''#fde68a'' : avatar.hairColour === ''black'' ? ''#111'' : avatar.hairColour === ''platinum'' ? ''#e2e8f0'' : ''#92400e''} />}
      {avatar.hairStyle === ''long'' && <path d="M34 34 Q34 60 36 65 L40 65 Q38 45 40 34 Q50 26 60 34 Q62 45 60 65 L64 65 Q66 60 66 34 Q57 22 50 23 Q43 22 34 34Z" fill={avatar.hairColour === ''gold'' ? ''#f59e0b'' : ''#92400e''} />}
      {avatar.hairStyle === ''bald'' && null}
      {avatar.hairStyle === ''curly'' && <ellipse cx="50" cy="32" rx="17" ry="10" fill="#1f1209" opacity="0.9" />}
      {avatar.hairStyle === ''fade'' && <>
        <ellipse cx="50" cy="34" rx="16" ry="7" fill="#111" />
        <ellipse cx="50" cy="40" rx="16" ry="4" fill={skinColor} opacity="0.5" />
      </>}

      {/* Eyes */}
      <ellipse cx="44" cy="47" rx="2.5" ry="2" fill="#1f2937" />
      <ellipse cx="56" cy="47" rx="2.5" ry="2" fill="#1f2937" />
      <ellipse cx="44.5" cy="46.5" rx="1" ry="0.8" fill="white" opacity="0.6" />
      <ellipse cx="56.5" cy="46.5" rx="1" ry="0.8" fill="white" opacity="0.6" />

      {/* Glasses */}
      {avatar.glasses && <>
        <rect x="39" y="44" width="10" height="7" rx="2" fill="none" stroke="#94a3b8" strokeWidth="1" />
        <rect x="51" y="44" width="10" height="7" rx="2" fill="none" stroke="#94a3b8" strokeWidth="1" />
        <line x1="49" y1="47" x2="51" y2="47" stroke="#94a3b8" strokeWidth="1" />
      </>}

      {/* Facial hair */}
      {avatar.facialHair === ''stubble'' && <ellipse cx="50" cy="56" rx="8" ry="3" fill="#4b2e2e" opacity="0.3" />}
      {avatar.facialHair === ''beard'' && <path d="M40 53 Q50 62 60 53 Q58 63 50 66 Q42 63 40 53Z" fill="#3b1f1f" opacity="0.6" />}
      {avatar.facialHair === ''moustache'' && <path d="M44 52 Q50 55 56 52 Q53 57 50 56 Q47 57 44 52Z" fill="#3b1f1f" opacity="0.7" />}

      {/* Arms */}
      <ellipse cx="30" cy="85" rx="6" ry="18" fill={kitColor} transform="rotate(-10 30 85)" />
      <ellipse cx="70" cy="85" rx="6" ry="18" fill={kitColor} transform="rotate(10 70 85)" />
      <ellipse cx="27" cy="97" rx="5" ry="7" fill={skinColor} transform="rotate(-10 27 97)" />
      <ellipse cx="73" cy="97" rx="5" ry="7" fill={skinColor} transform="rotate(10 73 97)" />

      {/* Wrist tape */}
      {avatar.wristTape && <>
        <rect x="22" y="97" width="10" height="3" rx="1" fill="white" opacity="0.8" />
        <rect x="68" y="97" width="10" height="3" rx="1" fill="white" opacity="0.8" />
      </>}

      {/* Legs */}
      <rect x="41" y="113" width="8" height="16" rx="3" fill="#1e3a5f" />
      <rect x="51" y="113" width="8" height="16" rx="3" fill="#1e3a5f" />

      {/* Boots */}
      <ellipse cx="45" cy="129" rx="7" ry="3" fill={bootColor} />
      <ellipse cx="55" cy="129" rx="7" ry="3" fill={bootColor} />

      {/* Headband */}
      {avatar.headband && <rect x="34" y="38" width="32" height="4" rx="2" fill="white" opacity="0.9" />}

      {/* Captain armband */}
      {avatar.captainArmband && <rect x="20" y="83" width="14" height="4" rx="2" fill="#f59e0b" opacity="0.9" />}

      {/* Gloves */}
      {avatar.gloves && <>
        <ellipse cx="27" cy="100" rx="6" ry="8" fill="white" opacity="0.8" />
        <ellipse cx="73" cy="100" rx="6" ry="8" fill="white" opacity="0.8" />
      </>}

      {/* Pose modifications */}
      {avatar.pose === ''celebration'' && (
        <line x1="70" y1="75" x2="85" y2="55" stroke={kitColor} strokeWidth="12" strokeLinecap="round" />
      )}
      {avatar.pose === ''power'' && (
        <line x1="30" y1="75" x2="15" y2="60" stroke={kitColor} strokeWidth="12" strokeLinecap="round" />
      )}
    </svg>
  );
}

export default function PlayerCard({ card, profile, avatar, animated = false, compact = false }: PlayerCardProps) {
  const [showBack, setShowBack] = useState(false);
  const tierConfig = TIER_CONFIG[card.tier as keyof typeof TIER_CONFIG] || TIER_CONFIG.bronze;
  const isElite = card.tier === ''elite'';

  const stats = [
    { label: ''PAC'', value: card.pace },
    { label: ''SHO'', value: card.shooting },
    { label: ''PAS'', value: card.passing },
    { label: ''DRI'', value: card.dribbling },
    { label: ''DEF'', value: card.defending },
    { label: ''PHY'', value: card.physical },
    { label: ''STA'', value: card.stamina },
    { label: ''REC'', value: card.recovery },
    { label: ''COM'', value: card.composure },
  ];

  return (
    <div
      className={`relative cursor-pointer select-none ${compact ? ''w-36 h-48'' : ''w-56 h-80''}`}
      onClick={() => setShowBack(!showBack)}
      style={{ perspective: ''1000px'' }}
    >
      <div
        className="relative w-full h-full transition-all duration-700"
        style={{ transformStyle: ''preserve-3d'', transform: showBack ? ''rotateY(180deg)'' : ''rotateY(0)'' }}
      >
        {/* Front */}
        <div
          className={`absolute inset-0 rounded-2xl overflow-hidden ${tierConfig.bgClass} ${isElite ? ''animate-pulse-glow'' : ''''}`}
          style={{
            backfaceVisibility: ''hidden'',
            border: `2px solid ${tierConfig.borderColor}`,
            boxShadow: isElite
              ? `0 0 30px rgba(167,139,250,0.5), 0 0 60px rgba(236,72,153,0.3)`
              : `0 4px 20px rgba(0,0,0,0.5)`,
          }}
        >
          {/* Elite shine overlay */}
          {isElite && (
            <div className="absolute inset-0 elite-shine opacity-60 z-10 pointer-events-none" />
          )}

          <div className="relative z-20 h-full flex flex-col p-3">
            {/* Header */}
            <div className="flex items-start justify-between mb-1">
              <div className="text-center">
                <div
                  className={`font-display font-black leading-none ${compact ? ''text-3xl'' : ''text-4xl''}`}
                  style={{ color: tierConfig.textColor }}
                >
                  {card.overall}
                </div>
                <div className={`font-display font-bold uppercase ${compact ? ''text-[8px]'' : ''text-[10px]''}`} style={{ color: tierConfig.accentColor }}>
                  {profile.position}
                </div>
              </div>
              <div className={`font-display font-black uppercase tracking-wider ${compact ? ''text-[7px]'' : ''text-[9px]''}`} style={{ color: tierConfig.accentColor }}>
                {tierConfig.label}
              </div>
            </div>

            {/* Avatar area */}
            <div className={`flex-1 flex items-center justify-center ${compact ? ''py-1'' : ''py-2''}`}>
              <div className={compact ? ''w-20 h-24'' : ''w-32 h-40''}>
                <AvatarSVG avatar={avatar} tier={card.tier} />
              </div>
            </div>

            {/* Name */}
            <div className="text-center mb-2">
              <div
                className={`font-display font-black uppercase tracking-wide ${compact ? ''text-xs'' : ''text-sm''}`}
                style={{ color: tierConfig.textColor }}
              >
                {profile.displayName.toUpperCase()}
              </div>
            </div>

            {/* Stats grid */}
            {!compact && (
              <div className="grid grid-cols-3 gap-1">
                {stats.map(({ label, value }) => (
                  <div key={label} className="text-center">
                    <div className="font-display font-black text-sm" style={{ color: tierConfig.textColor }}>{value}</div>
                    <div className="text-[8px] font-medium" style={{ color: tierConfig.accentColor, opacity: 0.8 }}>{label}</div>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>

        {/* Back - full stats */}
        <div
          className={`absolute inset-0 rounded-2xl overflow-hidden ${tierConfig.bgClass}`}
          style={{
            backfaceVisibility: ''hidden'',
            transform: ''rotateY(180deg)'',
            border: `2px solid ${tierConfig.borderColor}`,
          }}
        >
          <div className="h-full flex flex-col p-3">
            <div className="text-center mb-2">
              <div className="font-display font-bold text-sm" style={{ color: tierConfig.textColor }}>FULL STATS</div>
            </div>
            <div className="flex-1 space-y-1.5">
              {stats.map(({ label, value }) => (
                <div key={label} className="flex items-center gap-2">
                  <div className="text-[9px] font-display font-bold w-8" style={{ color: tierConfig.accentColor }}>{label}</div>
                  <div className="flex-1 h-1.5 rounded-full bg-black/30">
                    <div
                      className="h-full rounded-full transition-all"
                      style={{
                        width: `${value}%`,
                        backgroundColor: value >= 80 ? ''#10b981'' : value >= 65 ? ''#f59e0b'' : tierConfig.accentColor,
                      }}
                    />
                  </div>
                  <div className="text-[10px] font-display font-black w-6 text-right" style={{ color: tierConfig.textColor }}>{value}</div>
                </div>
              ))}
            </div>
            <div className="text-center mt-2">
              <div className="text-[8px] text-gray-500">Tap to flip</div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
