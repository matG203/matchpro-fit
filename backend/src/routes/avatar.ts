import { Router, Response } from ''express'';
import { z } from ''zod'';
import { prisma } from ''../utils/prisma'';
import { authenticate, AuthRequest } from ''../middleware/auth'';

export const avatarRouter = Router();

// XP unlock thresholds for avatar items
export const AVATAR_UNLOCKS = [
  { key: ''hair_gold'', label: ''Gold Hair'', type: ''hairColour'', value: ''gold'', xpRequired: 500 },
  { key: ''hair_platinum'', label: ''Platinum Hair'', type: ''hairColour'', value: ''platinum'', xpRequired: 1500 },
  { key: ''kit_elite_blue'', label: ''Elite Blue Kit'', type: ''kitColour'', value: ''elite_blue'', xpRequired: 800 },
  { key: ''kit_elite_black'', label: ''Blackout Kit'', type: ''kitColour'', value: ''elite_black'', xpRequired: 1200 },
  { key: ''kit_gold'', label: ''Gold Kit'', type: ''kitColour'', value: ''gold'', xpRequired: 2500 },
  { key: ''kit_chrome'', label: ''Chrome Kit'', type: ''kitColour'', value: ''chrome'', xpRequired: 5000 },
  { key: ''kit_flame'', label: ''Flame Kit'', type: ''kitPattern'', value: ''flame'', xpRequired: 1000 },
  { key: ''kit_camo'', label: ''Camo Kit'', type: ''kitPattern'', value: ''camo'', xpRequired: 2000 },
  { key: ''kit_lightning'', label: ''Lightning Kit'', type: ''kitPattern'', value: ''lightning'', xpRequired: 3500 },
  { key: ''boots_gold'', label: ''Gold Boots'', type: ''bootColour'', value: ''gold'', xpRequired: 750 },
  { key: ''boots_platinum'', label: ''Platinum Boots'', type: ''bootColour'', value: ''platinum'', xpRequired: 2000 },
  { key: ''boots_chrome'', label: ''Chrome Boots'', type: ''bootColour'', value: ''chrome'', xpRequired: 4000 },
  { key: ''pose_celebration'', label: ''Celebration Pose'', type: ''pose'', value: ''celebration'', xpRequired: 600 },
  { key: ''pose_power'', label: ''Power Pose'', type: ''pose'', value: ''power'', xpRequired: 1500 },
  { key: ''pose_elite'', label: ''Elite Pose'', type: ''pose'', value: ''elite'', xpRequired: 3000 },
  { key: ''accessory_headband'', label: ''Headband'', type: ''headband'', value: true, xpRequired: 300 },
  { key: ''accessory_wrist_tape'', label: ''Wrist Tape'', type: ''wristTape'', value: true, xpRequired: 400 },
  { key: ''accessory_gloves'', label: ''GK Gloves'', type: ''gloves'', value: true, xpRequired: 700 },
  { key: ''accessory_captain'', label: ''Captain Armband'', type: ''captainArmband'', value: true, xpRequired: 1000 },
  { key: ''accessory_glasses'', label: ''Shades'', type: ''glasses'', value: true, xpRequired: 500 },
  { key: ''body_muscular'', label: ''Muscular Build'', type: ''bodyType'', value: ''muscular'', xpRequired: 2000 },
  { key: ''body_lean'', label: ''Lean Build'', type: ''bodyType'', value: ''lean'', xpRequired: 1000 },
];

avatarRouter.get(''/'', authenticate, async (req: AuthRequest, res: Response) => {
  const avatar = await prisma.avatar.findUnique({ where: { userId: req.userId } });
  const card = await prisma.playerCard.findUnique({ where: { userId: req.userId } });
  const totalXp = card?.totalXp || 0;
  const unlocked = AVATAR_UNLOCKS.filter((u) => totalXp >= u.xpRequired);
  return res.json({ avatar, unlocks: AVATAR_UNLOCKS, unlockedKeys: unlocked.map((u) => u.key), totalXp });
});

const avatarUpdateSchema = z.object({
  skinTone: z.string().optional(),
  hairStyle: z.string().optional(),
  hairColour: z.string().optional(),
  facialHair: z.string().optional(),
  kitColour: z.string().optional(),
  kitPattern: z.string().optional(),
  bootColour: z.string().optional(),
  bodyType: z.string().optional(),
  pose: z.string().optional(),
  headband: z.boolean().optional(),
  wristTape: z.boolean().optional(),
  gloves: z.boolean().optional(),
  captainArmband: z.boolean().optional(),
  glasses: z.boolean().optional(),
});

avatarRouter.put(''/'', authenticate, async (req: AuthRequest, res: Response) => {
  try {
    const data = avatarUpdateSchema.parse(req.body);
    const card = await prisma.playerCard.findUnique({ where: { userId: req.userId } });
    const totalXp = card?.totalXp || 0;

    // Validate XP-locked items
    for (const unlock of AVATAR_UNLOCKS) {
      const fieldVal = data[unlock.type as keyof typeof data];
      if (fieldVal === unlock.value && totalXp < unlock.xpRequired) {
        return res.status(403).json({ error: `${unlock.label} requires ${unlock.xpRequired} XP to unlock` });
      }
    }

    const avatar = await prisma.avatar.update({ where: { userId: req.userId }, data });
    return res.json(avatar);
  } catch (err) {
    if (err instanceof z.ZodError) return res.status(400).json({ error: err.errors });
    throw err;
  }
});
